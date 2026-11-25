# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-22  v1.16.0  (pending release) Created (AI gateway T4, NO-DRIFT).
#   AiToolsService.list for GET /api/v1/ai/tools (scope tools:platform.read,
#   the default 1,000 requests/hr/key tier). The answer mirrors AiToolList in
#   @caldera/platformxe-types 3.18.0 and passes through unchanged.
# 2026-11-23  v1.17.0  (pending release, AI gateway P5) Items also carry
#   sourceApp ("platformx" or the Caldera app that serves the tool) and
#   requiredPermission (or None); passed through unchanged.
# =============================================================================

"""Platform tools service: the tools an API key may use in the server-side tool loop."""

from __future__ import annotations
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient

#: The route. Kept as one constant so the sync and async services send the same request.
AI_TOOLS_PATH = "/api/v1/ai/tools"


class AiToolsService:
    """The platform tools an API key may use (scope ``tools:platform.read``)."""

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self) -> Dict[str, Any]:
        """The platform tools this key may use in the server-side tool loop
        (``toolsets`` on ``ai.messages`` and ``ai.complete``).

        Returns ``{items: [{name, version, description, inputSchema,
        dataClasses, toolset}], total}``. An organisation key holding
        ``tools:platform.read`` gets the ``platform.read`` tools, which read
        only its own organisation; a platform key gets none. No AI profile is
        read here, so a profile can narrow the list at call time. A key
        without the scope raises 403 ``FORBIDDEN``.
        """
        return self._client.get(AI_TOOLS_PATH)
