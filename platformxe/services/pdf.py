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
# =============================================================================

"""PDF service — document generation."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class PdfService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

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
            pdf_base64 (str, required — sent as pdfBase64): base64-encoded PDF, <=10MB decoded.
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
