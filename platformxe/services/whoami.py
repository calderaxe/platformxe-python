# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Whoami service — API key verification + caller identity."""

from __future__ import annotations
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class WhoamiService:
    """Verify the calling API key and surface caller identity.

    Designed for boot-time self-checks. The response includes
    grace-period and expiry warnings, plus platform-side env hints
    so consumers can detect environment drift.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def get(self) -> Dict[str, Any]:
        """Return the calling API key's identity, scopes, and metadata."""
        return self._client.get("/api/v1/whoami")
