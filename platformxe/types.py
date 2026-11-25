# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Type definitions for PlatformXe SDK."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class APIResponse:
    """Standard API envelope returned by PlatformXe."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None


@dataclass
class PaginationMeta:
    """Pagination metadata included in list responses."""
    page: int = 1
    limit: int = 20
    total: int = 0
