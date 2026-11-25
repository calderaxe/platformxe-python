# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.14.0, pending)  Initial: qr.generate_batch sends POST
#   /api/v1/qr/batch with items, format, zip and urlTtlSeconds, and the
#   idempotency key as x-idempotency-key. Sync and async.
# 2026-11-20  (1.14.0, pending)  W3 review: the generation call options
#   (65 s, never fail-open, sent once without an idempotency key).
# =============================================================================

"""Contract tests for qr.generate_batch (method, path, body, header)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient
from platformxe.exceptions import PlatformXeAPIError, PlatformXeError

ITEMS = [
    {"entityType": "PROPERTY", "entityId": "prop_001"},
    {"entityType": "PRINCIPAL", "accessCode": "A1B2", "options": {"size": "print"}},
]
ANSWER = {
    "items": [
        {
            "index": 0, "status": "generated", "entityType": "PROPERTY", "entityId": "prop_001",
            "targetUrl": "https://calderasuite.com/properties/prop_001", "format": "png",
            "fileId": "f_1", "signedUrl": "https://x?sp=r&sig=s", "expiresAt": "2026-11-21T14:30:00.000Z",
            "size": 3812,
        },
        {
            "index": 1, "status": "failed", "entityType": "PRINCIPAL", "entityId": None,
            "error": {"code": "VALIDATION_ERROR", "message": "entityId is required"},
        },
    ],
    "totalGenerated": 1,
    "totalFailed": 1,
    "zip": {"fileId": "f_z", "signedUrl": "https://z", "expiresAt": "2026-11-21T14:30:00.000Z",
            "size": 4021, "entries": 1},
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


def test_generate_batch_items_only():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(ANSWER)) as req:
        result = client.qr.generate_batch(ITEMS)
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/qr/batch")
    assert kwargs["json"] == {"items": ITEMS}
    assert "headers" not in kwargs
    assert kwargs["timeout"] == 65.0
    assert result == ANSWER
    client.close()


def test_generate_batch_keywords_and_idempotency_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(ANSWER)) as req:
        client.qr.generate_batch(ITEMS, format="svg", zip=False, url_ttl_seconds=600, idempotency_key="idem-q")
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/qr/batch")
    assert kwargs["json"] == {"items": ITEMS, "format": "svg", "zip": False, "urlTtlSeconds": 600}
    assert kwargs["headers"] == {"x-idempotency-key": "idem-q"}
    client.close()


@pytest.mark.asyncio
async def test_async_generate_batch_matches_sync():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(ANSWER)) as req:
        result = await client.qr.generate_batch(ITEMS, zip=True, idempotency_key="idem-a")
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/qr/batch")
    assert kwargs["json"] == {"items": ITEMS, "zip": True}
    assert kwargs["headers"] == {"x-idempotency-key": "idem-a"}
    assert result == ANSWER
    await client.close()


# ── W3 review: call options and re-send behaviour ───────────────────────────


def test_generate_batch_without_key_is_sent_once_and_raises_on_a_transport_failure():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch("time.sleep"), patch.object(client._client, "request", side_effect=httpx.ConnectError("down")) as req:
        with pytest.raises(PlatformXeError):
            client.qr.generate_batch(ITEMS)
    assert req.call_count == 1
    client.close()


def test_generate_batch_without_key_is_not_re_sent_after_a_429():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", return_value=_err(429, "RATE_LIMITED", retry_after="30")) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.qr.generate_batch(ITEMS)
    assert req.call_count == 1
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 30
    client.close()


def test_generate_batch_with_key_re_sends_only_when_no_answer_came_back():
    client = PlatformXeClient(api_key="test", retries=2)
    answers = [httpx.ReadTimeout("slow"), _ok(ANSWER)]
    with patch("time.sleep"), patch.object(client._client, "request", side_effect=answers) as req:
        result = client.qr.generate_batch(ITEMS, idempotency_key="idem-r")
    assert req.call_count == 2
    assert result == ANSWER
    for call in req.call_args_list:
        assert call.kwargs["headers"] == {"x-idempotency-key": "idem-r"}
        assert call.kwargs["timeout"] == 65.0
    client.close()


def test_generate_batch_with_key_raises_a_409_without_re_sending():
    client = PlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", return_value=_err(409, "CONFLICT")) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.qr.generate_batch(ITEMS, idempotency_key="idem-c")
    assert req.call_count == 1
    assert exc.value.code == "CONFLICT"
    client.close()


def test_generate_batch_never_fails_open():
    client = PlatformXeClient(api_key="test", retries=0, fail_open=True)
    with patch.object(client._client, "request", side_effect=httpx.ConnectError("down")):
        with pytest.raises(PlatformXeError):
            client.qr.generate_batch(ITEMS, idempotency_key="idem-f")
    client.close()


@pytest.mark.asyncio
async def test_async_generate_batch_uses_the_same_call_options():
    client = AsyncPlatformXeClient(api_key="test", retries=2)
    with patch.object(client._client, "request", side_effect=httpx.ConnectError("down")) as req:
        with pytest.raises(PlatformXeError):
            await client.qr.generate_batch(ITEMS)
    assert req.call_count == 1
    await client.close()
