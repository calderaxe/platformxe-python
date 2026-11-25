# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-01  Initial: create_override sends replace only when asked (sync and
#   async), so existing callers' bodies are unchanged.

"""create_override — the replace flag (409 OVERRIDE_DENY_ACTIVE without it)."""

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


BASE = {
    "adminId": "adm_1", "path": "invoices", "action": "DELETE",
    "effect": "GRANT", "reason": "Lift after review", "expiresAt": None,
}


def test_create_override_omits_replace_by_default():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"id": "ov_1"})) as req:
        client.permissions.create_override("adm_1", "invoices", "DELETE", "GRANT", "Lift after review")
    assert req.call_args.kwargs["json"] == BASE
    client.close()


def test_create_override_sends_replace_true():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"id": "ov_1"})) as req:
        client.permissions.create_override("adm_1", "invoices", "DELETE", "GRANT", "Lift after review", replace=True)
    assert req.call_args.kwargs["json"] == {**BASE, "replace": True}
    client.close()


def test_async_create_override_sends_replace_true():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")

        async def fake_request(*args, **kwargs):
            fake_request.kwargs = kwargs
            return _ok({"id": "ov_1"})

        with patch.object(client._client, "request", side_effect=fake_request):
            await client.permissions.create_override("adm_1", "invoices", "DELETE", "GRANT", "Lift after review", replace=True)
        await client.close()
        return fake_request.kwargs

    kwargs = asyncio.run(run())
    assert kwargs["json"] == {**BASE, "replace": True}
