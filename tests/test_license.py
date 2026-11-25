# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-22  (1.15.0, pending)  Initial: license.get sends GET
#   /api/v1/license and returns the view; errors keep their code. Sync and
#   async.
# 2026-11-22  (1.16.0, pending)  The version check accepts any release from
#   1.15.0 on (the AI gateway train, 1.16.0, follows this one).
# =============================================================================

"""Contract tests for license.get (method, path, answer, error codes)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

import platformxe
from platformxe import AsyncPlatformXeClient, PlatformXeAPIError, PlatformXeClient
from platformxe.services.license import LICENSE_EDITION_SOURCES, LICENSE_PATH, LICENSE_STATES

VIEW = {
    "edition": {"plan": "ENTERPRISE", "source": "license"},
    "bypass": None,
    "license": {
        "licenseId": "lic_1", "kind": "standard",
        "issuedAt": "2026-11-01T00:00:00.000Z", "expiresAt": "2027-11-01T00:00:00.000Z",
        "graceEndsAt": "2027-12-01T00:00:00.000Z", "state": "valid", "live": True,
        "daysLeft": 344, "renewalDue": False, "holderName": "Acme Holdings", "isHolder": True,
        "edition": "ENTERPRISE", "plugins": ["banking", "banking.payments"],
    },
}


def _response(status_code, body):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK" if resp.is_success else "Error"
    return resp


def _ok(data):
    return _response(200, {"success": True, "data": data})


def test_constants():
    assert LICENSE_PATH == "/api/v1/license"
    assert LICENSE_EDITION_SOURCES == ("license", "plan", "first_party")
    assert LICENSE_STATES == ("valid", "grace", "lapsed", "revoked")
    assert tuple(int(p) for p in platformxe.__version__.split(".")) >= (1, 15, 0)


def test_get_sends_get_with_no_query_or_body():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(VIEW)) as req:
        result = client.license.get()
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/license")
    assert kwargs.get("params") is None
    assert kwargs.get("json") is None
    assert result == VIEW
    client.close()


def test_get_returns_a_null_license_and_the_bypass():
    first_party = {"edition": {"plan": "ENTERPRISE", "source": "first_party"}, "bypass": "first_party", "license": None}
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(first_party)):
        assert client.license.get() == first_party
    client.close()


@pytest.mark.parametrize(
    "status,code",
    [(403, "FORBIDDEN"), (404, "NOT_FOUND"), (500, "INTERNAL_ERROR")],
)
def test_get_errors_keep_their_code(status, code):
    client = PlatformXeClient(api_key="test", fail_open=False, retries=0)
    body = {"success": False, "error": {"code": code, "message": "m"}}
    with patch.object(client._client, "request", return_value=_response(status, body)):
        with pytest.raises(PlatformXeAPIError) as exc_info:
            client.license.get()
    assert exc_info.value.code == code
    assert exc_info.value.status_code == status
    client.close()


@pytest.mark.asyncio
async def test_async_license_matches_sync():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(VIEW)) as req:
        result = await client.license.get()
    assert req.call_args.args == ("GET", "/api/v1/license")
    assert result == VIEW
    await client.close()
