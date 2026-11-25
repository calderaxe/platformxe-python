# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
#
# CHANGELOG:
# 2026-11-19  v1.13.0  Docs: index() names 400 RESERVED_SEARCH_APP (the
#   reserved app "fraud"); query() never returns that app's entries.
# =============================================================================

"""Search service — federated search index + query."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class SearchService:
    """Cross-app federated search index.

    Each Caldera app upserts its own resources via `index()`; consumers
    query a single endpoint that returns matches across all apps owned
    by the calling organisation.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def index(
        self,
        app: str,
        entity_type: str,
        entity_id: str,
        title: str,
        subtitle: Optional[str] = None,
        keywords: Optional[str] = None,
        rank: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upsert a resource into the federated search index.

        Accepted asynchronously (HTTP 202) — the upsert is performed by
        the inngest worker. The app ``fraud`` (any case or padding) is
        reserved for PlatformXe's fraud desk: 400 ``RESERVED_SEARCH_APP``.
        """
        body: Dict[str, Any] = {
            "app": app,
            "entityType": entity_type,
            "entityId": entity_id,
            "title": title,
        }
        if subtitle is not None:
            body["subtitle"] = subtitle
        if keywords is not None:
            body["keywords"] = keywords
        if rank is not None:
            body["rank"] = rank
        if metadata is not None:
            body["metadata"] = metadata
        return self._client.post("/api/v1/search/index", json=body)

    def query(self, q: str, app: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query the federated search index.

        Returns at most 20 results. Queries shorter than 2 characters
        return an empty list. Entries of the reserved ``fraud`` app are never
        returned to an API key (``app="fraud"`` finds nothing).
        """
        params: Dict[str, str] = {"q": q}
        if app is not None:
            params["app"] = app
        result = self._client.get("/api/v1/search/query", params=params)
        return result.get("results", []) if isinstance(result, dict) else result
