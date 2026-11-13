# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Templates service — CRUD, render, send."""

from __future__ import annotations
from typing import Any, Dict, Optional, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class TemplatesService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/templates")

    def create(self, name: str, subject: str, html: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/templates", json={"name": name, "subject": subject, "html": html, **kwargs})

    def get(self, template_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/templates/{template_id}")

    def update(self, template_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/templates/{template_id}", json=kwargs)

    def delete(self, template_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/templates/{template_id}")

    def render(self, template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/templates/{template_id}/render", json={"variables": variables})

    def send(self, template_id: str, to: Union[str, List[str]], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/templates/{template_id}/send", json={"to": to, "variables": variables or {}})
