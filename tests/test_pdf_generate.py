# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.14.0, pending)  Initial: pdf.generate sends POST
#   /api/v1/pdf/generate with html or templateId, data and options, and the
#   idempotency key as x-idempotency-key. Sync and async.
# 2026-11-20  (1.14.0, pending)  W3 review: 65 s, never fail-open, sent once
#   without an idempotency key (not re-sent after a transport failure or a
#   429); with a key re-sent only when no answer came back.
# =============================================================================

"""Contract tests for pdf.generate (method, path, body, header)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient
from platformxe.exceptions import PlatformXeAPIError, PlatformXeError

STORED = {
    "fileId": "f_1",
    "pdfUrl": "https://acct.blob.core.windows.net/platformx-documents/generated/x.pdf?sp=r&sig=s",
    "expiresAt": "2026-11-21T14:30:00.000Z",
    "size": 45230,
    "pages": 2,
    "generatedAt": "2026-11-20T14:30:00.000Z",
}
BASE64 = {
    "content": "JVBERi0xLjcK",
    "contentType": "application/pdf",
    "size": 9,
    "pages": 1,
    "generatedAt": "2026-11-20T14:30:00.000Z",
}


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


def _err(status, code, retry_after=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = False
    resp.headers = {"content-type": "application/json"}
    if retry_after is not None:
        resp.headers["retry-after"] = retry_after
    body = {"success": False, "error": {"code": code, "message": code}}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "ERR"
    return resp


def test_generate_html_posts_body_and_waits_longer():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(STORED)) as req:
        result = client.pdf.generate("<h1>Hi</h1>", options={"size": "A5", "urlTtlSeconds": 3600})
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/pdf/generate")
    assert kwargs["json"] == {"html": "<h1>Hi</h1>", "options": {"size": "A5", "urlTtlSeconds": 3600}}
    assert "headers" not in kwargs
    assert kwargs["timeout"] == 65.0
    assert result == STORED
    client.close()


def test_generate_template_sends_template_id_data_and_idempotency_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(BASE64)) as req:
        result = client.pdf.generate(
            template_id="tpl_abc",
            data={"customerName": "Ada", "total": 3},
            options={"returnBase64": True},
            idempotency_key="idem-1",
        )
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/pdf/generate")
    assert kwargs["json"] == {
        "templateId": "tpl_abc",
        "data": {"customerName": "Ada", "total": 3},
        "options": {"returnBase64": True},
    }
    assert kwargs["headers"] == {"x-idempotency-key": "idem-1"}
    assert result == BASE64
    client.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"html": "<p/>", "template_id": "tpl"},
        {"html": "<p/>", "data": {"a": "b"}},
    ],
)
def test_generate_refuses_html_template_misuse_without_sending(kwargs):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request") as req:
        with pytest.raises(ValueError):
            client.pdf.generate(**kwargs)
    req.assert_not_called()
    client.close()


@pytest.mark.asyncio
async def test_async_generate_matches_sync():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(STORED)) as req:
        result = await client.pdf.generate("<h1>Hi</h1>", idempotency_key="idem-2")
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/pdf/generate")
    assert kwargs["json"] == {"html": "<h1>Hi</h1>"}
    assert kwargs["headers"] == {"x-idempotency-key": "idem-2"}
    assert kwargs["timeout"] == 65.0
    assert result == STORED
    await client.close()


# ── W3 review: call options and re-send behaviour ───────────────────────────


def test_generation_call_options_rule():
    from platformxe.services.pdf import generation_call_options

    assert generation_call_options(None) == {"timeout": 65.0, "fail_open": False, "retries": 0}
    assert generation_call_options("") == {"timeout": 65.0, "fail_open": False, "retries": 0}
    assert generation_call_options("k") == {"timeout": 65.0, "fail_open": False}


def test_generate_without_key_is_sent_once_and_raises_on_a_transport_failure():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch("time.sleep"), patch.object(client._client, "request", side_effect=httpx.ConnectError("down")) as req:
        with pytest.raises(PlatformXeError):
            client.pdf.generate("<p/>")
    assert req.call_count == 1
    client.close()


def test_generate_without_key_is_not_re_sent_after_a_429():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", return_value=_err(429, "RATE_LIMITED", retry_after="30")) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.pdf.generate("<p/>")
    assert req.call_count == 1
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 30
    client.close()


def test_generate_with_key_re_sends_only_when_no_answer_came_back():
    client = PlatformXeClient(api_key="test", retries=2)
    answers = [httpx.ReadTimeout("slow"), _ok(STORED)]
    with patch("time.sleep"), patch.object(client._client, "request", side_effect=answers) as req:
        result = client.pdf.generate("<p/>", idempotency_key="idem-r")
    assert req.call_count == 2
    assert result == STORED
    for call in req.call_args_list:
        assert call.kwargs["headers"] == {"x-idempotency-key": "idem-r"}
        assert call.kwargs["timeout"] == 65.0
    client.close()


def test_generate_with_key_raises_a_409_without_re_sending():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", return_value=_err(409, "CONFLICT")) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.pdf.generate("<p/>", idempotency_key="idem-c")
    assert req.call_count == 1
    assert exc.value.code == "CONFLICT"
    client.close()


def test_generate_never_fails_open():
    client = PlatformXeClient(api_key="test", retries=0, fail_open=True)
    with patch.object(client._client, "request", side_effect=httpx.ConnectError("down")):
        with pytest.raises(PlatformXeError):
            client.pdf.generate("<p/>", idempotency_key="idem-f")
    client.close()


@pytest.mark.asyncio
async def test_async_generate_uses_the_same_call_options():
    client = AsyncPlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", side_effect=httpx.ConnectError("down")) as req:
        with pytest.raises(PlatformXeError):
            await client.pdf.generate("<p/>")
    assert req.call_count == 1
    await client.close()
