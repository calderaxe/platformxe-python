# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-07  Initial: identity.verify sends supporting.nin only when asked
#   (sync and async), so existing callers' bodies are unchanged.

"""identity.verify — the optional supporting.nin a PASSPORT check carries."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx

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


RESULT = {"verified": True, "matchScore": 1, "profile": None, "provider": "prembly"}
BASE = {
    "type": "PASSPORT", "value": "A12345678",
    "matchAgainst": {"firstName": "Ada", "lastName": "Obi", "dateOfBirth": "1990-03-15"},
}


def test_verify_omits_supporting_by_default():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.verify("PASSPORT", "A12345678", "Ada", "Obi", date_of_birth="1990-03-15")
    assert req.call_args.kwargs["json"] == BASE
    client.close()


def test_verify_sends_supporting_nin():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.verify(
            "PASSPORT", "A12345678", "Ada", "Obi",
            date_of_birth="1990-03-15", supporting_nin="12345678901",
        )
    assert req.call_args.kwargs["json"] == {**BASE, "supporting": {"nin": "12345678901"}}
    client.close()


def test_async_verify_sends_supporting_nin():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*args, **kwargs):
            fake_request.kwargs = kwargs
            return _ok(RESULT)

        with patch.object(client._client, "request", side_effect=fake_request):
            await client.identity.verify(
                "PASSPORT", "A12345678", "Ada", "Obi",
                date_of_birth="1990-03-15", supporting_nin="12345678901",
            )
        await client.close()
        return fake_request.kwargs

    kwargs = asyncio.run(run())
    assert kwargs["json"] == {**BASE, "supporting": {"nin": "12345678901"}}
