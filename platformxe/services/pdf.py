# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-09-21  v1.6.0  Add rasterize() — mirrors the property_flyer /
#   offer_letter **kwargs pattern above (the real request body only has
#   pdfBase64/format/page/dpi, so kwargs is sufficient; no wire-shape drift
#   risk the way documents.py's override methods had). POST
#   /api/v1/pdf/rasterize converts one page of a base64-encoded PDF to a
#   JPEG/PNG image — added alongside the Go SDK method and docs for the
#   caldera-platformxe NO-DRIFT policy (route added in MR !211). Requires
#   scope pdf:rasterize (200 req/hr/key). Response fields (imageBase64,
#   contentType, width, height, pageCount) pass through unchanged, as with
#   every other method on this client — verified against
#   src/app/api/v1/pdf/rasterize/route.ts's RasterizePdfRequest/Response.
# 2026-11-20  (1.14.0, pending) generate(): POST /api/v1/pdf/generate (W3),
#   HTML or a stored template to a PDF, stored (signed URL) or base64.
#   build_generate_body / PDF_GENERATE_PATH (and, before the W3 review,
#   PDF_GENERATE_CALL_OPTIONS) are shared with AsyncPdfService. Optional idempotency_key sends
#   x-idempotency-key (vision.idempotency_headers).
# 2026-11-20  (1.14.0, pending) W3 review: generation_call_options replaces
#   PDF_GENERATE_CALL_OPTIONS / QR_BATCH_CALL_OPTIONS (shared by pdf.generate
#   and qr.generate_batch, sync and async): 65 s timeout, never fail-open, and
#   no re-send without an idempotency key (a re-send is a second stored,
#   metered render). Docstring: 409 means the first request is still running;
#   a 408 is never stored for idempotency.
# =============================================================================

"""PDF service — document generation."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

from .vision import idempotency_headers

if TYPE_CHECKING:
    from ..client import PlatformXeClient

PDF_GENERATE_PATH = "/api/v1/pdf/generate"

# The generation routes (pdf.generate, qr.generate_batch) run up to 60 s on
# the server (a render has 25 s; 408 RENDER_TIMEOUT past that), far beyond the
# client's 10 s default.
GENERATION_TIMEOUT_SECONDS = 65.0


def generation_call_options(idempotency_key: Optional[str]) -> Dict[str, Any]:
    """Per-call options of the generation POSTs (pdf.generate, qr.generate_batch).

    - ``timeout`` 65 s (the routes run up to 60 s);
    - ``fail_open`` False: a transport failure raises PlatformXeError, never
      the ``{"_failed": True}`` placeholder (it would read as an empty result);
    - without an idempotency key, ``retries`` 0: the call is sent once. A
      re-send would render, store and meter a second time. (This client never
      re-sends after an API error, a 429 included: it raises
      PlatformXeAPIError with ``retry_after``.)
    - with a key, the client's own retries apply, and they re-send only when
      no answer came back (a network failure or the 65 s timeout). The server
      replays the stored answer; a re-send that arrives while the first
      request still runs gets 409 CONFLICT: call again with the same key
      after about 30 s.
    """
    call: Dict[str, Any] = {"timeout": GENERATION_TIMEOUT_SECONDS, "fail_open": False}
    if not idempotency_key:
        call["retries"] = 0
    return call


def build_generate_body(
    html: Optional[str] = None,
    template_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Request body of POST /api/v1/pdf/generate (shared by the sync and async clients).

    Exactly one of ``html`` / ``template_id`` is required; ``data`` only with
    ``template_id``. Raises ``ValueError`` otherwise (the API answers 400
    VALIDATION_ERROR for the same cases).
    """
    if (html is None) == (template_id is None):
        raise ValueError("pdf.generate needs exactly one of html or template_id")
    if data is not None and template_id is None:
        raise ValueError("pdf.generate: data is only sent with template_id")
    body: Dict[str, Any] = {}
    if html is not None:
        body["html"] = html
    if template_id is not None:
        body["templateId"] = template_id
    if data is not None:
        body["data"] = data
    if options is not None:
        body["options"] = options
    return body


