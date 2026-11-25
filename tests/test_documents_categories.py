# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-18  Initial (1.12.0): documents.categories and documents.settings
#   (sync and async) call /api/v1/storage/fixed/categories and /settings.

"""documents.categories / documents.settings: the fixed-storage registry."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient
from platformxe.exceptions import PlatformXeAPIError
from platformxe.services.documents import UNSET, category_body


def _resp(status, body):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def _ok(data, status=200):
    return _resp(status, {"success": True, "data": data})


CATEGORY = {"id": "cat_1", "key": "LEASE", "label": "Lease", "isActive": True}


def test_list_active_only_by_default():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"categories": [CATEGORY]})) as req:
        client.documents.categories.list()
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/storage/fixed/categories")
    assert kwargs["params"] is None
    client.close()


def test_list_include_inactive():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"categories": []})) as req:
        client.documents.categories.list(include_inactive=True)
    assert req.call_args.kwargs["params"] == {"includeInactive": "true"}
    client.close()


def test_create_sends_camel_case_and_drops_none():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"category": CATEGORY}, 201)) as req:
        client.documents.categories.create(
            "lease", "Lease", retention_type="LEGAL", retention_days=2555,
            deletable_by="SUPER_ADMIN", requires_witness=True,
        )
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/storage/fixed/categories")
    assert kwargs["json"] == {
        "key": "lease", "label": "Lease", "retentionType": "LEGAL",
        "retentionDays": 2555, "deletableBy": "SUPER_ADMIN", "requiresWitness": True,
    }
    client.close()


def test_update_sends_only_passed_fields_and_none_clears():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"category": CATEGORY})) as req:
        client.documents.categories.update("LEASE", label="Tenancy", retention_days=None, is_active=False)
    args, kwargs = req.call_args
    assert args == ("PATCH", "/api/v1/storage/fixed/categories")
    assert kwargs["params"] == {"key": "LEASE"}
    assert kwargs["json"] == {"label": "Tenancy", "isActive": False, "retentionDays": None}
    client.close()


def test_deactivate_deletes_by_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"category": CATEGORY})) as req:
        client.documents.categories.deactivate("LEASE")
    args, kwargs = req.call_args
    assert args == ("DELETE", "/api/v1/storage/fixed/categories")
    assert kwargs["params"] == {"key": "LEASE"}
    client.close()


def test_a_field_of_the_wrong_type_raises_400():
    client = PlatformXeClient(api_key="test")
    refusal = _resp(400, {"success": False, "error": {
        "code": "BAD_REQUEST", "message": "retentionDays must be a non-negative integer"}})
    with patch.object(client._client, "request", return_value=refusal):
        with pytest.raises(PlatformXeAPIError) as exc:
            client.documents.categories.create("LEASE", "Lease", retention_days=-1)
    assert exc.value.status_code == 400
    client.close()


def test_category_body_never_sends_unset():
    assert category_body({"label": UNSET, "color": None}, send_none=True) == {"color": None}
    assert category_body({"label": "A", "color": None}, send_none=False) == {"label": "A"}


def test_settings_get_and_update():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"settings": {"enforceCategories": True}})) as req:
        client.documents.settings.get()
        assert req.call_args.args == ("GET", "/api/v1/storage/fixed/settings")
        client.documents.settings.update(True)
    args, kwargs = req.call_args
    assert args == ("PATCH", "/api/v1/storage/fixed/settings")
    assert kwargs["json"] == {"enforceCategories": True}
    client.close()


def test_async_categories_and_settings():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")
        calls = []

        async def fake_request(*args, **kwargs):
            calls.append((args, kwargs))
            return _ok({"category": CATEGORY})

        with patch.object(client._client, "request", side_effect=fake_request):
            await client.documents.categories.create("LEASE", "Lease", color="#1c64b8")
            await client.documents.categories.update("LEASE", description=None)
            await client.documents.categories.deactivate("LEASE")
            await client.documents.settings.update(False)
        await client.close()
        return calls

    calls = asyncio.run(run())
    assert calls[0][0] == ("POST", "/api/v1/storage/fixed/categories")
    assert calls[0][1]["json"] == {"key": "LEASE", "label": "Lease", "color": "#1c64b8"}
    assert calls[1][0] == ("PATCH", "/api/v1/storage/fixed/categories")
    assert calls[1][1]["params"] == {"key": "LEASE"}
    assert calls[1][1]["json"] == {"description": None}
    assert calls[2][0] == ("DELETE", "/api/v1/storage/fixed/categories")
    assert calls[3][1]["json"] == {"enforceCategories": False}
