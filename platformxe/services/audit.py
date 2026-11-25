# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Audit service — federated audit log dispatch."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class AuditService:
    """Federated audit event dispatch.

    Events are accepted asynchronously (HTTP 202). The trace pipeline
    durably records them via the inngest worker.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def log(
        self,
        app: str,
        actor_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch an audit event into the federated trace pipeline."""
        body: Dict[str, Any] = {
            "app": app,
            "actorId": actor_id,
            "entityType": entity_type,
            "entityId": entity_id,
            "action": action,
        }
        if metadata is not None:
            body["metadata"] = metadata
        if occurred_at is not None:
            body["occurredAt"] = occurred_at
        return self._client.post("/api/v1/audit/log", json=body)
