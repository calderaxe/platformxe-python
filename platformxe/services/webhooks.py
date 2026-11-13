# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-20  (pending release) Webhooks v2 (NO-DRIFT train). create() takes
#   engine_version / recipient_ref (v2 recipient endpoints); list() takes the
#   recipient_ref filter plus limit / page; new dispatch() (POST
#   /api/v1/webhooks/dispatch, scope webhooks:dispatch, idempotent per
#   endpoint by event_id, optional x-idempotency-key), deliveries() (GET
#   /api/v1/webhooks/{id}/deliveries) and redeliver() (POST
#   /api/v1/webhooks/deliveries/{deliveryId}/redeliver). The create and
#   rotate responses carry the signing ``secret`` ONCE (v1 and v2); list and
#   get never do. The builders and path templates are module-level so
#   AsyncWebhooksService sends identical requests. The path templates keep
#   their ``{id}`` / ``{deliveryId}`` placeholders (the route's own names,
#   which openapi-route-coverage.test.ts matches) and are filled by
#   webhook_path() / redeliver_path().
# 2026-10-20  (pending release) Review fix wave 2: build_page_params sends
#   limit / page only when > 0 (0 or None = the server default, as the Go
#   SDK does - the server clamps limit=0 to 1, so limit=0 used to return one
#   row); build_dispatch_body sends a None data as {} (the API refuses null);
#   docstrings carry the event-name and eventId rules, non-PAUSED targeting,
#   the FORBIDDEN / NOT_FOUND split, the null snippet on engine-1 rows and
#   the redelivery 409.
# =============================================================================

