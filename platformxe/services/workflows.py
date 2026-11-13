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
"""

from __future__ import annotations
import warnings
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

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


class WorkflowsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/workflows")

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        return self._client.post("/api/v1/workflows", json=kwargs)

    def get(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/workflows/{workflow_id}")

    def update(self, workflow_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/workflows/{workflow_id}", json=kwargs)

    def delete(self, workflow_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/workflows/{workflow_id}")

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
        """Evaluate an event. entity_data is what the triggers' conditions and templates read
        (payload= is its deprecated name). Each result item's actionsExecuted[].status is one of
        WORKFLOW_ACTION_STATUSES; an item with no executionId recorded no execution."""
        body = evaluate_request_body(
            event_type, entity_data, payload=payload, entity_type=entity_type, entity_id=entity_id,
            source_app=source_app, metadata=metadata, dry_run=dry_run,
        )
        return self._client.post("/api/v1/workflows/evaluate", json=body)

    def dry_run(self, workflow_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Dry-run a trigger against a context (no side effects)."""
        return self._client.post(f"/api/v1/workflows/{workflow_id}/dry-run", json=context)
