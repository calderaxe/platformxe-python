# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
#
# CHANGELOG:
# 2026-11-20  v1.13.0  Created (re-review R4, N-R1): the one path filler. It
#   replaces events.py's private _fill, subscription_path's and rule_path's
#   inline quote(), and webhook_path / redeliver_path, which did not quote at
#   all. The Go SDK's fillPath is the counterpart.
# =============================================================================

"""Fill the ``{name}`` placeholders of an API path template."""

from __future__ import annotations

from urllib.parse import quote

__all__ = ["fill_path"]

#: Path segments a server or proxy may normalise away (RFC 3986 dot segments).
_DOT_SEGMENTS = frozenset({".", ".."})


def fill_path(template: str, **ids: str) -> str:
    """Return ``template`` with each ``{name}`` replaced by ``ids[name]``, URL-quoted.

    Every character outside the unreserved set is quoted (``safe=""``), so an id
    holding ``/``, ``?`` or ``#`` stays one path segment. An empty id, ``.`` or
    ``..`` raises ValueError before any request: each would address another
    route (the list route, or a parent path once normalised).

    >>> fill_path("/things/{id}", id="a/b")
    '/things/a%2Fb'
    """
    out = template
    for key, value in ids.items():
        if not isinstance(value, str) or value == "":
            raise ValueError(f"{key} is required")
        if value in _DOT_SEGMENTS:
            raise ValueError(f"{key} must not be '.' or '..'")
        out = out.replace("{" + key + "}", quote(value, safe=""))
    return out
