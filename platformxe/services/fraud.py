# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
#
# CHANGELOG:
# 2026-11-18  v1.12.0  Rule status changes go through the one route the API
#   has, POST /api/v1/fraud/rules/{id}/transition {target}: rules.transition()
#   added, rules.publish()/archive() now call it (they posted to
#   /rules/{id}/publish and /rules/{id}/archive, which do not exist: every call
#   was a 404), and rules.shadow()/draft() added. rules.shadow_report() added
#   (GET /api/v1/fraud/rules/{id}/shadow-report). cases.transition() documents
#   409 CASE_AT_MLRO_STAGE.
# 2026-11-18  v1.12.0  (review round 1) RULE_TRANSITIONS carries a DUPLICATION
#   marker naming the server table; src/lib/api/sdk-fraud-rule-transitions
#   .test.ts fails CI when they differ.
# 2026-11-19  v1.13.0  rules.update() and rules.transition() take
#   expected_version (409 VERSION_MISMATCH when the rule was edited since);
#   rules.shadow_report() takes version (the report counts one revision and
#   returns ruleVersion and currentVersion). transition() documents 409
#   FEED_MISSING and FEED_NOT_REALTIME; cases.transition() documents that a
#   resolve records the outcome at once. The rule paths are constants
#   (FRAUD_RULE_BY_ID_PATH, ...).
# 2026-11-21  pending   Spec 03 PM-1: decide() / shadow_decide() document 400
#   CARD_NUMBER_REFUSED. Fix: they send the body the route reads,
#   {subject: {id, kind}, action, resource: {kind, id?}, context?} (they sent
#   flat subjectId / subjectKind / resourceKind, which the route refuses: every
#   call was a 400 BAD_REQUEST). The signatures are unchanged.
# 2026-11-20  v1.13.0  Re-review R4: rule_path fills through paths.fill_path
#   (one copy); an empty rule id, '.' or '..' raises ValueError before any
#   request.
# 2026-11-22  1.15.0 pending  Enterprise License: activate() documents billing
#   LICENSED and 403 LICENSE_REQUIRED (no request change).
# =============================================================================

