# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Issues service — federated bug / support-ticket workflow."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class IssuesService:
    """Cross-app federated issue tracker.

    Issues are scoped to the calling organisation but stamped with the
    `app` that reported them, so a tenant's support team can triage
    problems regardless of which Caldera app surfaced them.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(
        self,
        app: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List federated issues for the calling organisation."""
        params: Dict[str, str] = {}
        if app is not None:
            params["app"] = app
        if status is not None:
            params["status"] = status
        result = self._client.get("/api/v1/issues", params=params)
        return result.get("issues", []) if isinstance(result, dict) else result

    def create(
        self,
        app: str,
        reporter_id: str,
        title: str,
        description: str,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a federated issue (bug / support ticket)."""
        body: Dict[str, Any] = {
            "app": app,
            "reporterId": reporter_id,
            "title": title,
            "description": description,
        }
        if priority is not None:
            body["priority"] = priority
        if tags is not None:
            body["tags"] = tags
        if metadata is not None:
            body["metadata"] = metadata
        return self._client.post("/api/v1/issues", json=body)
