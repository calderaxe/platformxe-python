# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Workflows service — event-driven automation.

CHANGELOG:
2026-11-12  (pending)  Task 4 fix round 3 (I-1, NO-DRIFT): the step statuses.
  An evaluate result's actionsExecuted[].status is one of
  WORKFLOW_ACTION_STATUSES; a recorded execution's actionsExecuted[].status is
  one of WORKFLOW_STEP_STATUSES. DEFERRED / deferred: an email declined for
  capacity (not retried, never counted toward auto-disable). An evaluate result
  item has no executionId when no execution could be recorded (error is set).
2026-11-12  (pending)  Task 4 fix round 4 (N3-I1): a recorded execution's steps
  are in the spelling of the engine that ran it (upper case for /evaluate and
  the event relay, lower case for event and scheduled runs), so
  WORKFLOW_STEP_STATUSES holds both and normalize_workflow_status() upper-cases
  either. evaluate() sends entityData, the field the route reads (it sent
  payload, which the route ignored, so no trigger saw the event data); payload
  stays a deprecated keyword alias. It also sends entityType, entityId,
  sourceApp, metadata and dryRun when given (evaluate_request_body, shared with
  the async client).
2026-11-20  (1.13.0, pending)  Fidelity register fix: dry_run posted to
  /api/v1/workflows/{id}/dry-run, which does not exist (every call was a 404).
  The dry run is POST /api/v1/workflows/{id} with {entityData}; dry_run now
  posts there (dry_run_request_body, shared with the async client) and takes
  entity_data=. A context dict is still accepted: its entityData (or the
  documented payload) is sent as entityData, or the whole dict when it has
  neither. The route ignores eventType. The answer is {"dryRun": {...}}.
2026-11-20  (1.13.0, pending)  Fix round (review L1, L2): a context is the
  entity data except in two shapes: the old {eventType, payload} context
  sends payload, and a dict whose only key (besides eventType) is entityData
  sends entityData (any payload key was unwrapped before, dropping the rest
  of raw entity data). The Go SDK reads it the same way. The trigger id is
  URL-quoted (workflow_path) for get / update / delete / dry_run, and an
  empty id raises ValueError before any request.
2026-11-20  (1.13.0, pending)  Re-review (R2, R4): a context is unwrapped when
  every key is a trigger-context key (TRIGGER_CONTEXT_KEYS: the route's
  TriggerContext fields plus payload, sourceApp and dryRun) and it carries an
  entityData or payload object; the {eventType, entityType, entityId,
  entityData} shape was nested by the narrower rule. The id is filled by
  events.py's _fill (the hand-written workflow_path copy is gone);
  require_workflow_id refuses an empty id.
