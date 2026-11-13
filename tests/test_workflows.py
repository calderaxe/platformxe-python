# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-12  (pending)  caldera-platformxe Task 4 fix round 3 (I-1, NO-DRIFT):
#   the workflow step statuses (evaluate: SUCCESS / FAILED / SKIPPED /
#   DEFERRED; recorded executions: success / failed / skipped / deferred) are
#   exported, and an evaluate result item with no executionId (no execution
#   recorded) passes through as answered.
# 2026-11-12  (pending)  Task 4 fix round 4 (N3-I1): a recorded step is in
#   either spelling (the engine that ran it decides); normalize_workflow_status.
#   evaluate sends entityData (the route never read payload, which is kept as a
#   deprecated keyword alias) and the route's optional fields.
# =============================================================================

"""Contract tests for the workflow step statuses and the evaluate result."""

import json
import warnings
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import (
    AsyncPlatformXeClient,
    PlatformXeClient,
    WORKFLOW_ACTION_STATUSES,
    WORKFLOW_STEP_STATUSES,
    normalize_workflow_status,
)


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = {"content-type": "application/json"}
    body = {"success": True, "data": data}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def test_step_statuses_are_the_route_values():
    assert WORKFLOW_ACTION_STATUSES == ("SUCCESS", "FAILED", "SKIPPED", "DEFERRED")
    # A recorded execution stores either spelling (N3-I1).
    assert WORKFLOW_STEP_STATUSES == (
        "success", "failed", "skipped", "deferred",
        "SUCCESS", "FAILED", "SKIPPED", "DEFERRED",
    )


def test_normalize_workflow_status_accepts_both_spellings():
    for lower, upper in zip(WORKFLOW_STEP_STATUSES[:4], WORKFLOW_ACTION_STATUSES):
        assert normalize_workflow_status(lower) == upper
        assert normalize_workflow_status(upper) == upper


def test_evaluate_returns_deferred_steps_and_an_item_without_execution_id():
    data = {
        "matched": 2,
        "total": 2,
        "results": [
            {
                "triggerId": "trg_1", "triggerCode": "A", "triggerName": "A", "matched": True,
                "executionId": "exec_1",
                "actionsExecuted": [
                    {"type": "SEND_EMAIL", "config": {}, "status": "DEFERRED",
                     "error": "Not sent: the sending limit for this recipient was reached."},
                    {"type": "UNKNOWN", "config": {}, "status": "SKIPPED"},
                ],
            },
            {"triggerId": "trg_2", "triggerCode": "B", "triggerName": "B", "matched": True, "error": "x"},
        ],
    }
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(data)):
        result = client.workflows.evaluate("BOOKING_CREATED", {})
    statuses = [s["status"] for s in result["results"][0]["actionsExecuted"]]
    assert statuses == ["DEFERRED", "SKIPPED"]
    assert all(s in WORKFLOW_ACTION_STATUSES for s in statuses)
    assert "executionId" not in result["results"][1]
    client.close()


def _sent_body(client, **call):
    with patch.object(client._client, "request", return_value=_ok({"matched": 0, "results": []})) as req:
        client.workflows.evaluate("BOOKING_CREATED", **call)
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/workflows/evaluate")
    return kwargs["json"]


def test_evaluate_sends_entity_data_the_route_reads():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"matched": 0, "results": []})) as req:
        client.workflows.evaluate("BOOKING_CREATED", {"guestEmail": "a@b.com"})
    assert req.call_args[1]["json"] == {"eventType": "BOOKING_CREATED", "entityData": {"guestEmail": "a@b.com"}}
    client.close()


def test_evaluate_sends_the_optional_fields_when_given():
    client = PlatformXeClient(api_key="test")
    body = _sent_body(
        client, entity_data={"x": 1}, entity_type="BOOKING", entity_id="bk_1",
        source_app="lettings", metadata={"m": 1}, dry_run=True,
    )
    assert body == {
        "eventType": "BOOKING_CREATED", "entityData": {"x": 1}, "entityType": "BOOKING",
        "entityId": "bk_1", "sourceApp": "lettings", "metadata": {"m": 1}, "dryRun": True,
    }
    client.close()


def test_evaluate_payload_keyword_is_a_deprecated_alias_for_entity_data():
    client = PlatformXeClient(api_key="test")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        body = _sent_body(client, payload={"x": 1})
    assert body == {"eventType": "BOOKING_CREATED", "entityData": {"x": 1}}
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    with pytest.raises(TypeError):
        client.workflows.evaluate("BOOKING_CREATED", {"x": 1}, payload={"y": 2})
    client.close()


@pytest.mark.asyncio
async def test_async_evaluate_sends_the_same_body():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"matched": 0, "results": []})) as req:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await client.workflows.evaluate("BOOKING_CREATED", payload={"x": 1}, dry_run=True)
    assert req.call_args[1]["json"] == {"eventType": "BOOKING_CREATED", "entityData": {"x": 1}, "dryRun": True}
    await client.close()
