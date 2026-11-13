# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

#
# CHANGELOG:
# 2026-09-15  v1.6.0  AsyncDocumentsService folder/override methods brought
#   in line with the sync DocumentsService: create_folder(owner_type,
#   owner_id), get_folder_by_owner(), deprecated list_folders(), explicit
#   request_override/process_override parameters with the legacy camelCase
#   **kwargs form still accepted (DeprecationWarning). The async copies still
#   sent the broken pre-1.6.0 shapes; they now share documents.py's builders.
# 2026-09-21  v1.6.0  Add AsyncPdfService.rasterize() to match the new sync
#   PdfService.rasterize() (pdf.py) — POST /api/v1/pdf/rasterize. Same
#   pdf_base64->pdfBase64 kwarg mapping so the async and sync clients cannot
#   drift on wire shape. See pdf.py's CHANGELOG for the full rationale.
# 2026-10-08  v1.7.0  Add AsyncAiService (complete / extract / profile /
#   usage) and AsyncVisionService (analyze_room) for the AI gateway and
#   vision routes (caldera-platformxe#22). They reuse ai.py's / vision.py's
#   body, query and header builders, so the async and sync clients cannot
#   drift on wire shape.
# 2026-10-08  v1.7.0  (pending release, xadmin#29) AsyncAiService.complete
#   takes tools / tool_choice; add AsyncKnowledgeService (upsert_document /
#   delete_document / list_documents / search) reusing knowledge.py's
#   builders.
# 2026-10-20  (pending release) Webhooks v2: AsyncWebhooksService gains
#   dispatch / deliveries / redeliver and recipient_ref / engine_version,
#   reusing webhooks.py's builders and path templates.
# 2026-10-20  (pending release) Webhooks v2 review fix wave 2:
#   AsyncWebhooksService.dispatch accepts data=None (sent as {}, through the
#   shared build_dispatch_body); limit / page of 0 are no longer sent
#   (build_page_params), matching the sync client and the Go SDK.
# 2026-10-09  (pending release) Final review: the async AI, vision and
#   knowledge calls pass the same per-call options as the sync ones
#   (MODEL_CALL_OPTIONS, analyze_room_call_options, UPSERT / SEARCH_CALL_OPTIONS).
# 2026-11-01  (pending release) AsyncPermissionsService.create_override gains
#   replace= (a GRANT over a live DENY is refused 409 OVERRIDE_DENY_ACTIVE
#   without it); resolve() documents deniedCapabilities, which a local
#   evaluator must apply. Same as the sync PermissionsService.
# 2026-11-13  v1.12.0  verify_business (async twin, shared body builder).
# 2026-11-08  v1.11.0  NO-DRIFT with the sync client and the TS / Go SDKs:
#   AsyncIdentityService gains providers_health, verify_bvn, verify_nin,
#   verify_account, liveness, face_match and dlq (AsyncIdentityDlqService),
#   built by identity.py's shared helpers; AsyncMessagingService gains
#   build_whatsapp_link and whatsapp_health. check_batch is typed as the
#   list the route answers (it always returned it).
# 2026-11-12  (pending release) Task 4 fix round 4: AsyncWorkflowsService.evaluate
#   sends entityData (payload= is a deprecated alias) and the optional fields,
#   through workflows.py's evaluate_request_body.
# =============================================================================

