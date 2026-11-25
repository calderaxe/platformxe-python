# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Domains service — sending domain management."""

from __future__ import annotations
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class DomainsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/domains")

    def add(self, domain: str) -> Dict[str, Any]:
        return self._client.post("/api/v1/domains", json={"domain": domain})

    def get(self, domain_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/domains/{domain_id}")

    def delete(self, domain_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/domains/{domain_id}")

    def verify(self, domain_id: str) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/domains/{domain_id}/verify")
