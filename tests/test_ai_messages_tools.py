# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-22  v1.16.0  (pending) Created (AI gateway T4, NO-DRIFT). Contract
#   tests for ai.messages (POST /api/v1/ai/messages), ai_tools.list
#   (GET /api/v1/ai/tools) and toolsets on ai.complete, sync and async,
#   against tests/fixtures/ai_vision.json (identical copy in
#   packages/sdk-go/testdata/). Each pins the method, path and exact camelCase
#   body, the passthrough of the answer, the model-call options (155 s, never
#   retried) and the new error envelopes (code, status, details, retry_after).
#   T5: AI_BUDGET_EXCEEDED with details.reason BUDGET_UNAVAILABLE and the
#   tool-loop refusal without a period; complete's model is the gateway slug.
# 2026-11-23  v1.18.0  (pending) AI gateway P6: ``actors`` sent as given (an
#   entry's missing permissions as []); never with ``actor`` (ValueError).
# 2026-11-23  v1.17.0  (pending) AI gateway P5: ``actor`` sent as is under its
#   wire name, sync and async; absent when not given.
# =============================================================================

"""Contract tests for the native messages route, the platform tools list and toolsets."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeAPIError, PlatformXeClient
from platformxe.services.ai import build_messages_body

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "ai_vision.json").read_text(encoding="utf-8"))


def _response(status_code, body, headers=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = {"content-type": "application/json", **(headers or {})}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK" if resp.is_success else "Error"
    return resp


def _ok(data):
    return _response(200, {"success": True, "data": data})


def _error(name):
    fixture = FIXTURES[name]
    return _response(fixture["status"], fixture["body"], fixture["headers"])


def _messages_kwargs(req):
    return dict(
        feature_key=req["featureKey"],
        messages=req["messages"],
        model=req["model"],
        system=req["system"],
        effort=req["effort"],
        toolsets=req["toolsets"],
        tool_choice=req["toolChoice"],
        max_tokens=req["maxTokens"],
    )


class TestAiMessages:
    def test_sends_the_fixture_request_and_returns_the_reply(self):
        req = FIXTURES["messagesRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["messagesResult"])) as mock_req:
            result = client.ai.messages(**_messages_kwargs(req))
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/messages")
        assert kwargs["json"] == req
        assert kwargs["timeout"] == 155.0
        assert result == FIXTURES["messagesResult"]
        assert result["toolRuns"][0]["status"] == "OK"
        client.close()

    def test_sends_only_the_required_fields_when_nothing_else_is_given(self):
        body = build_messages_body("ops-assistant", [{"role": "user", "content": "hi"}])
        assert body == {"featureKey": "ops-assistant", "messages": [{"role": "user", "content": "hi"}]}

    def test_sends_the_actor_as_given_and_only_when_given(self):
        actor = {"ref": "adm_123", "permissions": ["CN:ISSUES:VIEW"], "grant": "Z3JhbnQ"}
        body = build_messages_body("desk-brief", [], toolsets=["concierge.desk-read"], actor=actor)
        assert body["actor"] == actor
        assert body["toolsets"] == ["concierge.desk-read"]
        assert "actor" not in build_messages_body("f", [])

    def test_actor_without_permissions_is_sent_with_an_empty_list_never_null(self):
        for actor in ({"ref": "adm_1"}, {"ref": "adm_1", "permissions": None}):
            body = build_messages_body("desk-brief", [], actor=actor)
            assert body["actor"]["permissions"] == []
            assert "permissions" not in actor or actor["permissions"] is None  # the caller's dict is unchanged

    def test_sends_actors_as_given_and_only_when_given(self):
        actors = {
            "lettings": {"ref": "adm_l1", "permissions": ["LT:BOOKINGS:VIEW"], "grant": "bGV0"},
            "xadmin": {"ref": "usr_1", "permissions": ["XA:HR:VIEW"], "grant": "eGE"},
        }
        body = build_messages_body("ai-canvas", [], toolsets=["lettings.desk-read"], actors=actors)
        assert body["actors"] == actors
        assert "actor" not in body
        assert "actors" not in build_messages_body("f", [])

    def test_actors_entry_without_permissions_is_sent_with_an_empty_list(self):
        entry = {"ref": "adm_l1", "grant": "bGV0"}
        body = build_messages_body("ai-canvas", [], actors={"lettings": entry})
        assert body["actors"]["lettings"]["permissions"] == []
        assert "permissions" not in entry  # the caller's dict is unchanged

    def test_actor_and_actors_together_raise(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            build_messages_body("f", [], actor={"ref": "a", "permissions": []}, actors={"chats": {"ref": "b", "permissions": [], "grant": "g"}})

    def test_messages_passes_actors_sync_and_async(self):
        actors = {"chats": {"ref": "ops", "permissions": ["CH:CHAT_SESSION:VIEW"], "grant": "Y2g"}}
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request") as mock_req:
            mock_req.return_value = httpx.Response(200, json={"success": True, "data": {}}, request=httpx.Request("POST", "http://x"))
            client.ai.messages("ai-canvas", [{"role": "user", "content": "hi"}], actors=actors)
            assert mock_req.call_args.kwargs["json"]["actors"] == actors
        client.close()

        import asyncio

        async def run() -> None:
            ac = AsyncPlatformXeClient(api_key="test")
            with patch.object(ac._client, "request") as areq:
                async def ok(*a: object, **k: object) -> httpx.Response:
                    return httpx.Response(200, json={"success": True, "data": {}}, request=httpx.Request("POST", "http://x"))
                areq.side_effect = ok
                await ac.ai.messages("ai-canvas", [], actors=actors)
                assert areq.call_args.kwargs["json"]["actors"] == actors
            await ac.close()

        asyncio.run(run())

    def test_messages_passes_the_actor_sync_and_async(self):
        actor = {"ref": "adm_1", "permissions": ["CN:REQUESTS:VIEW"]}
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request") as mock_req:
            mock_req.return_value = httpx.Response(200, json={"success": True, "data": {}}, request=httpx.Request("POST", "http://x"))
            client.ai.messages("desk-brief", [{"role": "user", "content": "hi"}], actor=actor)
            assert mock_req.call_args.kwargs["json"]["actor"] == actor
        client.close()

        import asyncio

        async def run() -> None:
            ac = AsyncPlatformXeClient(api_key="test")
            with patch.object(ac._client, "request") as areq:
                async def ok(*a: object, **k: object) -> httpx.Response:
                    return httpx.Response(200, json={"success": True, "data": {}}, request=httpx.Request("POST", "http://x"))
                areq.side_effect = ok
                await ac.ai.messages("desk-brief", [], actor=actor)
                assert areq.call_args.kwargs["json"]["actor"] == actor
            await ac.close()

        asyncio.run(run())

    def test_sends_tools_and_output_schema_under_their_wire_names(self):
        tool = {"name": "lookup", "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}}
        schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        body = build_messages_body("f", [], tools=[tool], output_schema=schema)
        assert body["tools"] == [tool]
        assert body["outputSchema"] == schema
        assert "output_schema" not in body

    def test_is_never_retried(self):
        client = PlatformXeClient(api_key="test", retries=2, fail_open=True)
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("slow")) as mock_req:
            with pytest.raises(Exception):
                client.ai.messages(feature_key="ops-assistant", messages=[{"role": "user", "content": "hi"}])
        assert mock_req.call_count == 1
        client.close()

    @pytest.mark.parametrize("name,status,code,details", [
        ("refusedError", 422, "AI_REFUSED", {"category": "cyber"}),
        ("loopLimitError", 422, "AI_LOOP_LIMIT", {"reason": "TURNS"}),
        ("toolsetDeniedError", 403, "AI_TOOLSET_DENIED", {"reason": "NOT_ALLOWED"}),
        ("toolFailedError", 502, "AI_TOOL_FAILED", None),
    ])
    def test_new_closed_codes_surface(self, name, status, code, details):
        client = PlatformXeClient(api_key="test", fail_open=False, retries=2)
        with patch.object(client._client, "request", return_value=_error(name)) as mock_req:
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.messages(feature_key="ops-assistant", messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.code == code
        assert exc_info.value.status_code == status
        assert exc_info.value.details == details
        assert mock_req.call_count == 1
        client.close()

    def test_budget_exceeded_carries_retry_after_and_period(self):
        client = PlatformXeClient(api_key="test", fail_open=False, retries=2)
        with patch.object(client._client, "request", return_value=_error("budgetExceededError")) as mock_req:
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.messages(feature_key="ops-assistant", messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.code == "AI_BUDGET_EXCEEDED"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 52200
        assert exc_info.value.details == {"period": "DAY", "retryAfterSeconds": 52200}
        assert mock_req.call_count == 1
        client.close()

    @pytest.mark.parametrize("details", [
        {"period": "MONTH", "retryAfterSeconds": 60, "reason": "BUDGET_UNAVAILABLE"},
        {"retryAfterSeconds": 60},
    ])
    def test_budget_unavailable_and_loop_refusal_details(self, details):
        # The budget could not be checked (reason BUDGET_UNAVAILABLE), and the tool
        # loop's own refusal (no period): both final, Retry-After 60.
        body = {"success": False, "error": {"code": "AI_BUDGET_EXCEEDED", "message": "budget", "details": details}}
        client = PlatformXeClient(api_key="test", fail_open=False, retries=2)
        with patch.object(client._client, "request", return_value=_response(429, body, {"Retry-After": "60"})) as mock_req:
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.messages(feature_key="ops-assistant", messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.code == "AI_BUDGET_EXCEEDED"
        assert exc_info.value.retry_after == 60
        assert exc_info.value.details == details
        assert exc_info.value.details.get("period") == details.get("period")
        assert mock_req.call_count == 1
        client.close()


class TestCompleteWithToolsets:
    def test_sends_toolsets_and_returns_tool_runs(self):
        req = FIXTURES["completeWithToolsetsRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeWithToolsetsResult"])) as mock_req:
            result = client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
                model=req["model"], toolsets=req["toolsets"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/complete")
        assert kwargs["json"] == req
        assert result["toolRuns"][0]["denyReason"] == "DATA_CLASS"
        client.close()

    def test_omits_toolsets_when_not_given(self):
        req = FIXTURES["completeRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            client.ai.complete(feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"])
        assert "toolsets" not in mock_req.call_args.kwargs["json"]
        client.close()

    def test_profile_answers_the_governance_fields(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["profileView"])):
            view = client.ai.profile("guest-concierge")
        assert view["maxEffort"] == "medium"
        assert view["maxToolTurns"] == 8
        assert view["fallbackModel"] is None
        client.close()


class TestAiTools:
    def test_namespace_present(self):
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client.ai_tools, "list", None))
        client.close()

    def test_list_gets_the_route_and_returns_the_list(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["toolList"])) as mock_req:
            result = client.ai_tools.list()
        args, kwargs = mock_req.call_args
        assert args == ("GET", "/api/v1/ai/tools")
        assert kwargs.get("json") is None
        assert result == FIXTURES["toolList"]
        client.close()

    def test_missing_scope_is_forbidden(self):
        client = PlatformXeClient(api_key="test", fail_open=False)
        resp = _response(403, {"success": False, "error": {"code": "FORBIDDEN", "message": "Missing scope"}})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai_tools.list()
        assert exc_info.value.code == "FORBIDDEN"
        assert exc_info.value.status_code == 403
        client.close()


class TestAsync:
    @pytest.mark.asyncio
    async def test_async_messages_sends_the_same_body(self):
        req = FIXTURES["messagesRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["messagesResult"])) as mock_req:
            result = await client.ai.messages(**_messages_kwargs(req))
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/messages")
        assert kwargs["json"] == req
        assert kwargs["timeout"] == 155.0
        assert result == FIXTURES["messagesResult"]
        await client.close()

    @pytest.mark.asyncio
    async def test_async_complete_sends_toolsets(self):
        req = FIXTURES["completeWithToolsetsRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeWithToolsetsResult"])) as mock_req:
            await client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
                model=req["model"], toolsets=req["toolsets"],
            )
        assert mock_req.call_args.kwargs["json"] == req
        await client.close()

    @pytest.mark.asyncio
    async def test_async_tools_list(self):
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["toolList"])) as mock_req:
            result = await client.ai_tools.list()
        assert mock_req.call_args.args == ("GET", "/api/v1/ai/tools")
        assert result == FIXTURES["toolList"]
        await client.close()
