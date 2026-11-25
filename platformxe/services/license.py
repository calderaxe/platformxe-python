# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-22  (1.15.0, pending) New: LicenseService.get for GET
#   /api/v1/license (scope license:read; Enterprise License). The path is
#   shared with AsyncLicenseService.
# =============================================================================

"""License service: the key's organisation's own Enterprise License (scope ``license:read``)."""

from __future__ import annotations
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient

LICENSE_PATH = "/api/v1/license"

#: Where the organisation's effective plan comes from.
LICENSE_EDITION_SOURCES = ("license", "plan", "first_party")
#: A license's state: valid, then grace (everything still runs), then lapsed; or revoked.
LICENSE_STATES = ("valid", "grace", "lapsed", "revoked")


class LicenseService:
    """The key's organisation's Enterprise License (scope ``license:read``; ``billing:read`` does not grant it).

    Read-only: a license is installed by the holder in the portal (Billing,
    License card), never through the API. The answer never carries money,
    the license text or another organisation's grants.
    """

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def get(self) -> Dict[str, Any]:
        """The organisation's license position (GET /api/v1/license).

        Returns ``{edition: {plan, source}, bypass, license}``:

        - ``edition.plan`` is the effective plan (FREE, BASIC, PRO or
          ENTERPRISE) and ``edition.source`` one of ``license``, ``plan`` or
          ``first_party``;
        - ``bypass`` is ``first_party`` or ``demo`` when the organisation
          needs no license, else None;
        - ``license`` is None when no license covers the organisation, else
          ``{licenseId, kind, issuedAt, expiresAt, graceEndsAt, state, live,
          daysLeft, renewalDue, holderName, isHolder, edition, plugins}``,
          ``plugins`` being the plugins granted to this organisation only.

        Errors: 401 UNAUTHORIZED, 403 FORBIDDEN (no ``license:read``, or a
        platform key with no organisation), 404 NOT_FOUND, 429 RATE_LIMITED,
        500 INTERNAL_ERROR.
        """
        return self._client.get(LICENSE_PATH)
