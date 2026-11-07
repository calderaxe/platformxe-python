# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Events service — ingest, log, subscriptions, replay, plus the
tenant custom events surface accessible at ``client.events.custom``."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class CustomEventsService:
    """Tenant-defined events — register, emit, list, archive, dry-run, health.

    Available at ``client.events.custom``. Free-tier tenants can call
    :meth:`emit` against the platform-provided ``platformxe.generic``
    catch-all event without any additional configuration.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    # -- Register / list / archive ------------------------------------------------

    def register(
        self,
        namespace: str,
        name: str,
        version: str,
        payload_schema: Dict[str, Any],
        *,
        status: Optional[str] = None,
        description: Optional[str] = None,
        payload_example: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new custom event (or a new version of an existing one)."""
        body: Dict[str, Any] = {
            "namespace": namespace,
            "name": name,
            "version": version,
            "payloadSchema": payload_schema,
        }
        if status is not None:
            body["status"] = status
        if description is not None:
            body["description"] = description
        if payload_example is not None:
            body["payloadExample"] = payload_example
        headers: Optional[Dict[str, str]] = None
        if idempotency_key is not None:
            headers = {"Idempotency-Key": idempotency_key}
        return self._client.post("/api/v1/events/custom", json=body, headers=headers)

    def list(
        self, namespace: Optional[str] = None, status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all registrations belonging to the caller's organisation."""
        params: Dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        if status:
            params["status"] = status
        return self._client.get("/api/v1/events/custom", params=params)

    def get(self, registration_id: str) -> Dict[str, Any]:
        """Fetch the full row for a single registration."""
        return self._client.get(f"/api/v1/events/custom/{registration_id}")

    def archive(self, registration_id: str) -> Dict[str, Any]:
        """Soft-delete a registration. The platform-provided generic event
        cannot be archived by tenants."""
        return self._client.delete(f"/api/v1/events/custom/{registration_id}")

    # -- Emit / dry-run / health -------------------------------------------------

    def emit(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        version: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Emit a payload against a registered event. Returns ``status: queued``
        on success — delivery to subscribers is asynchronous.

        Free-tier tenants may emit ``platformxe.generic`` without prior
        registration; everything else requires Basic+.
        """
        body: Dict[str, Any] = {"name": name, "payload": payload}
        if version is not None:
            body["version"] = version
        if idempotency_key is not None:
            body["idempotencyKey"] = idempotency_key
        headers: Optional[Dict[str, str]] = None
        if idempotency_key is not None:
            headers = {"Idempotency-Key": idempotency_key}
        return self._client.post("/api/v1/events/custom/emit", json=body, headers=headers)

    def dry_run(
        self,
        namespace: str,
        name: str,
        version: str,
        payload_schema: Dict[str, Any],
        *,
        description: Optional[str] = None,
        payload_example: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate a registration template without persisting. Mirrors the
        first stage of :meth:`register` — useful from ``terraform plan``
        previews and SDK type-generation workflows."""
        body: Dict[str, Any] = {
            "namespace": namespace,
            "name": name,
            "version": version,
            "payloadSchema": payload_schema,
        }
        if description is not None:
            body["description"] = description
        if payload_example is not None:
            body["payloadExample"] = payload_example
        return self._client.post("/api/v1/events/custom/dry-run", json=body)

    def health(self) -> Dict[str, Any]:
        """Usage diagnostics for the caller's organisation: plan, registration
        count, monthly emit count vs caps, recent failed emits."""
        return self._client.get("/api/v1/events/custom/health")

    # -- Subscribe (Phase 9B.4) --------------------------------------------------

    def subscribe(
        self,
        name: str,
        webhook_url: str,
        *,
        version: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Subscribe a webhook to a registered custom event.

        :param name: ``<namespace>.<name>`` (e.g. ``"lettings.property.favorited"``).
        :param webhook_url: HTTPS URL the platform will POST events to.
        :param version: exact semver to subscribe to, ``"*"`` for all versions, or
                        omitted for "all versions" (same as ``"*"``).
        :param display_name: optional friendly label for the subscription.

        Returns a payload containing ``subscriptionId``, ``canonicalName``,
        ``secret`` (returned ONCE — used to verify ``X-Event-Signature`` on
        deliveries), and ``webhookUrl``.

        The platform resolves the canonical bus name from the calling org's
        api-key — tenants don't need to construct ``TENANT_CUSTOM:org:…@v``
        strings by hand.
        """
        body: Dict[str, Any] = {"name": name, "webhookUrl": webhook_url}
        if version is not None:
            body["version"] = version
        if display_name is not None:
            body["displayName"] = display_name
        return self._client.post("/api/v1/events/custom/subscribe", json=body)

    @property
    def marketplace(self) -> "MarketplaceService":
        """Lazy-init marketplace sub-resource. Mirrors TS SDK's
        ``client.events.custom.marketplace``.
        """
        if not hasattr(self, "_marketplace"):
            self._marketplace = MarketplaceService(self._client)
        return self._marketplace

    @property
    def federation(self) -> "EventFederationService":
        """Lazy-init federation sub-resource. Mirrors TS SDK's
        ``client.events.custom.federation``. ENTERPRISE-only on both
        sides — owners and members must be on the Enterprise plan.
        """
        if not hasattr(self, "_federation"):
            self._federation = EventFederationService(self._client)
        return self._federation


class MarketplaceService:
    """Tenant Custom Events Marketplace (Phase 9C). PRO+ tenants publish a
    registered event so other PRO+ tenants can fork the schema into their
    own org. Forks copy the schema verbatim — independent of source
    thereafter.

    Available at ``client.events.custom.marketplace``.
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def publish(
        self,
        registration_id: str,
        title: str,
        *,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Publish a registered event to the marketplace. PRO+ only."""
        body: Dict[str, Any] = {"registrationId": registration_id, "title": title}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        return self._client.post("/api/v1/events/custom/marketplace/publish", json=body)

    def list(
        self,
        *,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Browse the marketplace. Open to all plans."""
        params: Dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return self._client.get("/api/v1/events/custom/marketplace", params=params)

    def get(self, listing_id: str) -> Dict[str, Any]:
        """Fetch full detail (incl. payloadSchema) for a listing."""
        return self._client.get(f"/api/v1/events/custom/marketplace/{listing_id}")

    def unpublish(self, listing_id: str) -> Dict[str, Any]:
        """Unpublish a listing the caller's org owns. Existing forks unaffected."""
        return self._client.delete(f"/api/v1/events/custom/marketplace/{listing_id}")

    def republish(self, listing_id: str) -> Dict[str, Any]:
        """Re-activate a previously unpublished listing the caller's org owns."""
        return self._client.post(f"/api/v1/events/custom/marketplace/{listing_id}/republish")

    def fork(
        self,
        listing_id: str,
        namespace: str,
        name: str,
        *,
        version: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fork a listing into the caller's org under a chosen destination
        ``namespace``/``name``. Schema is copied at fork-time — the fork is
        an independent registration thereafter. PRO+ only.

        :param version: defaults to ``"1.0.0"`` if omitted (initial version).
        :param status: defaults to ``"draft"`` — fork doesn't auto-publish.
        """
        body: Dict[str, Any] = {"namespace": namespace, "name": name}
        if version is not None:
            body["version"] = version
        if description is not None:
            body["description"] = description
        if status is not None:
            body["status"] = status
        return self._client.post(
            f"/api/v1/events/custom/marketplace/{listing_id}/fork", json=body
        )


class EventFederationService:
    """Tenant Custom Events Federation Push (Phase 9D, ENTERPRISE-only).

    Owner organisations create federation groups, invite peer Enterprise
    orgs, and declare per-version event-pushes. When the owner emits a
    pushed event, every accepted member receives the relay on their own
    bus channel. The schema is snapshotted at push-declaration time — a
    member's view is stable even if the owner archives the registration.

    Available at ``client.events.custom.federation``.

    Naming distinguishes this *Custom Event Federation* from the
    ``client.permissions.federation`` *Permission Federation* surface
    (cross-app admin permissions sync, v1.x.x).
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def create_group(
        self,
        name: str,
        *,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new federation group owned by the calling org."""
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        return self._client.post("/api/v1/events/custom/federation/groups", json=body)

    def list_groups(
        self,
        *,
        include_archived: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """List groups the caller owns or is a member of."""
        params: Dict[str, str] = {}
        if include_archived is not None:
            params["includeArchived"] = "true" if include_archived else "false"
        return self._client.get("/api/v1/events/custom/federation/groups", params=params)

    def get_group(self, group_id: str) -> Dict[str, Any]:
        """Fetch full detail for a group (members + active pushes)."""
        return self._client.get(f"/api/v1/events/custom/federation/groups/{group_id}")

    def archive_group(self, group_id: str) -> Dict[str, Any]:
        """Archive a group the caller's org owns. Stops fan-out;
        preserves history."""
        return self._client.delete(
            f"/api/v1/events/custom/federation/groups/{group_id}"
        )

    def invite(self, group_id: str, member_organization_id: str) -> Dict[str, Any]:
        """Invite a peer ENTERPRISE org into the group. Owner-only."""
        return self._client.post(
            f"/api/v1/events/custom/federation/groups/{group_id}/invite",
            json={"memberOrganizationId": member_organization_id},
        )

    def accept(self, group_id: str) -> Dict[str, Any]:
        """Accept a pending invitation. Caller must be the invited org."""
        return self._client.post(
            f"/api/v1/events/custom/federation/groups/{group_id}/accept"
        )

    def leave(self, group_id: str) -> Dict[str, Any]:
        """Voluntarily leave a group the caller is a member of."""
        return self._client.post(
            f"/api/v1/events/custom/federation/groups/{group_id}/leave"
        )

    def declare_push(self, group_id: str, registration_id: str) -> Dict[str, Any]:
        """Declare a per-version push of one of the owner's
        registrations. Owner-only."""
        return self._client.post(
            f"/api/v1/events/custom/federation/groups/{group_id}/pushes",
            json={"registrationId": registration_id},
        )

    def list_pushes(
        self,
        group_id: str,
        *,
        include_inactive: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """List pushes declared in a group."""
        params: Dict[str, str] = {}
        if include_inactive is not None:
            params["includeInactive"] = "true" if include_inactive else "false"
        return self._client.get(
            f"/api/v1/events/custom/federation/groups/{group_id}/pushes",
            params=params,
        )

    def undeclare_push(self, push_id: str) -> Dict[str, Any]:
        """Stop pushing a previously-declared per-version push. Owner-only."""
        return self._client.delete(
            f"/api/v1/events/custom/federation/pushes/{push_id}"
        )

    # ─── Pattern 3 — external webhook peers (added in 1.5.0) ──────────

    def add_external_peer(
        self,
        group_id: str,
        *,
        label: str,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Add an external (non-tenant) peer to a federation group, addressed
        by webhook URL. Returns ``{"peer": {...}, "secret": "whsec_..."}``.

        The HMAC ``secret`` is shown ONCE — store it immediately and use it
        to verify the ``X-Platformxe-Signature`` header on inbound webhooks.
        Owner-only. ENTERPRISE-plan group required.
        """
        body: Dict[str, Any] = {"label": label, "webhookUrl": webhook_url}
        if headers is not None:
            body["headers"] = headers
        return self._client.post(
            f"/api/v1/events/custom/federation/groups/{group_id}/external-peers",
            json=body,
        )

    def remove_external_peer(self, member_id: str) -> Dict[str, Any]:
        """Archive an external webhook peer (sets status='removed'). The
        encrypted secret is wiped from storage as part of the soft-delete.
        Owner-only.
        """
        return self._client.delete(
            f"/api/v1/events/custom/federation/external-peers/{member_id}"
        )


class EventsService:
    def __init__(self, client: "PlatformXeClient"):
        self._client = client
        self.custom = CustomEventsService(client)

    def ingest(self, event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.post("/api/v1/events", json={
            "eventType": event_type, "entityType": entity_type,
            "entityId": entity_id, "payload": payload,
        })

    def log(self, event_type: Optional[str] = None, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if event_type:
            params["eventType"] = event_type
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return self._client.get("/api/v1/event-log", params=params)

    def list_subscriptions(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/event-subscriptions")

    def create_subscription(self, event_types: List[str], webhook_url: str, secret: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"eventTypes": event_types, "webhookUrl": webhook_url}
        if secret:
            body["secret"] = secret
        return self._client.post("/api/v1/event-subscriptions", json=body)

    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/event-subscriptions/{subscription_id}")

    def update_subscription(self, subscription_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/event-subscriptions/{subscription_id}", json=kwargs)

    def delete_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/event-subscriptions/{subscription_id}")

    def replay(self, subscription_id: str, from_date: str, to_date: str) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/event-subscriptions/{subscription_id}/replay", json={"from": from_date, "to": to_date})
