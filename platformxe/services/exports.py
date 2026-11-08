# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Exports service — data export creation and retrieval."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class ExportsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def create_export(self, **kwargs: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/exports", json=kwargs)

    def get_export(self, export_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/exports/{export_id}")

    def get_processor(self) -> Dict[str, Any]:
        """Get the exports processor configuration."""
        return self._client.get("/api/v1/exports/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the exports processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/exports/processor", json=body)
