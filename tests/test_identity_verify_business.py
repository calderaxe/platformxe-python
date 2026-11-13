# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG (2026-11-13, v1.12.0 pending):
# - Created. identity.verify_business (POST /api/v1/identity/verify-business,
#   scope business:verify), sync and async, with x-idempotency-key.
# =============================================================================

import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx

from platformxe import AsyncPlatformXeClient, PlatformXeClient


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = {"success": True, "data": data}
    resp.text = json.dumps({"success": True, "data": data})
    resp.is_success = True
    resp.reason_phrase = "OK"
    return resp


RESULT = {
    "status": "verified",
    "reason": None,
    "matchScore": 100,
    "registeredName": "ACME TRADING LIMITED",
    "registrationStatus": "ACTIVE",
    "registeredAt": "2015-03-01",
    "tinStatus": "MATCHED",
    "provider": "prembly",
    "verificationId": "iv_9",
}

BODY = {
    "subjectId": "prov_1",
    "country": "NG",
    "registrationType": "RC",
    "registrationNumber": "1234567",
    "expectedName": "Acme Trading Ltd",
}


def test_verify_business_sends_the_route_body():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        got = client.identity.verify_business("prov_1", "RC", "1234567", "Acme Trading Ltd")
    assert "/api/v1/identity/verify-business" in str(req.call_args)
    assert req.call_args.kwargs["json"] == BODY
    assert got == RESULT
    client.close()


def test_verify_business_sends_tin_threshold_and_idempotency_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.verify_business(
            "prov_1", "BN", "3456789", "Acme Trading Ltd",
            tin="12345678-0001", threshold=80, idempotency_key="kyb-1",
        )
    assert req.call_args.kwargs["json"] == {
        **BODY, "registrationType": "BN", "registrationNumber": "3456789",
        "tin": "12345678-0001", "threshold": 80,
    }
    assert req.call_args.kwargs["headers"]["x-idempotency-key"] == "kyb-1"
    client.close()


def test_async_verify_business_sends_the_route_body():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*args, **kwargs):
            fake_request.kwargs = kwargs
            return _ok(RESULT)

        with patch.object(client._client, "request", side_effect=fake_request):
            got = await client.identity.verify_business("prov_1", "RC", "1234567", "Acme Trading Ltd", tin="123456780001")
        await client.close()
        return fake_request.kwargs, got

    kwargs, got = asyncio.run(run())
    assert kwargs["json"] == {**BODY, "tin": "123456780001"}
    assert got == RESULT