"""Webhooks service — CRUD, rotate, test, v2 recipient endpoints, dispatch, deliveries."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .vision import idempotency_headers

if TYPE_CHECKING:
    from ..client import PlatformXeClient

WEBHOOKS_PATH = "/api/v1/webhooks"
WEBHOOK_BY_ID_PATH = "/api/v1/webhooks/{id}"
WEBHOOK_ROTATE_PATH = "/api/v1/webhooks/{id}/rotate"
WEBHOOK_TEST_PATH = "/api/v1/webhooks/{id}/test"
WEBHOOK_DELIVERIES_PATH = "/api/v1/webhooks/{id}/deliveries"
WEBHOOK_DISPATCH_PATH = "/api/v1/webhooks/dispatch"
WEBHOOK_REDELIVER_PATH = "/api/v1/webhooks/deliveries/{deliveryId}/redeliver"


def webhook_path(template: str, webhook_id: str) -> str:
    """Fill the ``{id}`` placeholder of a webhook path template."""
    return template.replace("{id}", webhook_id)


def redeliver_path(delivery_id: str) -> str:
    """Fill the ``{deliveryId}`` placeholder of the redeliver path."""
    return WEBHOOK_REDELIVER_PATH.replace("{deliveryId}", delivery_id)


def build_create_body(
    name: str,
    url: str,
    events: List[str],
    engine_version: Optional[int] = None,
    recipient_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """CreateWebhookInput: {name, url, events, engineVersion?, recipientRef?}.
    engine_version 2 requires recipient_ref; recipient_ref with 1 is refused.
    Without engine_version a recipient_ref follows the server's
    PLATFORMX_WEBHOOK_ENGINE_DEFAULT environment variable (only the value
    "2" makes the endpoint v2; with anything else the create is refused) -
    pass engine_version=2. v2 events are
    "*", "prefix.*" or event names (built-ins, custom.*, dotted names such
    as booking.created; the webhook. prefix is reserved; max 200 chars)."""
    body: Dict[str, Any] = {"name": name, "url": url, "events": events}
    if engine_version is not None:
        body["engineVersion"] = engine_version
    if recipient_ref is not None:
        body["recipientRef"] = recipient_ref
    return body


def build_page_params(
    recipient_ref: Optional[str] = None,
    limit: Optional[int] = None,
    page: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """Query for the list and deliveries calls (None when nothing is set).
    ``limit`` / ``page`` are sent only when > 0: 0 or None means the server
    default (the Go SDK's rule)."""
    params: Dict[str, str] = {}
    if recipient_ref is not None:
        params["recipientRef"] = recipient_ref
    if limit is not None and limit > 0:
        params["limit"] = str(limit)
    if page is not None and page > 0:
        params["page"] = str(page)
    return params or None


def build_dispatch_body(
    recipient_ref: str, event_type: str, event_id: str, data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """DispatchWebhookInput: {recipientRef, eventType, eventId, data}.
    ``data`` is required by the API (null is refused): None is sent as {}."""
    return {
        "recipientRef": recipient_ref,
        "eventType": event_type,
        "eventId": event_id,
        "data": data if data is not None else {},
    }


class WebhooksService:
    """Webhook endpoints (scope ``webhooks:manage``) and dispatch (``webhooks:dispatch``)."""

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(
        self,
        recipient_ref: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List endpoints. Without ``recipient_ref`` only the untargeted
        endpoints; with it, that recipient's. Never carries a secret."""
        return self._client.get(WEBHOOKS_PATH, params=build_page_params(recipient_ref, limit, page))

    def create(
        self,
        name: str,
        url: str,
        events: List[str],
        engine_version: Optional[int] = None,
        recipient_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an endpoint. Returns ``{webhook, secret}``; the secret is
        shown ONCE."""
        return self._client.post(
            WEBHOOKS_PATH, json=build_create_body(name, url, events, engine_version, recipient_ref)
        )

    def get(self, webhook_id: str) -> Dict[str, Any]:
        """One endpoint. Another service's webhook is FORBIDDEN; a missing
        one NOT_FOUND."""
        return self._client.get(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id))

    def update(self, webhook_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Update name, url, events or status. engineVersion / recipientRef
        are accepted only when unchanged; a change is VALIDATION_ERROR."""
        return self._client.patch(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id), json=kwargs)

    def delete(self, webhook_id: str) -> Dict[str, Any]:
        return self._client.delete(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id))

    def rotate_secret(self, webhook_id: str) -> Dict[str, Any]:
        """Rotate the signing secret. Returns ``{webhook, secret}``; shown ONCE."""
        return self._client.post(webhook_path(WEBHOOK_ROTATE_PATH, webhook_id))

    def test(self, webhook_id: str) -> Dict[str, Any]:
        return self._client.post(webhook_path(WEBHOOK_TEST_PATH, webhook_id))

    def dispatch(
        self,
        recipient_ref: str,
        event_type: str,
        event_id: str,
        data: Optional[Dict[str, Any]],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send one event to ONE recipient's v2 endpoints that subscribe to it
        and are not PAUSED. Idempotent per endpoint by ``event_id`` (1-200
        visible ASCII characters, no spaces). Returns ``{targeted, created}``
        once the deliveries are recorded (the attempts run after the
        response). Besides the closed webhook codes the API can answer
        CONFLICT (409), RATE_LIMITED (429) and IDEMPOTENCY_UNAVAILABLE (503),
        all retryable."""
        return self._client.post(
            WEBHOOK_DISPATCH_PATH,
            json=build_dispatch_body(recipient_ref, event_type, event_id, data),
            headers=idempotency_headers(idempotency_key),
        )

    def deliveries(
        self, webhook_id: str, limit: Optional[int] = None, page: Optional[int] = None
    ) -> Dict[str, Any]:
        """Delivery log of one endpoint, newest first. Returns
        ``{items, total, page, limit}``; rows never carry the payload, and an
        engine-1 endpoint's rows carry no ``responseSnippet`` (None)."""
        return self._client.get(
            webhook_path(WEBHOOK_DELIVERIES_PATH, webhook_id), params=build_page_params(None, limit, page)
        )

    def redeliver(self, delivery_id: str) -> Dict[str, Any]:
        """Re-send one v2 delivery once (same delivery id). Returns
        ``{deliveryId, ok, status, responseTimeMs, reason}``. A delivery being
        processed or about to be retried is DELIVERY_IN_PROGRESS (409); a
        PAUSED endpoint may be redelivered to and stays PAUSED."""
        return self._client.post(redeliver_path(delivery_id))
