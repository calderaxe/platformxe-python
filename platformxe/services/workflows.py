# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Workflows service — event-driven automation."""

from __future__ import annotations
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class WorkflowsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/workflows")

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/workflows", json=kwargs)

    def get(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/workflows/{workflow_id}")

    def update(self, workflow_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/workflows/{workflow_id}", json=kwargs)

    def delete(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/workflows/{workflow_id}")

    def evaluate(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.post("/api/v1/workflows/evaluate", json={"eventType": event_type, "payload": payload})

    def dry_run(self, workflow_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Dry-run a trigger against a context (no side effects)."""
        return self._client.post(f"/api/v1/workflows/{workflow_id}/dry-run", json=context)
