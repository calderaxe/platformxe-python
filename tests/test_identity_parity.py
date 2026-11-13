# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-08  v1.11.0  Created. The async client's identity verifications,
#   DLQ and WhatsApp methods send the same requests as the sync client's
#   (shared builders); content types on liveness / face_match; check_batch
#   returns the route's list.

"""Sync / async parity for identity, WhatsApp health and check_batch."""

import asyncio
import json
from unittest.mock import MagicMock, patch

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


CALLS = [
    ("verify_bvn", ("s_1", "22222222222", "Ada", "Obi"), {"idempotency_key": "k1"}),
    ("verify_nin", ("s_1", "12345678901", "Ada", "Obi", "1990-03-15"), {"idempotency_key": "k2"}),
    ("verify_account", ("s_1", "0123456789", "058", "Ada", "Obi"), {"threshold": 80}),
    ("liveness", ("s_1",), {"image_base64": "AAAA", "image_content_type": "image/jpeg"}),
    (
        "face_match",
        ("s_1",),
        {"selfie_base64": "AAAA", "selfie_content_type": "image/png", "reference_verification_id": "iv_1"},
    ),
]


def _sync_call(name, args, kwargs, target="identity"):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"status": "verified"})) as req:
        getattr(getattr(client, target), name)(*args, **kwargs)
    client.close()
    return req.call_args


def _async_call(name, args, kwargs, target="identity"):
    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*a, **kw):
            fake_request.call = (a, kw)
            return _ok({"status": "verified"})

        with patch.object(client._client, "request", side_effect=fake_request):
            await getattr(getattr(client, target), name)(*args, **kwargs)
        await client.close()
        return fake_request.call

    return asyncio.run(run())


@pytest.mark.parametrize("name,args,kwargs", CALLS)
def test_async_identity_call_matches_sync(name, args, kwargs):
    sync = _sync_call(name, args, kwargs)
    a_args, a_kwargs = _async_call(name, args, kwargs)
    assert a_args[:2] == sync.args[:2]
    assert a_kwargs["json"] == sync.kwargs["json"]
    assert a_kwargs.get("headers") == sync.kwargs.get("headers")


def test_face_match_body_with_content_types_and_stored_reference():
    call = _sync_call("face_match", *CALLS[4][1:])
    assert call.args[:2] == ("POST", "/api/v1/identity/face-match")
    assert call.kwargs["json"] == {
        "subjectId": "s_1",
        "selfie": {"base64": "AAAA", "contentType": "image/png"},
        "reference": {"verificationId": "iv_1"},
    }


def test_verify_nin_sends_the_idempotency_key():
    call = _sync_call("verify_nin", *CALLS[1][1:])
    assert call.kwargs["headers"] == {"x-idempotency-key": "k2"}
    assert call.kwargs["json"]["matchAgainst"]["dateOfBirth"] == "1990-03-15"


def test_async_dlq_matches_sync():
    sync = PlatformXeClient(api_key="test")
    with patch.object(sync._client, "request", return_value=_ok({})) as req:
        sync.identity.dlq.list(unreplayed_only=True, kind="nin", limit=5)
    sync.close()

    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*a, **kw):
            fake_request.call = (a, kw)
            return _ok({})

        with patch.object(client._client, "request", side_effect=fake_request):
            await client.identity.dlq.list(unreplayed_only=True, kind="nin", limit=5)
            listed = fake_request.call
            await client.identity.dlq.replay("idlq_1", idempotency_key="r1")
            replayed = fake_request.call
        await client.close()
        return listed, replayed

    listed, replayed = asyncio.run(run())
    assert listed[0][:2] == req.call_args.args[:2]
    assert listed[1]["params"] == req.call_args.kwargs["params"] == {"unreplayedOnly": "true", "kind": "nin", "limit": 5}
    assert replayed[0][:2] == ("POST", "/api/v1/identity/dlq/idlq_1/replay")
    assert replayed[1]["headers"] == {"x-idempotency-key": "r1"}


@pytest.mark.parametrize(
    "name,args,path",
    [
        ("whatsapp_health", (), ("GET", "/api/v1/messaging/whatsapp/health")),
        ("build_whatsapp_link", ("+2348000000000", "hi"), ("POST", "/api/v1/messaging/whatsapp/link")),
    ],
)
def test_async_messaging_whatsapp(name, args, path):
    a_args, a_kwargs = _async_call(name, args, {}, target="messaging")
    assert a_args[:2] == path
    if name == "build_whatsapp_link":
        assert a_kwargs["json"] == {"to": "+2348000000000", "message": "hi"}


def test_check_batch_returns_the_list():
    rows = [{"adminId": "a", "path": "p", "action": "LIST", "allowed": True, "source": "role"}]
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(rows)):
        assert client.permissions.check_batch([{"adminId": "a", "path": "p", "action": "LIST"}]) == rows
    client.close()


def test_fraud_decide_sends_x_idempotency_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"verdict": "ALLOW"})) as req:
        client.fraud.decide("s_1", "USER", "login", "SESSION", idempotency_key="d1")
    assert req.call_args.kwargs["headers"] == {"x-idempotency-key": "d1"}
    client.close()
