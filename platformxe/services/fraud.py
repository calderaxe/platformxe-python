# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Fraud Detection Engine — decide, screen, rules, lists, cases, devices,
terms, and federation push.

Covers Phase 6A through 6H of the Fraud Detection Engine:
  - decide / shadow_decide   (Phase 6A)
  - decisions (list / get)   (Phase 6A)
  - rules (CRUD)             (Phase 6B)
  - screen                   (Phase 6C)
  - lists + list entries     (Phase 6C)
  - devices.seen             (Phase 6D)
  - cases (list / get / open / update / transition)  (Phase 6E)
  - terms.status / terms.accept                       (Phase 6H)
  - federation.preview / federation.push              (Phase 6G)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class FraudTermsService:
    """Fraud Detection Engine T&Cs (Phase 6H)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def status(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/fraud/terms/status")

    def accept(self, accepted_by: str, version: str) -> Dict[str, Any]:
        return self._client.post(
            "/api/v1/fraud/terms/accept",
            json={"acceptedBy": accepted_by, "version": version},
        )


class FraudFederationService:
    """Fraud federation push (Phase 6G — Enterprise only)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def preview(self, group_id: str) -> Dict[str, Any]:
        return self._client.get(
            f"/api/v1/permissions/federation/groups/{group_id}/fraud/preview",
        )

    def push(self, group_id: str) -> Dict[str, Any]:
        return self._client.post(
            f"/api/v1/permissions/federation/groups/{group_id}/fraud/push",
            json={},
        )


class FraudCasesService:
    """Cases workflow (Phase 6E)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(
        self,
        status: Optional[str] = None,
        decision_id: Optional[str] = None,
        overdue_only: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if decision_id:
            params["decisionId"] = decision_id
        if overdue_only:
            params["overdueOnly"] = "true"
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._client.get("/api/v1/fraud/cases", params=params or None)

    def get(self, case_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/fraud/cases/{case_id}")

    def open(self, **payload: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/fraud/cases", json=payload)

    def update(self, case_id: str, **payload: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/fraud/cases/{case_id}", json=payload)

    def transition(self, case_id: str, **payload: Any) -> Dict[str, Any]:
        return self._client.post(
            f"/api/v1/fraud/cases/{case_id}/transition",
            json=payload,
        )


class FraudRulesService:
    """Tenant fraud rules CRUD (Phase 6B)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(self, status: Optional[str] = None) -> Dict[str, Any]:
        params = {"status": status} if status else None
        return self._client.get("/api/v1/fraud/rules", params=params)

    def get(self, rule_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/fraud/rules/{rule_id}")

    def create(self, **payload: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/fraud/rules", json=payload)

    def update(self, rule_id: str, **payload: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/fraud/rules/{rule_id}", json=payload)

    def publish(self, rule_id: str) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/fraud/rules/{rule_id}/publish", json={})

    def archive(self, rule_id: str) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/fraud/rules/{rule_id}/archive", json={})


class FraudListsService:
    """Tenant blocklists / allowlists (Phase 6C)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/fraud/lists")

    def get(self, list_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/fraud/lists/{list_id}")

    def create(self, source: str, name: str, kind: str) -> Dict[str, Any]:
        return self._client.post(
            "/api/v1/fraud/lists",
            json={"source": source, "name": name, "kind": kind},
        )

    def update(self, list_id: str, **payload: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/fraud/lists/{list_id}", json=payload)

    def delete(self, list_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/fraud/lists/{list_id}")

    def list_entries(self, list_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/fraud/lists/{list_id}/entries")

    def add_entry(self, list_id: str, **payload: Any) -> Dict[str, Any]:
        return self._client.post(
            f"/api/v1/fraud/lists/{list_id}/entries",
            json=payload,
        )

    def remove_entry(self, list_id: str, entry_id: str) -> Dict[str, Any]:
        return self._client.delete(
            f"/api/v1/fraud/lists/{list_id}/entries/{entry_id}",
        )


class FraudDevicesService:
    """Device fingerprint registry (Phase 6D)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def seen(self, **payload: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/fraud/devices/seen", json=payload)


class FraudService:
    """Top-level Fraud Detection Engine namespace.

    Sub-namespaces:
      client.fraud.cases       — cases workflow
      client.fraud.rules       — rule CRUD
      client.fraud.lists       — list + entry CRUD
      client.fraud.devices     — device fingerprint registry
      client.fraud.terms       — T&Cs status / accept
      client.fraud.federation  — federation push / preview
    """

    def __init__(self, client: "PlatformXeClient"):
        self._client = client
        self.cases = FraudCasesService(client)
        self.rules = FraudRulesService(client)
        self.lists = FraudListsService(client)
        self.devices = FraudDevicesService(client)
        self.terms = FraudTermsService(client)
        self.federation = FraudFederationService(client)

    # --- /decide and /shadow-decide -----------------------------------

    def decide(
        self,
        subject_id: str,
        subject_kind: str,
        action: str,
        resource_kind: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "subjectKind": subject_kind,
            "action": action,
            "resourceKind": resource_kind,
        }
        if resource_id is not None:
            body["resourceId"] = resource_id
        if context is not None:
            body["context"] = context
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/fraud/decide", json=body, headers=headers)

    def shadow_decide(
        self,
        subject_id: str,
        subject_kind: str,
        action: str,
        resource_kind: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "subjectKind": subject_kind,
            "action": action,
            "resourceKind": resource_kind,
        }
        if resource_id is not None:
            body["resourceId"] = resource_id
        if context is not None:
            body["context"] = context
        return self._client.post("/api/v1/fraud/shadow-decide", json=body)

    # --- /screen ------------------------------------------------------

    def screen(
        self,
        name: str,
        dob: Optional[str] = None,
        country: Optional[str] = None,
        identifiers: Optional[Dict[str, str]] = None,
        kinds: Optional[Sequence[str]] = None,
        threshold: Optional[float] = None,
        decision_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name}
        if dob:
            body["dob"] = dob
        if country:
            body["country"] = country
        if identifiers:
            body["identifiers"] = identifiers
        if kinds:
            body["kinds"] = list(kinds)
        if threshold is not None:
            body["threshold"] = threshold
        if decision_id:
            body["decisionId"] = decision_id
        return self._client.post("/api/v1/fraud/screen", json=body)

    # --- /decisions ---------------------------------------------------

    def list_decisions(
        self,
        subject_id: Optional[str] = None,
        verdict: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if subject_id:
            params["subjectId"] = subject_id
        if verdict:
            params["verdict"] = verdict
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._client.get("/api/v1/fraud/decisions", params=params or None)

    def get_decision(self, decision_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/fraud/decisions/{decision_id}")
