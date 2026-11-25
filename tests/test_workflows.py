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
# 2026-11-20  (1.13.0, pending)  Re-review R5, N-R1: list() takes page, limit,
#   is_active, trigger_type and event_type (the query string is pinned, sync
#   and async); '.' and '..' are refused as ids, like an empty id.
# 2026-11-22  (1.14.1, pending)  evaluate's entity_data, the custom-parameters
#   object: an empty dict is sent as {}, None is omitted.
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


# -- Dry run (fidelity register, 2026-11-20): POST /api/v1/workflows/{id} -----

_DRY = {"dryRun": {"wouldMatch": True, "conditionsEvaluated": {}, "actionsWouldExecute": []}}


def _dry_run_call(client, *args, **kwargs):
    with patch.object(client._client, "request", return_value=_ok(_DRY)) as req:
        result = client.workflows.dry_run("trg_1", *args, **kwargs)
    return req.call_args, result


def test_dry_run_posts_to_the_trigger_route_not_a_dry_run_path():
    client = PlatformXeClient(api_key="test")
    (args, kwargs), result = _dry_run_call(client, entity_data={"amount": 5})
    assert args == ("POST", "/api/v1/workflows/trg_1")
    assert kwargs["json"] == {"entityData": {"amount": 5}}
    assert result == _DRY
    client.close()


def test_dry_run_reads_entity_data_from_a_context_dict():
    client = PlatformXeClient(api_key="test")
    for context, sent in [
        ({"entityData": {"a": 1}}, {"a": 1}),
        ({"eventType": "INVOICE_PAID", "entityData": {"a": 1}}, {"a": 1}),
        ({"eventType": "INVOICE_PAID", "payload": {"b": 2}}, {"b": 2}),
        # The standard trigger context is unwrapped (re-review R2).
        ({"eventType": "INVOICE_PAID", "entityType": "INVOICE", "entityId": "inv_1", "entityData": {"amount": 250000}},
         {"amount": 250000}),
        ({"eventType": "X", "sourceApp": "lettings", "metadata": {"m": 1}, "payload": {"b": 2}}, {"b": 2}),
        ({"c": 3}, {"c": 3}),
        # Raw entity data with its own payload / entityData field is sent whole (L1).
        ({"status": "FAILED", "payload": {"id": "x"}}, {"status": "FAILED", "payload": {"id": "x"}}),
        ({"status": "FAILED", "entityData": {"id": "x"}}, {"status": "FAILED", "entityData": {"id": "x"}}),
        ({"eventType": "X", "payload": "not-an-object"}, {"eventType": "X", "payload": "not-an-object"}),
    ]:
        (args, kwargs), _ = _dry_run_call(client, context)
        assert args == ("POST", "/api/v1/workflows/trg_1")
        assert kwargs["json"] == {"entityData": sent}
    (args, kwargs), _ = _dry_run_call(client)
    assert kwargs["json"] == {"entityData": {}}
    with pytest.raises(TypeError):
        client.workflows.dry_run("trg_1", {"a": 1}, entity_data={"b": 2})
    client.close()


@pytest.mark.asyncio
async def test_async_dry_run_posts_the_same_request():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_DRY)) as req:
        result = await client.workflows.dry_run("trg_1", {"eventType": "INVOICE_PAID", "payload": {"b": 2}})
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/workflows/trg_1")
    assert kwargs["json"] == {"entityData": {"b": 2}}
    assert result == _DRY
    await client.close()


def test_workflow_ids_are_quoted_and_an_empty_id_is_refused():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_DRY)) as req:
        client.workflows.dry_run("a/b?c", entity_data={})
        assert req.call_args[0] == ("POST", "/api/v1/workflows/a%2Fb%3Fc")
        client.workflows.get("a/b")
        assert req.call_args[0] == ("GET", "/api/v1/workflows/a%2Fb")
        client.workflows.update("a/b", name="n")
        assert req.call_args[0] == ("PATCH", "/api/v1/workflows/a%2Fb")
        client.workflows.delete("a/b")
        assert req.call_args[0] == ("DELETE", "/api/v1/workflows/a%2Fb")
        calls = req.call_count
        for call in (
            lambda: client.workflows.dry_run("", entity_data={}),
            lambda: client.workflows.get(""),
            lambda: client.workflows.update("", name="n"),
            lambda: client.workflows.delete(""),
        ):
            with pytest.raises(ValueError):
                call()
        assert req.call_count == calls
    client.close()


@pytest.mark.asyncio
async def test_async_workflow_ids_are_quoted_and_an_empty_id_is_refused():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_DRY)) as req:
        await client.workflows.get("a/b")
        assert req.call_args[0] == ("GET", "/api/v1/workflows/a%2Fb")
        with pytest.raises(ValueError):
            await client.workflows.dry_run("", entity_data={})
        assert req.call_count == 1
    await client.close()


# -- List (re-review R5): page, limit and the route's filters ----------------

_LIST = {"triggers": [{"id": "trg_2"}], "pagination": {"page": 2, "limit": 1, "total": 3}}


@pytest.mark.parametrize("call, params", [
    ({}, None),
    ({"page": 0, "limit": 0}, None),
    ({"page": 2, "limit": 1}, {"page": "2", "limit": "1"}),
    ({"is_active": False}, {"isActive": "false"}),
    (
        {"page": 3, "limit": 25, "is_active": True, "trigger_type": "EVENT", "event_type": "BOOKING_CREATED"},
        {"page": "3", "limit": "25", "isActive": "true", "triggerType": "EVENT", "eventType": "BOOKING_CREATED"},
    ),
])
def test_list_sends_the_page_and_filters_the_route_reads(call, params):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_LIST)) as req:
        result = client.workflows.list(**call)
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/workflows")
    assert kwargs["params"] == params
    assert result == _LIST
    client.close()


@pytest.mark.asyncio
async def test_async_list_sends_the_same_query():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_LIST)) as req:
        await client.workflows.list(page=2, limit=10, is_active=True, trigger_type="SCHEDULE", event_type="INVOICE_PAID")
        assert req.call_args[0] == ("GET", "/api/v1/workflows")
        assert req.call_args[1]["params"] == {
            "page": "2", "limit": "10", "isActive": "true", "triggerType": "SCHEDULE", "eventType": "INVOICE_PAID",
        }
        await client.workflows.list()
        assert req.call_args[1]["params"] is None
    await client.close()


def test_dot_segment_ids_are_refused_before_any_request():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_DRY)) as req:
        for bad in (".", ".."):
            with pytest.raises(ValueError):
                client.workflows.get(bad)
            with pytest.raises(ValueError):
                client.workflows.dry_run(bad, entity_data={})
        assert req.call_count == 0
    client.close()


def test_evaluate_entity_data_empty_dict_is_sent_and_none_is_omitted():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"matched": 0, "results": []})) as req:
        client.workflows.evaluate("SERVICE_REQUESTED", {})
        client.workflows.evaluate("SERVICE_REQUESTED", None)
    first, second = (c[1]["json"] for c in req.call_args_list)
    assert first == {"eventType": "SERVICE_REQUESTED", "entityData": {}}
    assert second == {"eventType": "SERVICE_REQUESTED"}
    client.close()
