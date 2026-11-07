# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""OCR service — identity document verification."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class OcrService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def verify_identity(self, document_url: Optional[str] = None, document_base64: Optional[str] = None, profile_name: Optional[Dict[str, str]] = None, expected_type: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if document_url:
            body["documentUrl"] = document_url
        if document_base64:
            body["documentBase64"] = document_base64
        if profile_name:
            body["profileName"] = profile_name
        if expected_type:
            body["expectedDocumentType"] = expected_type
        return self._client.post("/api/v1/ocr/verify-identity", json=body)

    def get_processor(self) -> Dict[str, Any]:
        """Get the OCR processor configuration."""
        return self._client.get("/api/v1/ocr/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the OCR processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/ocr/processor", json=body)
