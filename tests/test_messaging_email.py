# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-11  (pending release) Created (Batch A closing fix, fix5 code review
#   M4, NO-DRIFT): send_email sends the required from (from_) and a replyTo
#   string or list, sync and async; the optional fields only when given.
# =============================================================================

"""Contract tests for messaging.send_email."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = {"content-type": "application/json"}
    body = {"success": True, "data": data}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


RESULT = {"messageId": "m1", "provider": "primary", "queued": False}


def _send(*args, **kwargs):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as mock_req:
        result = client.messaging.send_email(*args, **kwargs)
    client.close()
    return mock_req.call_args, result


class TestSendEmail:
    def test_from_is_sent_and_reply_to_list_is_kept(self):
        (args, kwargs), result = _send(
            "jane@acme.ng", "Hi", "<p>Hi</p>",
            reply_to=["desk@app.ng", "Ops <ops@app.ng>"],
            from_="App <hello@app.ng>",
        )
        assert args == ("POST", "/api/v1/messaging/email/send")
        assert kwargs["json"] == {
            "from": "App <hello@app.ng>",
            "to": ["jane@acme.ng"],
            "subject": "Hi",
            "html": "<p>Hi</p>",
            "replyTo": ["desk@app.ng", "Ops <ops@app.ng>"],
        }
        assert result == RESULT

    def test_one_reply_to_string_and_the_optional_fields(self):
        (_, kwargs), _ = _send(
            ["a@acme.ng"], "S", "<p>h</p>", "desk@app.ng",
            from_="hello@app.ng", cc=["c@acme.ng"], bcc=["b@acme.ng"], text="h",
            caller_ref="order:1", template_id="tpl_1", variables={"name": "Ada"},
        )
        assert kwargs["json"] == {
            "from": "hello@app.ng",
            "to": ["a@acme.ng"],
            "subject": "S",
            "html": "<p>h</p>",
            "replyTo": "desk@app.ng",
            "cc": ["c@acme.ng"],
            "bcc": ["b@acme.ng"],
            "text": "h",
            "callerRef": "order:1",
            "templateId": "tpl_1",
            "variables": {"name": "Ada"},
        }

    def test_from_is_required(self):
        client = PlatformXeClient(api_key="test")
        with pytest.raises(TypeError):
            client.messaging.send_email("a@acme.ng", "S", "<p>h</p>")
        client.close()

    def test_async_sends_the_same_body(self):
        async def run():
            client = AsyncPlatformXeClient(api_key="test")
            with patch.object(client._client, "request", new=AsyncMock(return_value=_ok(RESULT))) as mock_req:
                await client.messaging.send_email(
                    "jane@acme.ng", "Hi", "<p>Hi</p>", reply_to=["desk@app.ng"], from_="hello@app.ng",
                )
            await client.close()
            return mock_req.call_args

        (args, kwargs) = asyncio.run(run())
        assert args == ("POST", "/api/v1/messaging/email/send")
        assert kwargs["json"]["from"] == "hello@app.ng"
        assert kwargs["json"]["replyTo"] == ["desk@app.ng"]
