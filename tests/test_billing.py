# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.14.0, pending)  Initial: billing.list_invoices /
#   get_invoice send GET /api/v1/billing/invoices and /{id} (id URL-quoted).
#   Sync and async.
# 2026-11-20  (1.14.0, pending)  W3 review: get_invoice refuses an empty id,
#   "." and ".." locally (ValueError, nothing sent). Sync and async.
# =============================================================================

"""Contract tests for billing.list_invoices / get_invoice (method, path, query)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient

INVOICE = {
    "id": "inv_1", "status": "PAID", "currency": "NGN",
    "periodStart": "2026-10-01T00:00:00.000Z", "periodEnd": "2026-10-31T23:59:59.999Z",
    "subtotal": "9900000", "tax": "742500", "total": "10642500",
    "paidAt": "2026-11-02T08:15:00.000Z", "paidVia": "FLUTTERWAVE", "pdfUrl": None,
    "createdAt": "2026-11-01T00:05:00.000Z", "updatedAt": "2026-11-02T08:15:00.000Z",
}
LIST = {"invoices": [INVOICE], "pagination": {"page": 1, "limit": 20, "total": 1, "totalPages": 1}}
DETAIL = {
    "invoice": INVOICE,
    "lineItems": [{"id": "li_1", "service": "plan", "description": "Pro plan", "quantity": 1,
                   "unitPrice": "9900000", "total": "9900000"}],
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


def test_list_invoices_without_query():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(LIST)) as req:
        result = client.billing.list_invoices()
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/billing/invoices")
    assert kwargs["params"] is None
    assert result == LIST
    client.close()


def test_list_invoices_with_page_limit_status():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(LIST)) as req:
        client.billing.list_invoices(page=2, limit=50, status="PAID")
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/billing/invoices")
    assert kwargs["params"] == {"page": "2", "limit": "50", "status": "PAID"}
    client.close()


def test_get_invoice_quotes_the_id():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(DETAIL)) as req:
        result = client.billing.get_invoice("inv_1")
        client.billing.get_invoice("a/b?c")
    first, second = req.call_args_list
    assert first.args == ("GET", "/api/v1/billing/invoices/inv_1")
    assert second.args == ("GET", "/api/v1/billing/invoices/a%2Fb%3Fc")
    assert result == DETAIL
    client.close()


@pytest.mark.asyncio
async def test_async_billing_matches_sync():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(LIST)) as req:
        result = await client.billing.list_invoices(limit=10, status="DRAFT")
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/billing/invoices")
    assert kwargs["params"] == {"limit": "10", "status": "DRAFT"}
    assert result == LIST
    with patch.object(client._client, "request", return_value=_ok(DETAIL)) as req:
        detail = await client.billing.get_invoice("inv/2")
    assert req.call_args.args == ("GET", "/api/v1/billing/invoices/inv%2F2")
    assert detail == DETAIL
    await client.close()


@pytest.mark.parametrize("bad", ["", "   ", ".", "..", None, 7])
def test_get_invoice_refuses_empty_and_dot_ids_without_sending(bad):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request") as req:
        with pytest.raises(ValueError):
            client.billing.get_invoice(bad)
    req.assert_not_called()
    client.close()


@pytest.mark.asyncio
async def test_async_get_invoice_refuses_dot_ids_without_sending():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request") as req:
        for bad in ("", ".", ".."):
            with pytest.raises(ValueError):
                await client.billing.get_invoice(bad)
    req.assert_not_called()
    await client.close()


def test_get_invoice_keeps_ids_with_dots_inside():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(DETAIL)) as req:
        client.billing.get_invoice("inv.1")
        client.billing.get_invoice("...")
    first, second = req.call_args_list
    assert first.args == ("GET", "/api/v1/billing/invoices/inv.1")
    assert second.args == ("GET", "/api/v1/billing/invoices/...")
    client.close()
