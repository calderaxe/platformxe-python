# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-01  (pending release) create_override gains replace= (a GRANT over a
#   live DENY is refused 409 OVERRIDE_DENY_ACTIVE without it; the endpoint now
#   upserts onto (admin, path, action), 201 create / 200 update); resolve()
#   documents deniedCapabilities, which a local evaluator must apply.
# =============================================================================

"""Permissions service — RBAC, ABAC, ReBAC, Federation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class PermissionsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def check(self, admin_id: str, path: str, action: str, resource: Optional[Dict] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/check", json={
            "adminId": admin_id, "path": path, "action": action,
            "resource": resource, "context": context,
        })

    def check_batch(self, checks: List[Dict]) -> List[Dict[str, Any]]:
        """The results in request order. The route answers a bare list, which
        this always returned; the annotation said a dict until v1.11.0."""
        return self._client.post("/api/v1/permissions/check-batch", json={"checks": checks})  # type: ignore[return-value]

    def resolve(self, admin_id: str) -> Dict[str, Any]:
        """Resolved capabilities for an admin.

        The result carries ``deniedCapabilities`` (``path:action`` of every live DENY override). A local
        evaluator MUST refuse any request one covers (same action, same path or a sub-path,
        case-insensitive, trailing '/' ignored) before using ``capabilities``, which may still hold role
        wildcards a deny overrides.
        """
        return self._client.get(f"/api/v1/permissions/resolve/{admin_id}")

    def list_roles(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/permissions/roles")

    def create_role(self, name: str, description: Optional[str] = None, model: str = "SIMPLE") -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/roles", json={
            "name": name, "description": description, "model": model,
        })

    def get_role(self, role_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/roles/{role_id}")

    def update_role(self, role_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return self._client.patch(f"/api/v1/permissions/roles/{role_id}", json=body)

    def delete_role(self, role_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/permissions/roles/{role_id}")

    def get_role_capabilities(self, role_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/roles/{role_id}/capabilities")

    def set_role_capabilities(self, role_id: str, capabilities: List[str]) -> Dict[str, Any]:
        return self._client.put(f"/api/v1/permissions/roles/{role_id}/capabilities", json={"capabilities": capabilities})

    def get_role_module_permissions(self, role_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/roles/{role_id}/modules")

    def set_role_module_permissions(self, role_id: str, modules: List[Dict]) -> Dict[str, Any]:
        return self._client.put(f"/api/v1/permissions/roles/{role_id}/modules", json={"modules": modules})

    def list_overrides(self, admin_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/overrides/{admin_id}")

    def create_override(self, admin_id: str, path: str, action: str, effect: str, reason: str, expires_at: Optional[str] = None, replace: bool = False) -> Dict[str, Any]:
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
        return self._client.post("/api/v1/permissions/overrides", json=body)

    def delete_override(self, override_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/permissions/overrides/remove/{override_id}")

    def list_policies(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/permissions/policies")

    def create_policy(self, path: str, action: str, condition: Dict, effect: str, priority: int = 0, description: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/policies", json={
            "path": path, "action": action, "condition": condition,
            "effect": effect, "priority": priority, "description": description,
        })

    def update_policy(self, policy_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/permissions/policies/{policy_id}", json=kwargs)

    def delete_policy(self, policy_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/permissions/policies/{policy_id}")

    def list_relationships(self, **params: Any) -> Dict[str, Any]:
        return self._client.get("/api/v1/permissions/relationships", params=params)

    def update_relationships(self, operations: List[Dict]) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/relationships", json=operations)

    def register_module(self, id: str, app: str, name: str, paths: List[str], description: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/modules", json={
            "id": id, "app": app, "name": name, "paths": paths, "description": description,
        })

    def list_modules(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/permissions/modules")

    def get_audit_logs(self, admin_id: Optional[str] = None, path: Optional[str] = None, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if admin_id:
            params["adminId"] = admin_id
        if path:
            params["path"] = path
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return self._client.get("/api/v1/permissions/audit", params=params)

    def list_change_logs(self, entity_type: Optional[str] = None, entity_id: Optional[str] = None, changed_by: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
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
        return self._client.get("/api/v1/permissions/audit/changes", params=params)

    def export_audit(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._client.get("/api/v1/permissions/audit/export", params=params)

    def shadow_check(self, admin_id: str, path: str, action: str, local_decision: bool, context: Optional[Dict] = None) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/shadow-check", json={
            "adminId": admin_id, "path": path, "action": action,
            "localDecision": local_decision, "context": context,
        })

    # Federation

    def create_federation_group(self, name: str) -> Dict[str, Any]:
        return self._client.post("/api/v1/permissions/federation/groups", json={"name": name})

    def list_federation_groups(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/permissions/federation/groups")

    def get_federation_group(self, group_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/federation/groups/{group_id}")

    def delete_federation_group(self, group_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/permissions/federation/groups/{group_id}")

    def add_federation_member(self, group_id: str, organization_id: str, prefix: str) -> Dict[str, Any]:
        """Invite an organization into the group (owner only).

        The membership is created with status ``INVITED``; the invited
        organization must call :meth:`accept_federation_membership` with its own
        API key before any pull or push reaches it.
        """
        return self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/members", json={
            "organizationId": organization_id, "prefix": prefix,
        })

    def accept_federation_membership(self, group_id: str) -> Dict[str, Any]:
        """Accept this organization's invitation to a federation group.

        Call with the invited organization's own API key — the caller's
        organization is the one accepted. Returns the ``ACTIVE`` membership.
        """
        return self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/members/accept", json={})

    def remove_federation_member(self, group_id: str, organization_id: str) -> Dict[str, Any]:
        """Remove a membership.

        The owner may remove any member; any other organization may pass its own
        ``organization_id`` to leave the group or decline an invitation.
        """
        return self._client.delete(f"/api/v1/permissions/federation/groups/{group_id}/members?organizationId={organization_id}")

    def pull_federation_modules(self, group_id: str, target_org_id: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/pull", json={"targetOrgId": target_org_id})

    def push_federation_permissions(self, group_id: str, admin_ids: List[str], target_org_id: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/permissions/federation/groups/{group_id}/push", json={
            "adminIds": admin_ids, "targetOrgId": target_org_id,
        })

    def get_federation_status(self, group_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/permissions/federation/groups/{group_id}/status")
