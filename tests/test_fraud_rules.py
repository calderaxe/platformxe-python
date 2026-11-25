# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-18  Initial (1.12.0): every rule status change posts to
#   /api/v1/fraud/rules/{id}/transition {target}; shadow_report reads
#   /api/v1/fraud/rules/{id}/shadow-report; a case at an MLRO stage raises
#   409 CASE_AT_MLRO_STAGE.

"""fraud.rules: transition, the status helpers and the shadow report."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import PlatformXeClient
from platformxe.exceptions import PlatformXeAPIError
from platformxe.services.fraud import RULE_STATUSES, RULE_TRANSITIONS


def _resp(status, body):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def _ok(data):
    return _resp(200, {"success": True, "data": data})


RULE = {"id": "frl_1", "status": "shadow", "version": 2}


@pytest.mark.parametrize(
    "method,target",
    [
        ("draft", "draft"),
        ("shadow", "shadow"),
        ("publish", "published"),
        ("archive", "archived"),
    ],
)
def test_status_helpers_post_to_the_transition_route(method, target):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        getattr(client.fraud.rules, method)("frl_1")
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1] == "/api/v1/fraud/rules/frl_1/transition"
    assert kwargs["json"] == {"target": target}
    client.close()


def test_transition_sends_the_target():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        result = client.fraud.rules.transition("frl_1", "shadow")
    assert req.call_args.kwargs["json"] == {"target": "shadow"}
    assert result["status"] == "shadow"
    client.close()


def test_no_helper_calls_the_routes_that_do_not_exist():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        client.fraud.rules.publish("frl_1")
        client.fraud.rules.archive("frl_1")
    paths = [c.args[1] for c in req.call_args_list]
    assert not any(p.endswith("/publish") or p.endswith("/archive") for p in paths)
    client.close()


def test_a_transition_not_allowed_raises_409_conflict():
    client = PlatformXeClient(api_key="test")
    refusal = _resp(409, {"success": False, "error": {
        "code": "CONFLICT", "message": "Transition not allowed from current status"}})
    with patch.object(client._client, "request", return_value=refusal) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.fraud.rules.publish("frl_1")
    assert exc.value.status_code == 409
    assert exc.value.code == "CONFLICT"
    assert req.call_count == 1
    client.close()


def test_transition_table_matches_the_api():
    assert RULE_STATUSES == ("draft", "shadow", "published", "archived")
    assert tuple(RULE_TRANSITIONS["draft"]) == ("shadow", "archived")
    assert tuple(RULE_TRANSITIONS["shadow"]) == ("draft", "published", "archived")
    assert tuple(RULE_TRANSITIONS["published"]) == ("archived",)
    assert tuple(RULE_TRANSITIONS["archived"]) == ()


def test_shadow_report_reads_the_route_with_the_window():
    client = PlatformXeClient(api_key="test")
    report = {"ruleId": "frl_1", "evaluated": 10, "triggered": 2}
    with patch.object(client._client, "request", return_value=_ok(report)) as req:
        client.fraud.rules.shadow_report("frl_1", from_="2026-11-01T00:00:00Z", to="2026-11-08T00:00:00Z")
    args, kwargs = req.call_args
    assert args[0] == "GET"
    assert args[1] == "/api/v1/fraud/rules/frl_1/shadow-report"
    assert kwargs["params"] == {"from": "2026-11-01T00:00:00Z", "to": "2026-11-08T00:00:00Z"}
    client.close()


def test_shadow_report_without_a_window_sends_no_params():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({})) as req:
        client.fraud.rules.shadow_report("frl_1")
    assert req.call_args.kwargs["params"] is None
    client.close()


def test_case_transition_at_an_mlro_stage_raises_case_at_mlro_stage():
    client = PlatformXeClient(api_key="test")
    refusal = _resp(409, {"success": False, "error": {
        "code": "CASE_AT_MLRO_STAGE", "message": "The case is at an MLRO stage"}})
    with patch.object(client._client, "request", return_value=refusal):
        with pytest.raises(PlatformXeAPIError) as exc:
            client.fraud.cases.transition("fc_1", target="resolved", resolution="false_positive")
    assert exc.value.code == "CASE_AT_MLRO_STAGE"
    assert exc.value.status_code == 409
    client.close()


# -- 1.13.0: revisions (expectedVersion, shadow report version) ---------------


def test_transition_sends_expected_version_when_given():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        client.fraud.rules.transition("frl_1", "published", expected_version=4)
    args, kwargs = req.call_args
    assert args[1] == "/api/v1/fraud/rules/frl_1/transition"
    assert kwargs["json"] == {"target": "published", "expectedVersion": 4}
    client.close()


def test_update_sends_expected_version_beside_the_fields():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        client.fraud.rules.update("frl_1", expected_version=2, weight=20)
        client.fraud.rules.update("frl_1", weight=30)
    first, second = req.call_args_list
    assert first.args[:2] == ("PATCH", "/api/v1/fraud/rules/frl_1")
    assert first.kwargs["json"] == {"weight": 20, "expectedVersion": 2}
    assert second.kwargs["json"] == {"weight": 30}
    client.close()


@pytest.mark.parametrize("code", ["VERSION_MISMATCH", "FEED_MISSING", "FEED_NOT_REALTIME"])
def test_a_transition_409_raises_with_its_code_once(code):
    client = PlatformXeClient(api_key="test")
    refusal = _resp(409, {"success": False, "error": {"code": code, "message": "refused"}})
    with patch.object(client._client, "request", return_value=refusal) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.fraud.rules.transition("frl_1", "published", expected_version=3)
    assert exc.value.code == code
    assert exc.value.status_code == 409
    assert req.call_count == 1
    client.close()


def test_shadow_report_sends_the_version():
    client = PlatformXeClient(api_key="test")
    report = {"ruleId": "frl_1", "ruleVersion": 3, "currentVersion": 4}
    with patch.object(client._client, "request", return_value=_ok(report)) as req:
        result = client.fraud.rules.shadow_report("frl_1", version=3)
    assert req.call_args.kwargs["params"] == {"version": "3"}
    assert result["currentVersion"] == 4
    client.close()


def test_rule_ids_are_url_quoted():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(RULE)) as req:
        client.fraud.rules.get("a/b")
    assert req.call_args.args[1] == "/api/v1/fraud/rules/a%2Fb"
    client.close()
