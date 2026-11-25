# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.14.0, pending) New: BillingService.list_invoices /
#   get_invoice for GET /api/v1/billing/invoices and /{id} (W3). The path
#   constants and builders are shared with AsyncBillingService.
# 2026-11-20  (1.14.0, pending) W3 review: invoice_path refuses an empty id,
#   "." and ".." with ValueError before anything is sent (quoting leaves dots
#   as they are, and a dot segment would reach the list route or another one).
# =============================================================================

"""Billing service: the key's organisation's own invoices (scope ``billing:read``)."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from ..client import PlatformXeClient

INVOICES_PATH = "/api/v1/billing/invoices"
INVOICE_BY_ID_PATH = "/api/v1/billing/invoices/{id}"

INVOICE_STATUSES = ("DRAFT", "PENDING", "PAID", "OVERDUE", "CANCELLED")


def invoice_path(invoice_id: str) -> str:
    """The detail path with ``invoice_id`` URL-quoted (a ``/`` cannot reach another route).

    Raises ``ValueError`` for an id that is not a non-empty string, or is
    ``.`` or ``..`` (a dot segment would resolve to another route), before
    anything is sent.
    """
    if not isinstance(invoice_id, str) or invoice_id.strip() == "" or invoice_id in (".", ".."):
        raise ValueError("billing.get_invoice needs an invoice id (not empty, '.' or '..')")
    return INVOICE_BY_ID_PATH.replace("{id}", quote(invoice_id, safe=""))


def build_invoice_list_params(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Query of the list call (None when nothing is set). ``page`` / ``limit``
    are sent only when > 0 (0 or None means the server default)."""
    params: Dict[str, str] = {}
    if page is not None and page > 0:
        params["page"] = str(page)
    if limit is not None and limit > 0:
        params["limit"] = str(limit)
    if status is not None:
        params["status"] = status
    return params or None


class BillingService:
    """Invoices of the key's own organisation (scope ``billing:read``).

    Money fields are strings in kobo (minor units): ``subtotal``, ``tax``
    (7.5% VAT), ``total``, and a line item's ``unitPrice`` / ``total``.
    ``pdfUrl`` is always None today. A platform key with no organisation is
    answered 403 FORBIDDEN.
    """

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list_invoices(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List invoices, newest first (GET /api/v1/billing/invoices).

        ``limit`` is 1..100 (default 20); ``status`` is one of DRAFT, PENDING,
        PAID, OVERDUE, CANCELLED (anything else is 400 VALIDATION_ERROR).

        Returns ``{invoices: [...], pagination: {page, limit, total,
        totalPages}}``. Each invoice is ``{id, status, currency, periodStart,
        periodEnd, subtotal, tax, total, paidAt, paidVia, pdfUrl, createdAt,
        updatedAt}``.

        Errors: 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 INTERNAL_ERROR.
        """
        return self._client.get(INVOICES_PATH, params=build_invoice_list_params(page, limit, status))

    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """One invoice and its line items (GET /api/v1/billing/invoices/{id}).

        Returns ``{invoice, lineItems}``; a line item is ``{id, service,
        description, quantity, unitPrice, total}``.

        Raises ``ValueError`` for an empty id, ``.`` or ``..`` (nothing is
        sent).

        Errors: 403 FORBIDDEN, 404 NOT_FOUND (unknown id, or another
        organisation's invoice), 500 INTERNAL_ERROR.
        """
        return self._client.get(invoice_path(invoice_id))