"""Fraud Detection Engine — decide, screen, rules, lists, cases, devices,
terms, and federation push.

Covers Phase 6A through 6H of the Fraud Detection Engine:
  - decide / shadow_decide   (Phase 6A)
  - decisions (list / get)   (Phase 6A)
  - rules (CRUD, transition, shadow report)  (Phase 6B)
  - screen                   (Phase 6C)
  - lists + list entries     (Phase 6C)
  - devices.seen             (Phase 6D)
  - cases (list / get / open / update / transition)  (Phase 6E)
  - terms.status / terms.accept                       (Phase 6H)
  - activate                 (2026-11-07: turn the Detection Pack on)
  - federation.preview / federation.push              (Phase 6G)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from .paths import fill_path

if TYPE_CHECKING:
    from ..client import PlatformXeClient


def _decide_body(
    subject_id: str,
    subject_kind: str,
    action: str,
    resource_kind: str,
    resource_id: Optional[str],
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """The decide / shadow-decide body as the route reads it (nested subject and resource)."""
    resource: Dict[str, Any] = {"kind": resource_kind}
    if resource_id is not None:
        resource["id"] = resource_id
    body: Dict[str, Any] = {
        "subject": {"id": subject_id, "kind": subject_kind},
        "action": action,
        "resource": resource,
    }
    if context is not None:
        body["context"] = context
    return body


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
        """POST /api/v1/fraud/cases/{id}/transition with ``target`` and the
        optional ``resolution`` / ``note``.

        A case at an MLRO stage (``mlro``, ``sar_filed``, ``le_referred``)
        answers 409 ``CASE_AT_MLRO_STAGE`` for every transition: that decision
        is the MLRO desk's in the portal, and an API key holds no desk role. A
        transition not allowed from the current status, or one that lost a race
        to another change, is 409 ``CONFLICT``. Both raise PlatformXeAPIError.

        A transition to ``resolved`` records the case's outcome at once (as a
        portal close does), named ``api-key:<key id>``; a ``false_positive``
        close also withdraws the case's open recovery actions. The response is
        unchanged.
        """
        return self._client.post(
            f"/api/v1/fraud/cases/{case_id}/transition",
            json=payload,
        )


# The rule statuses and the moves POST /rules/{id}/transition allows
# (src/lib/services/fraud/rules: draft -> shadow | archived, shadow -> draft |
# published | archived, published -> archived; archived is terminal).
#
# DUPLICATION: mirrors TRANSITIONS in src/lib/services/fraud/rules/api.ts
# (caldera-platformxe), so callers can check a move before sending it.
# src/lib/api/sdk-fraud-rule-transitions.test.ts parses both and fails CI when
# they differ.
RULE_STATUSES = ("draft", "shadow", "published", "archived")
RULE_TRANSITIONS: Dict[str, Sequence[str]] = {
    "draft": ("shadow", "archived"),
    "shadow": ("draft", "published", "archived"),
    "published": ("archived",),
    "archived": (),
}


FRAUD_RULES_PATH = "/api/v1/fraud/rules"
FRAUD_RULE_BY_ID_PATH = "/api/v1/fraud/rules/{id}"
FRAUD_RULE_TRANSITION_PATH = "/api/v1/fraud/rules/{id}/transition"
FRAUD_RULE_SHADOW_REPORT_PATH = "/api/v1/fraud/rules/{id}/shadow-report"


def rule_path(template: str, rule_id: str) -> str:
    """A fraud-rule path with its ``{id}`` filled (paths.fill_path: URL-quoted;
    an empty id, '.' or '..' raises ValueError)."""
    return fill_path(template, id=rule_id)


class FraudRulesService:
    """Tenant fraud rules CRUD (Phase 6B)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(self, status: Optional[str] = None) -> Dict[str, Any]:
        params = {"status": status} if status else None
        return self._client.get(FRAUD_RULES_PATH, params=params)

    def get(self, rule_id: str) -> Dict[str, Any]:
        """The rule. Its ``version`` is its revision (it goes up on every
        PATCH that changes something): send it back as ``expected_version``."""
        return self._client.get(rule_path(FRAUD_RULE_BY_ID_PATH, rule_id))

    def create(self, **payload: Any) -> Dict[str, Any]:
        """409 ``CONFLICT`` when another rule in the organisation (any
        version or status) already has the name."""
        return self._client.post(FRAUD_RULES_PATH, json=payload)

    def update(self, rule_id: str, expected_version: Optional[int] = None, **payload: Any) -> Dict[str, Any]:
        """PATCH a draft or shadow rule; answers the rule with its new ``version``.

        With ``expected_version`` (the ``version`` you last read) the edit is
        written only while the rule is still at that revision: 409
        ``VERSION_MISMATCH`` otherwise, and nothing is written. A malformed
        field is 400 ``BAD_REQUEST``; a published or archived rule, a name
        another rule holds, or an edit that kept losing to concurrent edits
        is 409 ``CONFLICT``.
        """
        body: Dict[str, Any] = dict(payload)
        if expected_version is not None:
            body["expectedVersion"] = expected_version
        return self._client.patch(rule_path(FRAUD_RULE_BY_ID_PATH, rule_id), json=body)

    def transition(self, rule_id: str, target: str, expected_version: Optional[int] = None) -> Dict[str, Any]:
        """POST /api/v1/fraud/rules/{id}/transition with ``{"target": target}``.

        ``target`` is one of ``RULE_STATUSES``. The allowed moves are
        ``RULE_TRANSITIONS``: draft to shadow or archived; shadow to draft,
        published or archived; published to archived; archived is terminal.
        A move not allowed from the rule's status is 409 ``CONFLICT``, an
        unknown target 400 ``BAD_REQUEST``, a rule not found 404. Scope
        ``fraud:manage``; returns the rule.

        ``expected_version`` (1.13.0) is the revision you reviewed (the shadow
        report's ``ruleVersion``): the move goes through only while the rule is
        still at it, else 409 ``VERSION_MISMATCH`` and nothing changes.
        Publishing a rule that reads a feed the organisation has not sent
        recently is 409 ``FEED_MISSING``; one that needs a real-time payment
        feed where the pack's ``paymentFeed`` setting is not ``realtime`` is
        409 ``FEED_NOT_REALTIME``.
        """
        body: Dict[str, Any] = {"target": target}
        if expected_version is not None:
            body["expectedVersion"] = expected_version
        return self._client.post(rule_path(FRAUD_RULE_TRANSITION_PATH, rule_id), json=body)

    def draft(self, rule_id: str) -> Dict[str, Any]:
        """Move a shadow rule back to draft (``transition(rule_id, "draft")``)."""
        return self.transition(rule_id, "draft")

    def shadow(self, rule_id: str) -> Dict[str, Any]:
        """Move a draft rule to shadow: it is evaluated but never enforced."""
        return self.transition(rule_id, "shadow")

    def publish(self, rule_id: str) -> Dict[str, Any]:
        """Publish a shadow rule (``transition(rule_id, "published")``).

        Before 1.12.0 it posted to /rules/{id}/publish, which does not exist;
        it now sends the transition route. A draft rule must be moved to shadow first.
        """
        return self.transition(rule_id, "published")

    def archive(self, rule_id: str) -> Dict[str, Any]:
        """Archive a rule from any status but archived (terminal).

        Before 1.12.0 it posted to /rules/{id}/archive, which does not exist;
        it now sends the transition route.
        """
        return self.transition(rule_id, "archived")

    def shadow_report(
        self,
        rule_id: str,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/fraud/rules/{id}/shadow-report: the rule's trigger-rate
        metrics over a window, to check a shadow rule before publishing it.

        ``from_`` / ``to`` are ISO-8601 timestamps (default: the last 7 days);
        a timestamp that does not parse is 400. Scope ``fraud:manage``.
        The report counts one revision's decisions: the current one, or
        ``version`` (1.13.0; 400 unless a positive integer). ``ruleVersion``
        is the revision counted (publish it with ``expected_version``);
        ``currentVersion`` is the rule's version now.
        """
        params: Dict[str, str] = {}
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
        if version is not None:
            params["version"] = str(version)
        return self._client.get(
            rule_path(FRAUD_RULE_SHADOW_REPORT_PATH, rule_id),
            params=params or None,
        )


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

    # --- /activate (2026-11-07) ----------------------------------------

    def activate(self, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Turn the Detection Pack addon on for the key's own organisation.

        Idempotent: a pack already on answers ``alreadyActive: True`` and
        bills nothing again. Accept the terms next with ``terms.accept``.
        Returns ``detectionPackEnabled``, ``detectionPackEnabledAt``,
        ``alreadyActive``, ``billing``, ``invoiceId`` and ``firstParty``.
        ``billing`` is ``FIRST_PARTY_METERED``, ``PLAN_INCLUDED``,
        ``INVOICED``, ``DEMO_SEED``, ``LICENSED`` (under an Enterprise
        License: nothing invoiced here) or None when it was already on.
        Scope ``fraud:manage``.

        Errors: 402 ``ADDON_PLAN_REQUIRED`` / ``SUBSCRIPTION_REQUIRED``;
        403 ``FORBIDDEN``, or ``LICENSE_REQUIRED`` after the licensing
        cut-over when no live license grant names a fraud pack (1.15.0);
        404 ``NOT_FOUND``.
        """
        headers = {"x-idempotency-key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/fraud/activate", json={}, headers=headers)

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
        """Render a production verdict (``POST /api/v1/fraud/decide``, scope ``fraud:decide``).

        The body is ``{subject: {id, kind}, action, resource: {kind, id?}, context?}``.
        A request carrying a card number or a card field (``pan``, ``cvv`` ...)
        anywhere in the subject, action, resource or context (only
        ``context.amount.value`` skips the number test) raises ``PlatformXeAPIError`` with status 400 and code
        ``CARD_NUMBER_REFUSED``; nothing is decided or recorded, and the message
        names the path, never the value. Send a token, never card data.
        """
        body = _decide_body(subject_id, subject_kind, action, resource_kind, resource_id, context)
        # x-idempotency-key is what the route reads (withIdempotency); the
        # Idempotency-Key sent before v1.11.0 was ignored.
        headers = {"x-idempotency-key": idempotency_key} if idempotency_key else None
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
        """Render a non-enforcing verdict (``POST /api/v1/fraud/shadow-decide``).

        Same body as :meth:`decide`; refuses card data the same way (400
        ``CARD_NUMBER_REFUSED``).
        """
        body = _decide_body(subject_id, subject_kind, action, resource_kind, resource_id, context)
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
