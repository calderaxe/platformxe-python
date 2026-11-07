# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""QR service — QR code generation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


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

    def generate_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate QR codes in batch."""
        return self._client.post("/api/v1/qr/batch", json={"items": items})

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