class PdfService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def generate(
        self,
        html: Optional[str] = None,
        *,
        template_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Render HTML, or a stored template, to a PDF (POST /api/v1/pdf/generate, 1.14.0).

        Requires the ``pdf:generate`` scope; 100 requests/hr per key, plus the
        key budget.

        Args:
            html: the document (at most 2 MiB UTF-8). Exactly one of ``html``
                and ``template_id``.
            template_id: a stored template of your organisation (sent as
                ``templateId``); 404 TEMPLATE_NOT_FOUND otherwise.
            data: template variables (string, number or boolean values; at
                most 200 keys of 1 to 64 word characters, 64 KiB serialised).
                Only with ``template_id``.
            options: sent as given, camelCase keys: ``size`` (A3 | A4 | A5 |
                Letter | Legal, default A4), ``orientation`` (portrait |
                landscape), ``margins`` ({top, right, bottom, left}, e.g.
                "10mm", at most 100 mm each), ``printBackground``,
                ``headerHtml`` / ``footerHtml`` (at most 16 KiB each,
                allow-listed elements), ``filename`` (1 to 100 word characters, dots or hyphens),
                ``remoteImages`` (default true: https images fetched by the
                server), ``returnBase64`` (default false), ``urlTtlSeconds``
                (60..604800, default 86400).
            idempotency_key: sent as ``x-idempotency-key``; a retry with the
                same key answers the stored result. A base64 answer and a 408
                RENDER_TIMEOUT are never stored, so their retry renders (and
                meters) again. Without a key the call is sent once (see
                generation_call_options).

        Returns, stored mode: ``{fileId, pdfUrl, expiresAt, size, pages,
        generatedAt}`` (``pdfUrl`` is a read-only signed URL valid until
        ``expiresAt``). Base64 mode: ``{content, contentType, size, pages,
        generatedAt}`` (PDF at most 3 MiB).

        The stored file stays until deleted with DELETE
        /api/v1/storage/media/files/{fileId}, which needs ``storage:upload``
        (a key holding only ``pdf:generate`` cannot delete it).

        Errors: 400 VALIDATION_ERROR, 404 TEMPLATE_NOT_FOUND, 408
        RENDER_TIMEOUT (never stored for idempotency: retry, with the same
        key or a new one), 409 CONFLICT (the first request with this
        idempotency key is still running: call again with the same key
        after about 30 s), 413
        PAYLOAD_TOO_LARGE / OUTPUT_TOO_LARGE (over 100 pages, 20 MiB stored,
        3 MiB base64), 503 STORAGE_UNAVAILABLE / RENDERER_UNAVAILABLE, 500
        INTERNAL_ERROR.
        """
        return self._client.post(
            PDF_GENERATE_PATH,
            json=build_generate_body(html, template_id, data, options),
            headers=idempotency_headers(idempotency_key),
            **generation_call_options(idempotency_key),
        )

    def generate_offer_letter(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate an offer letter PDF."""
        return self._client.post("/api/v1/pdf/offer-letter", json=kwargs)

    def generate_property_flyer(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate a property flyer PDF."""
        return self._client.post("/api/v1/pdf/property-flyer", json=kwargs)

    def rasterize(self, **kwargs: Any) -> Dict[str, Any]:
        """Rasterize one page of a base64-encoded PDF to a JPEG/PNG image.

        Expected kwargs (mirror the request body exactly — see
        src/app/api/v1/pdf/rasterize/route.ts's RasterizePdfRequest):
            pdf_base64 (str, required — sent as pdfBase64): base64-encoded PDF. The whole
                request body is limited to 4.5 MB by the hosting platform (its
                own 413, before the route runs), so the PDF can be at most about
                3.3 MB (base64 adds a third).
            format (str, required): "jpeg" or "png".
            page (int, optional): 1-indexed page to render. Default: 1.
            dpi (int, optional): render resolution, clamped server-side to [1, 300]. Default: 150.

        Requires the pdf:rasterize scope (200 requests/hr/key). Returns
        {imageBase64, contentType, width, height, pageCount} on success.
        """
        body: Dict[str, Any] = dict(kwargs)
        if "pdf_base64" in body:
            body["pdfBase64"] = body.pop("pdf_base64")
        return self._client.post("/api/v1/pdf/rasterize", json=body)

    def get_processor(self) -> Dict[str, Any]:
        """Get the PDF processor configuration."""
        return self._client.get("/api/v1/pdf/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the PDF processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/pdf/processor", json=body)
