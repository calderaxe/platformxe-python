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
# 2026-11-16  (pending release) W2 Task 5b (NO-DRIFT): the not-accepted answers
#   (429 EMAIL_RATE_LIMITED, 503 EMAIL_NOT_ACCEPTED /
#   EMAIL_PROVIDER_UNAVAILABLE) raise once with retry_after and are never
#   re-sent; a deduplicated send is returned as queued.
# =============================================================================

"""Contract tests for messaging.send_email."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeAPIError, PlatformXeClient


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


def _error(status, code, retry_after=None, content_type="application/json"):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = False
    resp.headers = {"content-type": content_type}
    if retry_after is not None:
        resp.headers["retry-after"] = str(retry_after)
    body = {"success": False, "error": {"code": code, "message": "not accepted"}}
    resp.json.return_value = body
    resp.text = json.dumps(body) if content_type == "application/json" else "upstream unavailable"
    resp.reason_phrase = "Service Unavailable"
    return resp


class TestSendEmailNotAccepted:
    """W2 Task 5b (NO-DRIFT): the not-accepted answers carry Retry-After and are never re-sent."""

    @pytest.mark.parametrize(
        "status,code,retry_after",
        [
            (429, "EMAIL_RATE_LIMITED", 2710),
            (503, "EMAIL_NOT_ACCEPTED", 60),
            (503, "EMAIL_PROVIDER_UNAVAILABLE", 300),
        ],
    )
    def test_raised_once_with_retry_after_and_no_sleep(self, status, code, retry_after):
        client = PlatformXeClient(api_key="test", retries=2, fail_open=True)
        with patch.object(client._client, "request", return_value=_error(status, code, retry_after)) as mock_req, \
                patch("platformxe.client.time.sleep") as sleep:
            with pytest.raises(PlatformXeAPIError) as raised:
                client.messaging.send_email("jane@acme.ng", "Hi", "<p>Hi</p>", from_="hello@app.ng")
        client.close()
        assert raised.value.code == code
        assert raised.value.status_code == status
        assert raised.value.retry_after == retry_after
        # One request: the client never re-sends it (and so never sooner than Retry-After).
        assert mock_req.call_count == 1
        sleep.assert_not_called()

    def test_a_gateway_error_that_is_not_json_carries_retry_after_too(self):
        client = PlatformXeClient(api_key="test", retries=2)
        with patch.object(
            client._client, "request", return_value=_error(503, "X", 120, content_type="text/plain"),
        ) as mock_req:
            with pytest.raises(PlatformXeAPIError) as raised:
                client.messaging.send_email("jane@acme.ng", "Hi", "<p>Hi</p>", from_="hello@app.ng")
        client.close()
        assert raised.value.code == "HTTP_503"
        assert raised.value.retry_after == 120
        assert mock_req.call_count == 1

    def test_a_deduplicated_send_is_returned_as_queued(self):
        client = PlatformXeClient(api_key="test")
        answer = {"provider": "none", "queued": True, "deduplicated": True}
        with patch.object(client._client, "request", return_value=_ok(answer)):
            result = client.messaging.send_email("jane@acme.ng", "Hi", "<p>Hi</p>", from_="hello@app.ng")
        client.close()
        assert result == answer

    def test_async_raises_once_with_retry_after(self):
        async def run():
            client = AsyncPlatformXeClient(api_key="test", retries=2)
            mock_req = AsyncMock(return_value=_error(429, "EMAIL_RATE_LIMITED", 86000))
            with patch.object(client._client, "request", new=mock_req):
                with pytest.raises(PlatformXeAPIError) as raised:
                    await client.messaging.send_email("jane@acme.ng", "Hi", "<p>Hi</p>", from_="hello@app.ng")
            await client.close()
            return raised.value, mock_req.call_count

        error, calls = asyncio.run(run())
        assert error.code == "EMAIL_RATE_LIMITED"
        assert error.retry_after == 86000
        assert calls == 1
