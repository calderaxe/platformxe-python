# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  PlatformXeAPIError gains optional ``details`` (the
#   envelope's error.details dict — e.g. details["path"] on 422
#   AI_OUTPUT_INVALID, details["metric"] on 429 AI_QUOTA_EXCEEDED) and
#   ``retry_after`` (the Retry-After header in seconds) for the AI gateway
#   and vision routes (caldera-platformxe#22). Both default to None and are
#   keyword arguments after the existing three, so existing callers and the
#   str() form are unchanged.
# =============================================================================

"""PlatformXe SDK exceptions."""

from typing import Any, Dict, Optional


class PlatformXeError(Exception):
    """Base exception for PlatformXe SDK."""
    pass


class PlatformXeAPIError(PlatformXeError):
    """API returned an error response."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.retry_after = retry_after
        super().__init__(f"[{code}] {message} (HTTP {status_code})")
