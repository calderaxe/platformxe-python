# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-18  Initial: identity.resolve sends the required `purpose` at the top
#   level of the body (sync and async); the API answers 400 without it.
# 2026-11-18  resolve_linked defaults to False (sync and async), as the API.

"""identity.resolve: the required purpose (POST /api/v1/identity/resolve)."""

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


RESULT = {"resolved": False, "outcome": "not_found", "provider": "none"}


def test_resolve_sends_purpose_at_the_top_level():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.resolve(
            "NIN", "12345678901",
            purpose="tenant onboarding",
            resolve_linked=False,
            consent_reference="consent_abc",
        )
    body = req.call_args.kwargs["json"]
    assert body["type"] == "NIN"
    assert body["value"] == "12345678901"
    assert body["purpose"] == "tenant onboarding"
    assert body["resolveLinked"] is False
    assert body["consent"]["granted"] is True
    assert body["consent"]["reference"] == "consent_abc"
    client.close()


def test_resolve_requires_purpose():
    client = PlatformXeClient(api_key="test")
    with pytest.raises(TypeError):
        client.identity.resolve("NIN", "12345678901", consent_reference="c")  # type: ignore[call-arg]
    client.close()


def test_async_resolve_sends_purpose():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*args, **kwargs):
            fake_request.kwargs = kwargs
            return _ok(RESULT)

        with patch.object(client._client, "request", side_effect=fake_request):
            await client.identity.resolve("BVN", "22012345678", purpose="kyc", consent_reference="c")
        await client.close()
        return fake_request.kwargs["json"]

    body = asyncio.run(run())
    assert body["purpose"] == "kyc"
    assert body["consent"] == {"granted": True, "reference": "c"}
    # resolve_linked defaults to False, as the API.
    assert body["resolveLinked"] is False


def test_resolve_linked_defaults_to_false():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.resolve("NIN", "12345678901", purpose="kyc", consent_reference="c")
    assert req.call_args.kwargs["json"]["resolveLinked"] is False
    with patch.object(client._client, "request", return_value=_ok(RESULT)) as req:
        client.identity.resolve("NIN", "12345678901", resolve_linked=True, purpose="kyc", consent_reference="c")
    assert req.call_args.kwargs["json"]["resolveLinked"] is True
    client.close()


def test_async_resolve_requires_purpose():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")
        try:
            with pytest.raises(TypeError):
                await client.identity.resolve("BVN", "22012345678", consent_reference="c")  # type: ignore[call-arg]
        finally:
            await client.close()

    asyncio.run(run())
