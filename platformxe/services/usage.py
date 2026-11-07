# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Usage service — metering and usage summaries."""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class UsageService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def summary(self, month: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {"month": month} if month else {}
        return self._client.get("/api/v1/usage/summary", params=params)
