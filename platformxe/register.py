# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Standalone developer self-registration.

`POST /api/v1/register` is the unauthenticated bootstrap endpoint for new
developers. It can't sit on `PlatformXeClient` because constructing the
client requires an API key; this function gets you the key in the first
place.

Usage::

    from platformxe import register, PlatformXeClient

    r = register(name="Acme", email="dev@acme.test")
    client = PlatformXeClient(api_key=r["apiKey"])

Save ``r["apiKey"]`` immediately — it can never be retrieved again.
"""

from __future__ import annotations
from typing import Any, Dict
import httpx

from .exceptions import PlatformXeAPIError, PlatformXeError


def register(
    name: str,
    email: str,
    base_url: str = "https://platformxe.com",
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Self-register a developer tenant and receive an API key.

    Creates a FREE-tier tenant with a slug suffixed ``-dev`` and returns
    a ``pxk_dev_…`` API key that must be saved by the caller — the
    platform does not retain a way to retrieve it.

    Args:
        name: Display name. Used to derive the tenant slug.
        email: Billing + technical contact for the new tenant.
        base_url: Override the platform base URL.
        timeout: Request timeout in seconds.

    Returns:
        The full register response::

            {
                "message": "...",
                "tenant": {"id": ..., "name": ..., "slug": ..., "plan": "FREE"},
                "apiKey": "pxk_dev_...",
                "note": "...",
            }
    """
    url = f"{base_url.rstrip('/')}/api/v1/register"
    body = {"name": name, "email": email}

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=body)

    try:
        data = response.json()
    except ValueError as exc:
        raise PlatformXeError(f"Register response not valid JSON (status {response.status_code})") from exc

    if not data.get("success", False):
        error = data.get("error", {})
        raise PlatformXeAPIError(
            code=error.get("code", "UNKNOWN"),
            message=error.get("message", "Registration failed"),
            status_code=response.status_code,
        )

    return data.get("data", data)