"""Async service implementations for AsyncPlatformXeClient."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union, TYPE_CHECKING

from .ai import MODEL_CALL_OPTIONS, build_complete_body, build_extract_body, build_usage_params
from .identity import (
    dlq_list_params,
    face_match_body,
    idempotency_headers,
    liveness_body,
    verify_account_body,
    verify_business_body,
    verify_bvn_body,
    verify_nin_body,
)
from .knowledge import (
    SEARCH_CALL_OPTIONS,
    UPSERT_CALL_OPTIONS,
    build_document_ref_params,
    build_list_params,
    build_search_body,
    build_upsert_document_body,
)
from .documents import (
    build_process_override_body,
    build_request_override_body,
    check_deprecated_list_folders,
    folder_owner_params,
)
from .vision import analyze_room_call_options, build_analyze_room_body, idempotency_headers
from .workflows import evaluate_request_body
from .webhooks import (
    WEBHOOKS_PATH, WEBHOOK_BY_ID_PATH, WEBHOOK_ROTATE_PATH, WEBHOOK_TEST_PATH,
    WEBHOOK_DELIVERIES_PATH, WEBHOOK_DISPATCH_PATH, build_create_body,
    build_dispatch_body, build_page_params, redeliver_path, webhook_path,
)

if TYPE_CHECKING:
    from ..client import AsyncPlatformXeClient


class AsyncPermissionsService:
    """Async permissions service — RBAC, ABAC, ReBAC, Federation."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def check(self, admin_id: str, path: str, action: str, resource: Optional[Dict] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/check", json={
            "adminId": admin_id, "path": path, "action": action,
            "resource": resource, "context": context,
        })

    async def check_batch(self, checks: List[Dict]) -> List[Dict[str, Any]]:
        """The results in request order: the route answers a bare list."""
        return await self._client.post("/api/v1/permissions/check-batch", json={"checks": checks})  # type: ignore[return-value]

    async def resolve(self, admin_id: str) -> Dict[str, Any]:
        """Resolved capabilities for an admin.

        The result carries ``deniedCapabilities`` (``path:action`` of every live DENY override). A local
        evaluator MUST refuse any request one covers (same action, same path or a sub-path,
        case-insensitive, trailing '/' ignored) before using ``capabilities``, which may still hold role
        wildcards a deny overrides.
        """
        return await self._client.get(f"/api/v1/permissions/resolve/{admin_id}")

    async def list_roles(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/permissions/roles")

    async def create_role(self, name: str, description: Optional[str] = None, model: str = "SIMPLE") -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/roles", json={
            "name": name, "description": description, "model": model,
        })

    async def get_role(self, role_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/roles/{role_id}")

    async def update_role(self, role_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return await self._client.patch(f"/api/v1/permissions/roles/{role_id}", json=body)

    async def delete_role(self, role_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/permissions/roles/{role_id}")

    async def get_role_capabilities(self, role_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/roles/{role_id}/capabilities")

    async def set_role_capabilities(self, role_id: str, capabilities: List[str]) -> Dict[str, Any]:
        return await self._client.put(f"/api/v1/permissions/roles/{role_id}/capabilities", json={"capabilities": capabilities})

    async def get_role_module_permissions(self, role_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/roles/{role_id}/modules")

    async def set_role_module_permissions(self, role_id: str, modules: List[Dict]) -> Dict[str, Any]:
        return await self._client.put(f"/api/v1/permissions/roles/{role_id}/modules", json={"modules": modules})

    async def list_overrides(self, admin_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/overrides/{admin_id}")

    async def create_override(self, admin_id: str, path: str, action: str, effect: str, reason: str, expires_at: Optional[str] = None, replace: bool = False) -> Dict[str, Any]:
        """Create or replace the one override for (admin_id, path, action).

        The API answers 201 on create and 200 when it replaced the existing override. A GRANT over a
        live DENY is refused (409 OVERRIDE_DENY_ACTIVE) unless ``replace=True``; a DENY over a live DENY
        keeps the later expiry (no expiry wins).
        """
        body: Dict[str, Any] = {
            "adminId": admin_id, "path": path, "action": action,
            "effect": effect, "reason": reason, "expiresAt": expires_at,
        }
        if replace:
            body["replace"] = True
        return await self._client.post("/api/v1/permissions/overrides", json=body)

    async def delete_override(self, override_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/permissions/overrides/remove/{override_id}")

    async def list_policies(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/permissions/policies")

    async def create_policy(self, path: str, action: str, condition: Dict, effect: str, priority: int = 0, description: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/policies", json={
            "path": path, "action": action, "condition": condition,
            "effect": effect, "priority": priority, "description": description,
        })

    async def update_policy(self, policy_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/permissions/policies/{policy_id}", json=kwargs)

    async def delete_policy(self, policy_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/permissions/policies/{policy_id}")

    async def list_relationships(self, **params: Any) -> Dict[str, Any]:
        return await self._client.get("/api/v1/permissions/relationships", params=params)

    async def update_relationships(self, operations: List[Dict]) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/relationships", json=operations)

    async def register_module(self, id: str, app: str, name: str, paths: List[str], description: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/modules", json={
            "id": id, "app": app, "name": name, "paths": paths, "description": description,
        })

    async def list_modules(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/permissions/modules")

    async def get_audit_logs(self, admin_id: Optional[str] = None, path: Optional[str] = None, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if admin_id:
            params["adminId"] = admin_id
        if path:
            params["path"] = path
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return await self._client.get("/api/v1/permissions/audit", params=params)

    async def list_change_logs(self, entity_type: Optional[str] = None, entity_id: Optional[str] = None, changed_by: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if entity_type:
            params["entityType"] = entity_type
        if entity_id:
            params["entityId"] = entity_id
        if changed_by:
            params["changedBy"] = changed_by
        if limit:
            params["limit"] = str(limit)
        if offset:
            params["offset"] = str(offset)
        return await self._client.get("/api/v1/permissions/audit/changes", params=params)

    async def export_audit(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._client.get("/api/v1/permissions/audit/export", params=params)

    async def shadow_check(self, admin_id: str, path: str, action: str, local_decision: bool, context: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/shadow-check", json={
            "adminId": admin_id, "path": path, "action": action,
            "localDecision": local_decision, "context": context,
        })

    # Federation

    async def create_federation_group(self, name: str) -> Dict[str, Any]:
        return await self._client.post("/api/v1/permissions/federation/groups", json={"name": name})

    async def list_federation_groups(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/permissions/federation/groups")

    async def get_federation_group(self, group_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/federation/groups/{group_id}")

    async def delete_federation_group(self, group_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/permissions/federation/groups/{group_id}")

    async def add_federation_member(self, group_id: str, organization_id: str, prefix: str) -> Dict[str, Any]:
        """Invite an organization into the group (owner only). Status: INVITED."""
        return await self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/members", json={
            "organizationId": organization_id, "prefix": prefix,
        })

    async def accept_federation_membership(self, group_id: str) -> Dict[str, Any]:
        """Accept this organization's invitation (call with the invited org's key)."""
        return await self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/members/accept", json={})

    async def remove_federation_member(self, group_id: str, organization_id: str) -> Dict[str, Any]:
        """Remove a membership; pass your own org id to leave or decline."""
        return await self._client.delete(f"/api/v1/permissions/federation/groups/{group_id}/members?organizationId={organization_id}")

    async def pull_federation_modules(self, group_id: str, target_org_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/pull", json={"targetOrgId": target_org_id})

    async def push_federation_permissions(self, group_id: str, admin_ids: List[str], target_org_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/push", json={
            "adminIds": admin_ids, "targetOrgId": target_org_id,
        })

    async def get_federation_status(self, group_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/permissions/federation/groups/{group_id}/status")


class AsyncIdentityDlqService:
    """Async twin of IdentityDlqService (identity verification dead-letter queue)."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list(
        self,
        unreplayed_only: bool = False,
        subject_id: Optional[str] = None,
        kind: Optional[str] = None,
        country_code: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return await self._client.get(
            "/api/v1/identity/dlq",
            params=dlq_list_params(unreplayed_only, subject_id, kind, country_code, limit, offset),
        )

    async def stats(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/identity/dlq/stats")

    async def get(self, dlq_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/identity/dlq/{dlq_id}")

    async def replay(self, dlq_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post(
            f"/api/v1/identity/dlq/{dlq_id}/replay",
            json={},
            headers=idempotency_headers(idempotency_key),
        )


class AsyncIdentityService:
    """Async identity service — resolve, verify, lookup, KYC, biometrics, DLQ."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client
        self.dlq = AsyncIdentityDlqService(client)

    async def resolve(self, type: str, value: str, resolve_linked: bool = True, consent_reference: str = "", consent_obtained_at: str = "") -> Dict[str, Any]:
        return await self._client.post("/api/v1/identity/resolve", json={
            "type": type, "value": value, "resolveLinked": resolve_linked,
            "consent": {"granted": True, "reference": consent_reference, "obtainedAt": consent_obtained_at},
        })

    async def verify(
        self,
        type: str,
        value: str,
        first_name: str,
        last_name: str,
        date_of_birth: Optional[str] = None,
        supporting_nin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async twin of IdentityService.verify (``supporting_nin``: PASSPORT only)."""
        body: Dict[str, Any] = {
            "type": type, "value": value,
            "matchAgainst": {"firstName": first_name, "lastName": last_name},
        }
        if date_of_birth:
            body["matchAgainst"]["dateOfBirth"] = date_of_birth
        if supporting_nin is not None:
            body["supporting"] = {"nin": supporting_nin}
        return await self._client.post("/api/v1/identity/verify", json=body)

    async def lookup(self, type: str, value: str, purpose: str, consent_reference: str) -> Dict[str, Any]:
        """Raw registry lookup (v1.10.0): purpose and consent reference required."""
        return await self._client.get(
            "/api/v1/identity/lookup",
            params={"type": type, "value": value, "purpose": purpose, "consentReference": consent_reference},
        )

    async def providers(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/identity/providers")

    async def providers_health(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/identity/providers/health")

    async def verify_bvn(
        self,
        subject_id: str,
        bvn: str,
        first_name: str,
        last_name: str,
        date_of_birth: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(
            "/api/v1/identity/verify-bvn",
            json=verify_bvn_body(subject_id, bvn, first_name, last_name, date_of_birth),
            headers=idempotency_headers(idempotency_key),
        )

    async def verify_nin(
        self,
        subject_id: str,
        nin: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async twin of IdentityService.verify_nin (date_of_birth required)."""
        return await self._client.post(
            "/api/v1/identity/verify-nin",
            json=verify_nin_body(subject_id, nin, first_name, last_name, date_of_birth),
            headers=idempotency_headers(idempotency_key),
        )

    async def verify_account(
        self,
        subject_id: str,
        account_number: str,
        bank_code: str,
        first_name: str,
        last_name: str,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(
            "/api/v1/identity/verify-account",
            json=verify_account_body(subject_id, account_number, bank_code, first_name, last_name, threshold),
            headers=idempotency_headers(idempotency_key),
        )

    async def verify_business(
        self,
        subject_id: str,
        registration_type: str,
        registration_number: str,
        expected_name: str,
        tin: Optional[str] = None,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async twin of IdentityService.verify_business (business:verify)."""
        return await self._client.post(
            "/api/v1/identity/verify-business",
            json=verify_business_body(
                subject_id, registration_type, registration_number, expected_name, tin, threshold,
            ),
            headers=idempotency_headers(idempotency_key),
        )

    async def liveness(
        self,
        subject_id: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        image_content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(
            "/api/v1/identity/liveness",
            json=liveness_body(subject_id, image_url, image_base64, image_content_type),
            headers=idempotency_headers(idempotency_key),
        )

    async def face_match(
        self,
        subject_id: str,
        selfie_url: Optional[str] = None,
        selfie_base64: Optional[str] = None,
        reference_url: Optional[str] = None,
        reference_base64: Optional[str] = None,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        reference_verification_id: Optional[str] = None,
        selfie_content_type: Optional[str] = None,
        reference_content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async twin of IdentityService.face_match (reference_verification_id
        compares with a verified NIN check's registry photo)."""
        return await self._client.post(
            "/api/v1/identity/face-match",
            json=face_match_body(
                subject_id, selfie_url, selfie_base64, reference_url, reference_base64,
                threshold, reference_verification_id, selfie_content_type, reference_content_type,
            ),
            headers=idempotency_headers(idempotency_key),
        )

    async def get_processor(self) -> Dict[str, Any]:
        """Get the identity processor configuration."""
        return await self._client.get("/api/v1/identity/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the identity processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/identity/processor", json=body)


class AsyncMessagingService:
    """Async messaging service — email, SMS, WhatsApp."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def send_email(
        self,
        to: Union[str, List[str]],
        subject: str,
        html: str,
        reply_to: Optional[Union[str, List[str]]] = None,
        attachments: Optional[List[Dict]] = None,
        *,
        from_: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        text: Optional[str] = None,
        caller_ref: Optional[str] = None,
        template_id: Optional[str] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a transactional email (POST /api/v1/messaging/email/send).

        ``from_`` is required: an address or "Name <address>", at most 320
        characters. ``to`` (and ``cc`` / ``bcc``, up to 10 each) hold one
        address or "Name <address>" per entry. ``reply_to`` is one address or a
        list of 1 to 5, each at most 320 characters. ``template_id`` names a
        built-in, platform or your organisation's template (another's or an
        unknown id: 404), rendered with ``variables`` (string values) or none;
        its subject, HTML and text replace ``subject`` / ``html`` / ``text``.
        ``caller_ref`` (at most 200 characters) is stored with the email's
        message log entries. ``attachments`` entries are
        ``{"filename": ..., "content": <base64>}``. The server checks every
        limit and answers 400 (a refused field) or 404.
        """
        body: Dict[str, Any] = {
            "from": from_,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        }
        if reply_to:
            body["replyTo"] = reply_to
        if attachments:
            body["attachments"] = attachments
        if cc is not None:
            body["cc"] = cc
        if bcc is not None:
            body["bcc"] = bcc
        if text is not None:
            body["text"] = text
        if caller_ref is not None:
            body["callerRef"] = caller_ref
        if template_id is not None:
            body["templateId"] = template_id
        if variables is not None:
            body["variables"] = variables
        return await self._client.post("/api/v1/messaging/email/send", json=body)

    async def send_sms(self, to: str, message: str, region_code: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"to": to, "message": message}
        if region_code:
            body["regionCode"] = region_code
        return await self._client.post("/api/v1/messaging/sms", json=body)

    async def send_whatsapp(self, to: str, template_id: Optional[str] = None, message: Optional[str] = None, phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"to": to}
        if template_id:
            body["templateId"] = template_id
        if message:
            body["message"] = message
        if phone_number_id:
            body["phoneNumberId"] = phone_number_id
        return await self._client.post("/api/v1/messaging/whatsapp", json=body)

    async def build_whatsapp_link(self, to: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Async twin of MessagingService.build_whatsapp_link (nothing is sent)."""
        body: Dict[str, Any] = {"to": to}
        if message is not None:
            body["message"] = message
        return await self._client.post("/api/v1/messaging/whatsapp/link", json=body)

    async def whatsapp_health(self) -> Dict[str, Any]:
        """Async twin of MessagingService.whatsapp_health (the caller's own recent failures)."""
        return await self._client.get("/api/v1/messaging/whatsapp/health")

    async def email_health(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/messaging/email/health")

    async def sms_health(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/messaging/sms/health")

    async def queue_stats(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/messaging/queue/stats")

    async def process_queue(self) -> Dict[str, Any]:
        """Process the email retry queue now: platform keys only (a key with an organisation gets 403 FORBIDDEN)."""
        return await self._client.post("/api/v1/messaging/queue/process")

    async def get_processor(self) -> Dict[str, Any]:
        """Get the messaging processor configuration."""
        return await self._client.get("/api/v1/messaging/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the messaging processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/messaging/processor", json=body)


class AsyncWebhooksService:
    """Async webhooks service — CRUD, rotate, test, v2 recipient endpoints,
    dispatch, deliveries. Reuses webhooks.py's builders and path templates."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list(
        self,
        recipient_ref: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
    ) -> Dict[str, Any]:
        return await self._client.get(WEBHOOKS_PATH, params=build_page_params(recipient_ref, limit, page))

    async def create(
        self,
        name: str,
        url: str,
        events: List[str],
        engine_version: Optional[int] = None,
        recipient_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(
            WEBHOOKS_PATH, json=build_create_body(name, url, events, engine_version, recipient_ref)
        )

    async def get(self, webhook_id: str) -> Dict[str, Any]:
        return await self._client.get(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id))

    async def update(self, webhook_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id), json=kwargs)

    async def delete(self, webhook_id: str) -> Dict[str, Any]:
        return await self._client.delete(webhook_path(WEBHOOK_BY_ID_PATH, webhook_id))

    async def rotate_secret(self, webhook_id: str) -> Dict[str, Any]:
        return await self._client.post(webhook_path(WEBHOOK_ROTATE_PATH, webhook_id))

    async def test(self, webhook_id: str) -> Dict[str, Any]:
        return await self._client.post(webhook_path(WEBHOOK_TEST_PATH, webhook_id))

    async def dispatch(
        self,
        recipient_ref: str,
        event_type: str,
        event_id: str,
        data: Optional[Dict[str, Any]],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Same request as WebhooksService.dispatch (a None data is sent as {})."""
        return await self._client.post(
            WEBHOOK_DISPATCH_PATH,
            json=build_dispatch_body(recipient_ref, event_type, event_id, data),
            headers=idempotency_headers(idempotency_key),
        )

    async def deliveries(
        self, webhook_id: str, limit: Optional[int] = None, page: Optional[int] = None
    ) -> Dict[str, Any]:
        return await self._client.get(
            webhook_path(WEBHOOK_DELIVERIES_PATH, webhook_id), params=build_page_params(None, limit, page)
        )

    async def redeliver(self, delivery_id: str) -> Dict[str, Any]:
        return await self._client.post(redeliver_path(delivery_id))


class AsyncTemplatesService:
    """Async templates service — CRUD, render, send."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/templates")

    async def create(self, name: str, subject: str, html: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.post("/api/v1/templates", json={"name": name, "subject": subject, "html": html, **kwargs})

    async def get(self, template_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/templates/{template_id}")

    async def update(self, template_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/templates/{template_id}", json=kwargs)

    async def delete(self, template_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/templates/{template_id}")

    async def render(self, template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/templates/{template_id}/render", json={"variables": variables})

    async def send(self, template_id: str, to: Union[str, List[str]], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/templates/{template_id}/send", json={"to": to, "variables": variables or {}})


class AsyncStorageService:
    """Async storage service — media file uploads and management."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    # Media — direct uploads

    async def upload_file(
        self,
        file_path: Union[str, Path],
        *,
        module: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a single file via multipart form data."""
        path = Path(file_path)
        fields: Dict[str, Any] = {}
        if module:
            fields["module"] = module
        if entity_id:
            fields["entityId"] = entity_id
        return await self._client.upload("/api/v1/storage/media/upload", path, fields=fields)

    async def batch_upload(
        self,
        file_paths: Sequence[Union[str, Path]],
        *,
        module: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload multiple files in a single request via multipart form data."""
        paths = [Path(p) for p in file_paths]
        fields: Dict[str, Any] = {}
        if module:
            fields["module"] = module
        if entity_id:
            fields["entityId"] = entity_id
        return await self._client.upload_many("/api/v1/storage/media/upload/batch", paths, fields=fields)

    # Media — signed upload flow

    async def sign_upload(self, filename: str, content_type: str) -> Dict[str, Any]:
        return await self._client.post("/api/v1/storage/media/sign-upload", json={"filename": filename, "contentType": content_type})

    async def register_url(self, url: str, filename: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"url": url}
        if filename:
            body["filename"] = filename
        return await self._client.post("/api/v1/storage/media/register", json=body)

    async def list_files(self, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return await self._client.get("/api/v1/storage/media/files", params=params)

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/storage/media/files/{file_id}")

    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/storage/media/files/{file_id}")

    async def reorder_files(self, file_ids: List[str]) -> Dict[str, Any]:
        return await self._client.post("/api/v1/storage/media/files/reorder", json={"fileIds": file_ids})

    async def get_processor(self) -> Dict[str, Any]:
        """Get the storage processor configuration."""
        return await self._client.get("/api/v1/storage/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the storage processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/storage/processor", json=body)


class AsyncDocumentsService:
    """Async documents service — fixed documents, folders, and deletion overrides."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list_documents(self, folder_id: Optional[str] = None, page: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if folder_id:
            params["folderId"] = folder_id
        if page:
            params["page"] = str(page)
        return await self._client.get("/api/v1/storage/fixed/documents", params=params)

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/storage/fixed/documents/{document_id}")

    async def create_document(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new fixed document."""
        return await self._client.post("/api/v1/storage/fixed/documents", json=kwargs)

    async def update_document(self, document_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Update a fixed document."""
        return await self._client.patch(f"/api/v1/storage/fixed/documents/{document_id}", json=kwargs)

    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a fixed document. Retention-protected documents answer
        DELETE_BLOCKED — request and execute a deletion override instead."""
        return await self._client.delete(f"/api/v1/storage/fixed/documents/{document_id}")

    # Folders + overrides mirror DocumentsService (services/documents.py)
    # exactly and build their params/bodies with the SAME helpers, so the
    # sync and async clients cannot send different shapes.

    async def get_folder_by_owner(self, owner_type: str, owner_id: str) -> Dict[str, Any]:
        """Get the folder for a given owner (one folder per owner_type+owner_id)."""
        return await self._client.get(
            "/api/v1/storage/fixed/folders", params=folder_owner_params(owner_type, owner_id),
        )

    async def list_folders(self, owner_type: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
        """Deprecated — the API has no list-folders route. See DocumentsService.list_folders."""
        check_deprecated_list_folders(owner_type, owner_id)
        return await self.get_folder_by_owner(owner_type, owner_id)  # type: ignore[arg-type]

    async def get_folder(self, folder_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/storage/fixed/folders/{folder_id}")

    async def create_folder(self, owner_type: str, owner_id: str) -> Dict[str, Any]:
        """Create (or idempotently return) a storage folder for an owner.
        Returns {"folderId": "..."}."""
        return await self._client.post(
            "/api/v1/storage/fixed/folders", json=folder_owner_params(owner_type, owner_id),
        )

    async def request_override(
        self,
        document_id: Optional[str] = None,
        override_reason: Optional[str] = None,
        authority_reference: Optional[str] = None,
        authority_type: Optional[str] = None,
        authority_document: Optional[str] = None,
        operator_id: Optional[str] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """Request a deletion override. See DocumentsService.request_override."""
        body = build_request_override_body(
            {
                "document_id": document_id,
                "override_reason": override_reason,
                "authority_reference": authority_reference,
                "authority_type": authority_type,
                "authority_document": authority_document,
                "operator_id": operator_id,
            },
            legacy_kwargs,
        )
        return await self._client.post("/api/v1/storage/fixed/overrides", json=body)

    async def process_override(
        self,
        override_id: str,
        action: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """Approve, reject, witness, or execute an override. See DocumentsService.process_override."""
        body = build_process_override_body(
            {"action": action, "rejection_reason": rejection_reason, "operator_id": operator_id},
            legacy_kwargs,
        )
        return await self._client.patch(f"/api/v1/storage/fixed/overrides/{override_id}", json=body)


class AsyncWorkflowsService:
    """Async workflows service — event-driven automation."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/workflows")

    async def create(self, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.post("/api/v1/workflows", json=kwargs)

    async def get(self, workflow_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/workflows/{workflow_id}")

    async def update(self, workflow_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/workflows/{workflow_id}", json=kwargs)

    async def delete(self, workflow_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/workflows/{workflow_id}")

    async def evaluate(
        self,
        event_type: str,
        entity_data: Optional[Dict[str, Any]] = None,
        *,
        payload: Optional[Dict[str, Any]] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source_app: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """As WorkflowsService.evaluate (the same body, evaluate_request_body)."""
        body = evaluate_request_body(
            event_type, entity_data, payload=payload, entity_type=entity_type, entity_id=entity_id,
            source_app=source_app, metadata=metadata, dry_run=dry_run,
        )
        return await self._client.post("/api/v1/workflows/evaluate", json=body)

    async def dry_run(self, workflow_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Dry-run a trigger against a context (no side effects)."""
        return await self._client.post(f"/api/v1/workflows/{workflow_id}/dry-run", json=context)


class AsyncDomainsService:
    """Async domains service — sending domain management."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def list(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/domains")

    async def add(self, domain: str) -> Dict[str, Any]:
        return await self._client.post("/api/v1/domains", json={"domain": domain})

    async def get(self, domain_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/domains/{domain_id}")

    async def delete(self, domain_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/domains/{domain_id}")

    async def verify(self, domain_id: str) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/domains/{domain_id}/verify")


class AsyncEventsService:
    """Async events service — ingest, log, subscriptions, replay."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def ingest(self, event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client.post("/api/v1/events", json={
            "eventType": event_type, "entityType": entity_type,
            "entityId": entity_id, "payload": payload,
        })

    async def log(self, event_type: Optional[str] = None, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if event_type:
            params["eventType"] = event_type
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return await self._client.get("/api/v1/event-log", params=params)

    async def list_subscriptions(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/event-subscriptions")

    async def create_subscription(self, event_types: List[str], webhook_url: str, secret: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"eventTypes": event_types, "webhookUrl": webhook_url}
        if secret:
            body["secret"] = secret
        return await self._client.post("/api/v1/event-subscriptions", json=body)

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/event-subscriptions/{subscription_id}")

    async def update_subscription(self, subscription_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/event-subscriptions/{subscription_id}", json=kwargs)

    async def delete_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/event-subscriptions/{subscription_id}")

    async def replay(self, subscription_id: str, from_date: str, to_date: str) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/event-subscriptions/{subscription_id}/replay", json={"from": from_date, "to": to_date})


class AsyncThreadsService:
    """Async contextual messaging (Threads) service — channels, threads, messages, flags, escalation."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    # ── Channels ──────────────────────────────────────────────────────────

    async def create_channel(
        self,
        slug: str,
        display_name: str,
        entity_type: str,
        participant_roles: List[str],
        default_visibility: List[str],
        lifecycle_rules: Optional[Dict[str, Any]] = None,
        escalation_config: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post("/api/v1/threads/channels", json={
            "slug": slug,
            "displayName": display_name,
            "entityType": entity_type,
            "participantRoles": participant_roles,
            "defaultVisibility": default_visibility,
            "lifecycleRules": lifecycle_rules,
            "escalationConfig": escalation_config,
            "webhookUrl": webhook_url,
        })

    async def list_channels(self) -> Dict[str, Any]:
        return await self._client.get("/api/v1/threads/channels")

    async def update_channel(self, channel_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/threads/channels/{channel_id}", json=kwargs)

    async def get_escalation_config(self, channel_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/threads/channels/{channel_id}/escalation")

    async def set_escalation_config(self, channel_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client.put(f"/api/v1/threads/channels/{channel_id}/escalation", json=config)

    # ── Threads ───────────────────────────────────────────────────────────

    async def create_thread(
        self,
        channel_slug: str,
        entity_id: str,
        participants: List[Dict[str, str]],
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self._client.post("/api/v1/threads", json={
            "channelSlug": channel_slug,
            "entityId": entity_id,
            "subject": subject,
            "metadata": metadata,
            "participants": participants,
        })

    async def list_threads(self, **params: Any) -> Dict[str, Any]:
        return await self._client.get("/api/v1/threads", params=params)

    async def get_thread(self, thread_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/threads/{thread_id}")

    async def close_thread(self, thread_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/close", json={"reason": reason})

    async def reopen_thread(self, thread_id: str) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/reopen")

    async def entity_event(
        self,
        channel_slug: str,
        entity_id: str,
        event: str,
        new_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post("/api/v1/threads/entity-event", json={
            "channelSlug": channel_slug,
            "entityId": entity_id,
            "event": event,
            "newStatus": new_status,
        })

    # ── Messages ──────────────────────────────────────────────────────────

    async def send_message(
        self,
        thread_id: str,
        sender_external_id: str,
        sender_role: str,
        content: str,
        visibility: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/messages", json={
            "senderExternalId": sender_external_id,
            "senderRole": sender_role,
            "content": content,
            "visibility": visibility,
        })

    async def list_messages(
        self,
        thread_id: str,
        role: str,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return await self._client.get(
            f"/api/v1/threads/{thread_id}/messages",
            params={"page": page, "limit": limit},
            headers={"x-participant-role": role},
        )

    async def send_system_message(
        self,
        thread_id: str,
        content: str,
        visibility: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/messages/system", json={
            "content": content,
            "visibility": visibility or ["ALL"],
        })

    async def edit_message(self, message_id: str, content: str) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/threads/messages/{message_id}", json={"content": content})

    async def delete_message(self, message_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/threads/messages/{message_id}")

    # ── Read State & Inbox ────────────────────────────────────────────────

    async def mark_read(
        self,
        thread_id: str,
        external_id: str,
        role: str,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/read", json={
            "participantExternalId": external_id,
            "participantRole": role,
            "messageId": message_id,
        })

    async def get_read_states(self, thread_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/threads/{thread_id}/read-state")

    async def inbox(
        self,
        external_id: str,
        role: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"externalId": external_id, "role": role, "page": page, "limit": limit}
        if status:
            params["status"] = status
        return await self._client.get("/api/v1/threads/inbox", params=params)

    async def unread_count(self, external_id: str, role: str) -> Dict[str, Any]:
        return await self._client.get("/api/v1/threads/inbox/unread-count", params={
            "externalId": external_id,
            "role": role,
        })

    # ── Flags & Escalation ────────────────────────────────────────────────

    async def flag_message(
        self,
        thread_id: str,
        message_id: str,
        reason: str,
        flagged_by_external_id: str,
        flagged_by_role: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.post(
            f"/api/v1/threads/{thread_id}/messages/{message_id}/flag",
            json={
                "reason": reason,
                "note": note,
                "flaggedByExternalId": flagged_by_external_id,
                "flaggedByRole": flagged_by_role,
            },
        )

    async def escalate_thread(
        self,
        thread_id: str,
        reason: str,
        escalated_by_external_id: str,
        escalated_by_role: str,
    ) -> Dict[str, Any]:
        return await self._client.post(f"/api/v1/threads/{thread_id}/escalate", json={
            "reason": reason,
            "escalatedByExternalId": escalated_by_external_id,
            "escalatedByRole": escalated_by_role,
        })

    async def review_flag(
        self,
        flag_id: str,
        status: str,
        reviewed_by_external_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client.patch(f"/api/v1/threads/flags/{flag_id}", json={
            "status": status,
            "reviewedByExternalId": reviewed_by_external_id,
            "note": note,
        })

    async def list_flags(self, thread_id: str, status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        return await self._client.get(f"/api/v1/threads/{thread_id}/flags", params=params)

    async def list_flags_across_threads(
        self,
        status: Optional[str] = None,
        channel_slug: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if channel_slug:
            params["channelSlug"] = channel_slug
        return await self._client.get("/api/v1/threads/flags", params=params)

    # ── Participants ─────────────────────────────────────────────────────

    async def add_participant(
        self,
        thread_id: str,
        role: str,
        external_id: str,
        display_name: str,
        avatar_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "role": role,
            "externalId": external_id,
            "displayName": display_name,
        }
        if avatar_url is not None:
            body["avatarUrl"] = avatar_url
        return await self._client.post(f"/api/v1/threads/{thread_id}/participants", json=body)

    async def remove_participant(self, thread_id: str, participant_id: str) -> Dict[str, Any]:
        return await self._client.delete(f"/api/v1/threads/{thread_id}/participants/{participant_id}")

    async def update_participant(
        self,
        thread_id: str,
        participant_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        is_muted: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if display_name is not None:
            body["displayName"] = display_name
        if avatar_url is not None:
            body["avatarUrl"] = avatar_url
        if is_muted is not None:
            body["isMuted"] = is_muted
        return await self._client.patch(
            f"/api/v1/threads/{thread_id}/participants/{participant_id}",
            json=body,
        )

    async def update_thread(
        self,
        thread_id: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if subject is not None:
            body["subject"] = subject
        if metadata is not None:
            body["metadata"] = metadata
        return await self._client.patch(f"/api/v1/threads/{thread_id}", json=body)


class AsyncExportsService:
    """Async exports service — data export creation and retrieval."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def create_export(self, **kwargs: Any) -> Dict[str, Any]:
        return await self._client.post("/api/v1/exports", json=kwargs)

    async def get_export(self, export_id: str) -> Dict[str, Any]:
        return await self._client.get(f"/api/v1/exports/{export_id}")

    async def get_processor(self) -> Dict[str, Any]:
        """Get the exports processor configuration."""
        return await self._client.get("/api/v1/exports/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the exports processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/exports/processor", json=body)


class AsyncOcrService:
    """Async OCR service — identity document verification."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def verify_identity(self, document_url: Optional[str] = None, document_base64: Optional[str] = None, profile_name: Optional[Dict[str, str]] = None, expected_type: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if document_url:
            body["documentUrl"] = document_url
        if document_base64:
            body["documentBase64"] = document_base64
        if profile_name:
            body["profileName"] = profile_name
        if expected_type:
            body["expectedDocumentType"] = expected_type
        return await self._client.post("/api/v1/ocr/verify-identity", json=body)

    async def get_processor(self) -> Dict[str, Any]:
        """Get the OCR processor configuration."""
        return await self._client.get("/api/v1/ocr/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the OCR processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/ocr/processor", json=body)


class AsyncPdfService:
    """Async PDF service — document generation."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def generate_offer_letter(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate an offer letter PDF."""
        return await self._client.post("/api/v1/pdf/offer-letter", json=kwargs)

    async def generate_property_flyer(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate a property flyer PDF."""
        return await self._client.post("/api/v1/pdf/property-flyer", json=kwargs)

    async def rasterize(self, **kwargs: Any) -> Dict[str, Any]:
        """Rasterize one page of a base64-encoded PDF to a JPEG/PNG image.

        See PdfService.rasterize (pdf.py) for the expected kwargs and
        response shape — this sends the identical request.
        """
        body: Dict[str, Any] = dict(kwargs)
        if "pdf_base64" in body:
            body["pdfBase64"] = body.pop("pdf_base64")
        return await self._client.post("/api/v1/pdf/rasterize", json=body)

    async def get_processor(self) -> Dict[str, Any]:
        """Get the PDF processor configuration."""
        return await self._client.get("/api/v1/pdf/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the PDF processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/pdf/processor", json=body)


class AsyncQrService:
    """Async QR service — QR code generation."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def generate(self, data: str, size: Optional[int] = None, format: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"data": data}
        if size:
            body["size"] = size
        if format:
            body["format"] = format
        return await self._client.post("/api/v1/qr", json=body)

    async def generate_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate QR codes in batch."""
        return await self._client.post("/api/v1/qr/batch", json={"items": items})

    async def get_processor(self) -> Dict[str, Any]:
        """Get the QR processor configuration."""
        return await self._client.get("/api/v1/qr/processor")

    async def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the QR processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return await self._client.put("/api/v1/qr/processor", json=body)


class AsyncUsageService:
    """Async usage service — metering and usage summaries."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def summary(self, month: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {"month": month} if month else {}
        return await self._client.get("/api/v1/usage/summary", params=params)


class AsyncAiService:
    """Async product AI gateway (scope ``ai:complete``) — see AiService (ai.py)."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def complete(
        self,
        feature_key: str,
        provider: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run one chat completion (optionally with tools). See AiService.complete."""
        return await self._client.post(
            "/api/v1/ai/complete",
            json=build_complete_body(feature_key, provider, messages, model, tools, tool_choice),
            **MODEL_CALL_OPTIONS,
        )

    async def extract(
        self,
        feature_key: str,
        system_prompt: str,
        user_prompt: str,
        output_json_schema: Dict[str, Any],
        model_tier: str,
        images: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Structured extraction. See AiService.extract."""
        return await self._client.post(
            "/api/v1/ai/extract",
            json=build_extract_body(
                feature_key, system_prompt, user_prompt, output_json_schema,
                model_tier, images, temperature,
            ),
            **MODEL_CALL_OPTIONS,
        )

    async def profile(self, feature_key: str) -> Dict[str, Any]:
        """The calling service's own AI profile. See AiService.profile."""
        return await self._client.get("/api/v1/ai/profile", params={"featureKey": feature_key})

    async def usage(
        self,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        feature_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The calling service's own AI + vision usage. See AiService.usage."""
        return await self._client.get(
            "/api/v1/ai/usage",
            params=build_usage_params(from_, to, feature_key),
        )


class AsyncVisionService:
    """Async image analysis (scope ``vision:analyze``) — see VisionService (vision.py)."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def analyze_room(
        self,
        room_categories: List[str],
        want_alt_text: bool,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        locale: Optional[str] = None,
        feature_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a property photo. See VisionService.analyze_room."""
        return await self._client.post(
            "/api/v1/vision/analyze-room",
            json=build_analyze_room_body(
                room_categories, want_alt_text, image_url, image_base64, locale, feature_key,
            ),
            headers=idempotency_headers(idempotency_key),
            **analyze_room_call_options(idempotency_key),
        )


class AsyncKnowledgeService:
    """Async knowledge retrieval (scope ``ai:knowledge``) — see KnowledgeService (knowledge.py)."""

    def __init__(self, client: AsyncPlatformXeClient):
        self._client = client

    async def upsert_document(
        self,
        feature_key: str,
        collection: str,
        source_ref: str,
        title: str,
        text: str,
        url: Optional[str] = None,
        acl: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or replace one document. See KnowledgeService.upsert_document."""
        return await self._client.put(
            "/api/v1/ai/knowledge/documents",
            json=build_upsert_document_body(feature_key, collection, source_ref, title, text, url, acl),
            **UPSERT_CALL_OPTIONS,
        )

    async def delete_document(self, collection: str, source_ref: str) -> Dict[str, Any]:
        """Delete one document (idempotent). See KnowledgeService.delete_document."""
        return await self._client.delete(
            "/api/v1/ai/knowledge/documents",
            params=build_document_ref_params(collection, source_ref),
        )

    async def list_documents(
        self,
        collection: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """One page of a collection's documents. See KnowledgeService.list_documents."""
        return await self._client.get(
            "/api/v1/ai/knowledge/documents",
            params=build_list_params(collection, cursor, limit),
        )

    async def search(
        self,
        feature_key: str,
        collections: List[str],
        query: str,
        acl_tags: List[str],
        k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Hybrid search. See KnowledgeService.search."""
        return await self._client.post(
            "/api/v1/ai/knowledge/search",
            json=build_search_body(feature_key, collections, query, acl_tags, k),
            **SEARCH_CALL_OPTIONS,
        )