2026-11-20  (1.13.0, pending)  Re-review R4, R5, N-R1: the id is filled by
  paths.fill_path (events.py's private _fill is gone), which also refuses '.'
  and '..'. list() takes page, limit, is_active, trigger_type and event_type
  (the GET route's query; list_query_params, shared with the async client): it
  could only reach the first page. update() documents what the PATCH route now
  takes (code, triggerType, eventType, entityType; None-valued keys clear).
2026-11-22  (1.14.1, pending)  Docs only: evaluate()'s entity_data is your own
  parameters for the event (the custom-parameters object the triggers'
  conditions and templates read); for a business event type PlatformXe
  defines no fields. Optional: {} is sent as {}, None is omitted (the route
  also accepts null). event_type is one of the values on
  https://docs.platformxe.com/services/workflows/event-types.
"""

from __future__ import annotations
import warnings
from typing import Any, Dict, FrozenSet, Optional, Tuple, TYPE_CHECKING

from .paths import fill_path

if TYPE_CHECKING:
    from ..client import PlatformXeClient

#: actionsExecuted[].status in a POST /api/v1/workflows/evaluate result.
WORKFLOW_ACTION_STATUSES: Tuple[str, ...] = ("SUCCESS", "FAILED", "SKIPPED", "DEFERRED")

#: actionsExecuted[].status in a recorded workflow execution: lower case for an
#: event or scheduled run, upper case for a run recorded by /evaluate or the relay.
WORKFLOW_STEP_STATUSES: Tuple[str, ...] = (
    "success", "failed", "skipped", "deferred",
    "SUCCESS", "FAILED", "SKIPPED", "DEFERRED",
)


def normalize_workflow_status(status: str) -> str:
    """A step status in either spelling, as one of WORKFLOW_ACTION_STATUSES."""
    return status.upper()


def evaluate_request_body(
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
    """The POST /api/v1/workflows/evaluate body. payload is the deprecated name of entity_data."""
    if payload is not None:
        if entity_data is not None:
            raise TypeError("pass entity_data or payload (deprecated), not both")
        warnings.warn(
            "workflows.evaluate(payload=...) is deprecated; pass entity_data (sent as entityData)",
            DeprecationWarning,
            stacklevel=3,
        )
        entity_data = payload
    body: Dict[str, Any] = {"eventType": event_type}
    optional = {
        "entityData": entity_data,
        "entityType": entity_type,
        "entityId": entity_id,
        "sourceApp": source_app,
        "metadata": metadata,
        "dryRun": dry_run,
    }
    body.update({k: v for k, v in optional.items() if v is not None})
    return body


#: A trigger's route; paths.fill_path fills {id} (URL-quoted).
WORKFLOW_BY_ID_PATH = "/api/v1/workflows/{id}"

#: The keys of a trigger context: the route's TriggerContext fields
#: (src/lib/services/workflow/types.ts) plus payload (the old name of
#: entityData), sourceApp and dryRun (evaluate request fields). The Go SDK's
#: triggerContextKeys is the same set.
TRIGGER_CONTEXT_KEYS: FrozenSet[str] = frozenset({
    "eventType", "entityType", "entityId", "entityData", "metadata",
    "organizationId", "callerService", "payload", "sourceApp", "dryRun",
})


def require_workflow_id(workflow_id: str) -> str:
    """The id as given; an empty id raises ValueError before any request."""
    if not workflow_id:
        raise ValueError("workflow_id is required")
    return workflow_id


#: The workflow trigger list route (GET; POST creates).
WORKFLOWS_PATH = "/api/v1/workflows"


def list_query_params(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    is_active: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    event_type: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """The GET /api/v1/workflows query: page and limit (each from 1; the route
    caps limit at 100) when > 0, isActive as "true" / "false", triggerType
    (EVENT or SCHEDULE) and eventType when given. None when nothing is set
    (the route answers page 1, 50 per page). The route answers 400
    VALIDATION_ERROR for an unknown trigger or event type."""
    params: Dict[str, str] = {}
    if page is not None and page > 0:
        params["page"] = str(page)
    if limit is not None and limit > 0:
        params["limit"] = str(limit)
    if is_active is not None:
        params["isActive"] = "true" if is_active else "false"
    if trigger_type:
        params["triggerType"] = trigger_type
    if event_type:
        params["eventType"] = event_type
    return params or None


def dry_run_request_body(
    context: Optional[Dict[str, Any]] = None,
    entity_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The POST /api/v1/workflows/{id} (dry run) body: {"entityData": ...}.

    entity_data is sent as it is. A context dict (the earlier signature) is a
    trigger context when every key is in TRIGGER_CONTEXT_KEYS and it carries an
    entityData (else payload) dict: that dict is sent. Any other dict is the
    entity data, sent whole (raw data with its own payload field included).
    The route does not read eventType. The Go SDK's DryRun reads a context the
    same way."""
    if entity_data is not None:
        if context is not None:
            raise TypeError("pass entity_data or context, not both")
        return {"entityData": entity_data}
    if context is None:
        return {"entityData": {}}
    if set(context) <= TRIGGER_CONTEXT_KEYS:
        for key in ("entityData", "payload"):
            if isinstance(context.get(key), dict):
                return {"entityData": context[key]}
    return {"entityData": context}


class WorkflowsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        is_active: Optional[bool] = None,
        trigger_type: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """A page of the caller's triggers: {"triggers": [...], "pagination":
        {"page", "limit", "total"}}. With no arguments, the first page of every
        trigger; total counts every match, so page on until page * limit >= total."""
        params = list_query_params(page, limit, is_active, trigger_type, event_type)
        return self._client.get(WORKFLOWS_PATH, params=params)

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        return self._client.post(WORKFLOWS_PATH, json=kwargs)

    def get(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.get(fill_path(WORKFLOW_BY_ID_PATH, id=require_workflow_id(workflow_id)))

    def update(self, workflow_id: str, **kwargs: Any) -> Dict[str, Any]:
        """PATCH /api/v1/workflows/{id} with the given fields (camelCase, as the
        route reads them): name, description, code, triggerType, eventType,
        entityType, cronExpression, conditions, actions, isActive, priority,
        cooldownMinutes, maxExecutionsDay. A None value clears a nullable field.
        A code another trigger holds raises 409 DUPLICATE; sourceApp is accepted
        only as the calling service (a trigger never moves between apps)."""
        return self._client.patch(fill_path(WORKFLOW_BY_ID_PATH, id=require_workflow_id(workflow_id)), json=kwargs)

    def delete(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.delete(fill_path(WORKFLOW_BY_ID_PATH, id=require_workflow_id(workflow_id)))

    def evaluate(
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
        """Evaluate an event. event_type is one of the values on
        https://docs.platformxe.com/services/workflows/event-types (any other is 400
        VALIDATION_ERROR). entity_data is your own parameters for the event: what the triggers'
        conditions and templates read; for a business event type PlatformXe defines no fields.
        It is optional: {} is sent as {}, None is omitted (payload= is its deprecated name).
        Each result item's actionsExecuted[].status is one of WORKFLOW_ACTION_STATUSES; an item
        with no executionId recorded no execution."""
        body = evaluate_request_body(
            event_type, entity_data, payload=payload, entity_type=entity_type, entity_id=entity_id,
            source_app=source_app, metadata=metadata, dry_run=dry_run,
        )
        return self._client.post("/api/v1/workflows/evaluate", json=body)

    def dry_run(
        self,
        workflow_id: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        entity_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dry-run one trigger against entity data (no actions run): POST /api/v1/workflows/{id}.
        Returns {"dryRun": {wouldMatch, conditionsEvaluated, actionsWouldExecute, ...}}."""
        body = dry_run_request_body(context, entity_data)
        return self._client.post(fill_path(WORKFLOW_BY_ID_PATH, id=require_workflow_id(workflow_id)), json=body)
