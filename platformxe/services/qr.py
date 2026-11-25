# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.14.0, pending) generate_batch() matches POST /api/v1/qr/batch
#   (W3): keywords format / zip / url_ttl_seconds / idempotency_key; each
#   item is stored as a private file with a signed URL. build_batch_body,
#   QR_BATCH_PATH (and, before the W3 review, QR_BATCH_CALL_OPTIONS) are
#   shared with AsyncQrService.
# 2026-11-20  (1.14.0, pending) W3 review: the call options are
#   pdf.generation_call_options (65 s, never fail-open, sent once without an
#   idempotency key). Docstring: a sandbox key counts one write per item plus
#   the zip; zip is None also when it could not be built or stored; an
#   all-failed answer is never stored for idempotency, a partial one is (re-send
#   its failed items under a new key); 409 means the first request still runs.
# =============================================================================

"""QR service — QR code generation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .pdf import generation_call_options
from .vision import idempotency_headers

if TYPE_CHECKING:
    from ..client import PlatformXeClient

QR_BATCH_PATH = "/api/v1/qr/batch"


def build_batch_body(
    items: List[Dict[str, Any]],
    format: Optional[str] = None,
    zip: Optional[bool] = None,
    url_ttl_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Request body of POST /api/v1/qr/batch (shared by the sync and async clients)."""
    body: Dict[str, Any] = {"items": items}
    if format is not None:
        body["format"] = format
    if zip is not None:
        body["zip"] = zip
    if url_ttl_seconds is not None:
        body["urlTtlSeconds"] = url_ttl_seconds
    return body


class QrService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def generate(self, data: str, size: Optional[int] = None, format: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"data": data}
        if size:
            body["size"] = size
        if format:
            body["format"] = format
        return self._client.post("/api/v1/qr", json=body)

    def generate_batch(
        self,
        items: List[Dict[str, Any]],
        *,
        format: Optional[str] = None,
        zip: Optional[bool] = None,
        url_ttl_seconds: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and store QR codes in one call (POST /api/v1/qr/batch, 1.14.0).

        Requires the ``storage:upload`` scope; 120 requests/hr per key (route
        tier) plus the key budget. For a ``pxk_dev_`` sandbox key it counts
        one of the 50 daily ``storage:upload`` writes per item, plus one for
        the zip; a batch that does not fit is refused whole (429
        SANDBOX_QUOTA_EXCEEDED).

        Args:
            items: 1 to the processor's ``maxBatchSize`` (at most 100) dicts,
                camelCase keys as the API takes them: ``entityType`` (AGENT |
                PARTNER | PRINCIPAL | PROPERTY | BOOKING | PAYMENT),
                ``entityId``, ``accessCode``, ``baseUrl`` and ``options``
                (``size``, ``errorCorrection``, ``margin``, ``darkColor``,
                ``lightColor``, ``utmParams``).
            format: ``png`` or ``svg`` (default: the processor's).
            zip: also store one zip of every generated image.
            url_ttl_seconds: signed URL lifetime, 60..604800 (sent as
                ``urlTtlSeconds``; default 86400).
            idempotency_key: sent as ``x-idempotency-key``. Without a key
                the call is sent once (see pdf.generation_call_options). An
                answer in which nothing was generated is never stored, so a
                retry with the same key runs the batch again; a partial
                batch is stored: re-send its failed items under a NEW key.

        Returns ``{items, totalGenerated, totalFailed, zip, generatedAt}``.
        Each item is ``{index, status: 'generated', entityType, entityId,
        targetUrl, format, fileId, signedUrl, expiresAt, size}`` or
        ``{index, status: 'failed', entityType, entityId, error: {code,
        message}}`` (code VALIDATION_ERROR or STORAGE_FAILED); a failing item
        never fails the call. ``zip`` is ``{fileId, signedUrl, expiresAt,
        size, entries}``, or None when it was not asked for, when nothing was
        generated, or when the zip could not be built or stored (the images
        are stored either way).

        Errors: 400 VALIDATION_ERROR, 403 SERVICE_DISABLED, 409 CONFLICT (the
        first request with this idempotency key is still running: call again
        with the same key after about 30 s), 429 RATE_LIMITED /
        SANDBOX_QUOTA_EXCEEDED, 503 STORAGE_UNAVAILABLE, 500 INTERNAL_ERROR.
        """
        return self._client.post(
            QR_BATCH_PATH,
            json=build_batch_body(items, format, zip, url_ttl_seconds),
            headers=idempotency_headers(idempotency_key),
            **generation_call_options(idempotency_key),
        )

    def get_processor(self) -> Dict[str, Any]:
        """Get the QR processor configuration."""
        return self._client.get("/api/v1/qr/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the QR processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/qr/processor", json=body)
