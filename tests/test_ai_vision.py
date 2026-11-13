# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-01  (pending)  caldera-platformxe#33: 503 AI_MODEL_UNAVAILABLE joins
#   the closed-code surface test.
# 2026-10-09  v1.7.2  Final review: TestModelCallOptions — complete / extract
#   wait 155 s, are never retried or failed open; analyze_room waits 35 s and
#   retries only with an idempotency key; other calls keep the defaults.
# 2026-10-09  v1.7.1  The grok pass-through test uses spacexai/grok-4.1-fast-reasoning;
#   the gateway catalogue withdrew xai/grok-3 (ADR-0013 amendment, ADR-0014).
# 2026-10-08  v1.7.0  Created (caldera-platformxe#22). Contract tests for
#   client.ai (complete / extract / profile / usage) and client.vision
#   (analyze_room), sync and async, against tests/fixtures/ai_vision.json —
#   the shared fixture set (identical copy in packages/sdk-go/testdata/).
#   Each test pins the method, path, query, headers and the exact camelCase
#   body against the fixture request, the passthrough of the fixture
#   response, and the error surface: code, status, details["path"] on 422
#   AI_OUTPUT_INVALID, retry_after + details on 429 AI_QUOTA_EXCEEDED.
# =============================================================================

"""Contract tests for the AI gateway and vision services."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeAPIError, PlatformXeClient

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


def _ok(data, headers=None):
    return _response(200, {"success": True, "data": data}, headers)


def _error(name):
    fixture = FIXTURES[name]
    return _response(fixture["status"], fixture["body"], fixture["headers"])


# ---------------------------------------------------------------------------
# client.ai
# ---------------------------------------------------------------------------

class TestAiService:
    def test_namespaces_present(self):
        client = PlatformXeClient(api_key="test")
        for method in ["complete", "extract", "profile", "usage"]:
            assert callable(getattr(client.ai, method, None)), f"Missing ai.{method}"
        assert callable(getattr(client.vision, "analyze_room", None))
        client.close()

    def test_complete_sends_the_fixture_request(self):
        req = FIXTURES["completeRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            result = client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/complete")
        assert kwargs["json"] == req
        assert result == FIXTURES["completeResult"]
        client.close()

    def test_complete_sends_model_only_when_given(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            client.ai.complete(
                feature_key="ai-canvas", provider="grok",
                messages=[{"role": "user", "content": "hi"}], model="spacexai/grok-4.1-fast-reasoning",
            )
        _, kwargs = mock_req.call_args
        assert kwargs["json"]["model"] == "spacexai/grok-4.1-fast-reasoning"
        client.close()

    def test_extract_sends_the_fixture_request(self):
        req = FIXTURES["extractRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["extractResult"])) as mock_req:
            result = client.ai.extract(
                feature_key=req["featureKey"],
                system_prompt=req["systemPrompt"],
                user_prompt=req["userPrompt"],
                output_json_schema=req["outputJsonSchema"],
                model_tier=req["modelTier"],
                images=req["images"],
                temperature=req["temperature"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/extract")
        assert kwargs["json"] == req
        assert result == FIXTURES["extractResult"]
        client.close()

    def test_extract_omits_optional_fields(self):
        req = FIXTURES["extractRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["extractResult"])) as mock_req:
            client.ai.extract(
                feature_key=req["featureKey"], system_prompt="s", user_prompt="u",
                output_json_schema={"type": "object"}, model_tier="PREMIUM",
            )
        _, kwargs = mock_req.call_args
        assert "images" not in kwargs["json"]
        assert "temperature" not in kwargs["json"]
        client.close()

    def test_profile_queries_feature_key(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["profileView"])) as mock_req:
            result = client.ai.profile("guest-concierge")
        args, kwargs = mock_req.call_args
        assert args == ("GET", "/api/v1/ai/profile")
        assert kwargs["params"] == {"featureKey": "guest-concierge"}
        assert result == FIXTURES["profileView"]
        client.close()

    def test_usage_sends_window_and_feature_key(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["usageSummary"])) as mock_req:
            result = client.ai.usage(
                from_="2026-09-08T00:00:00.000Z", to="2026-10-08T00:00:00.000Z", feature_key="guest-concierge",
            )
        args, kwargs = mock_req.call_args
        assert args == ("GET", "/api/v1/ai/usage")
        assert kwargs["params"] == {
            "from": "2026-09-08T00:00:00.000Z",
            "to": "2026-10-08T00:00:00.000Z",
            "featureKey": "guest-concierge",
        }
        assert result == FIXTURES["usageSummary"]
        client.close()

    def test_usage_without_query_sends_no_params(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["usageSummary"])) as mock_req:
            client.ai.usage()
        _, kwargs = mock_req.call_args
        assert kwargs["params"] == {}
        client.close()

    def test_output_invalid_keeps_details_path(self):
        client = PlatformXeClient(api_key="test", fail_open=False)
        req = FIXTURES["extractRequest"]
        with patch.object(client._client, "request", return_value=_error("outputInvalidError")):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.extract(
                    feature_key=req["featureKey"], system_prompt="s", user_prompt="u",
                    output_json_schema={"type": "object"}, model_tier="FAST",
                )
        assert exc_info.value.code == "AI_OUTPUT_INVALID"
        assert exc_info.value.status_code == 422
        assert exc_info.value.details == {"path": "/total"}
        client.close()

    def test_quota_exceeded_carries_retry_after_and_is_not_retried(self):
        client = PlatformXeClient(api_key="test", fail_open=False, retries=2)
        with patch.object(client._client, "request", return_value=_error("quotaExceededError")) as mock_req:
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.complete(feature_key="guest-concierge", provider="gemini", messages=[])
        assert exc_info.value.code == "AI_QUOTA_EXCEEDED"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 3600
        assert exc_info.value.details == {"metric": "tokens", "retryAfterSeconds": 3600}
        assert mock_req.call_count == 1
        client.close()

    @pytest.mark.parametrize("status,code", [
        (403, "AI_PROFILE_NOT_FOUND"),
        (403, "AI_PROFILE_DISABLED"),
        (403, "AI_POLICY_DENIED"),
        (422, "AI_OUTPUT_BLOCKED"),
        (502, "AI_UPSTREAM_ERROR"),
        (503, "AI_NOT_CONFIGURED"),
        (503, "AI_MODEL_UNAVAILABLE"),
    ])
    def test_closed_error_codes_surface(self, status, code):
        client = PlatformXeClient(api_key="test", fail_open=False)
        resp = _response(status, {"success": False, "error": {"code": code, "message": "refused"}})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.ai.complete(feature_key="guest-concierge", provider="gemini", messages=[])
        assert exc_info.value.code == code
        assert exc_info.value.status_code == status
        assert exc_info.value.details is None
        assert exc_info.value.retry_after is None
        client.close()


# ---------------------------------------------------------------------------
# client.vision
# ---------------------------------------------------------------------------

class TestVisionService:
    def _call(self, client, **extra):
        req = FIXTURES["analyzeRoomRequest"]
        return client.vision.analyze_room(
            room_categories=req["roomCategories"],
            want_alt_text=req["wantAltText"],
            image_url=req["imageUrl"],
            locale=req["locale"],
            feature_key=req["featureKey"],
            **extra,
        )

    def test_analyze_room_sends_the_fixture_request(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["analyzeRoomResult"])) as mock_req:
            result = self._call(client)
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/vision/analyze-room")
        assert kwargs["json"] == FIXTURES["analyzeRoomRequest"]
        assert "headers" not in kwargs
        assert result == FIXTURES["analyzeRoomResult"]
        client.close()

    def test_idempotency_key_is_sent_as_header(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["analyzeRoomResult"])) as mock_req:
            self._call(client, idempotency_key="photo-123")
        _, kwargs = mock_req.call_args
        assert kwargs["headers"] == {"x-idempotency-key": "photo-123"}
        client.close()

    def test_base64_image_is_sent_as_imageBase64(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["analyzeRoomResult"])) as mock_req:
            client.vision.analyze_room(room_categories=["KITCHEN"], want_alt_text=False, image_base64="aW1n")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"roomCategories": ["KITCHEN"], "wantAltText": False, "imageBase64": "aW1n"}
        client.close()

    def test_fallback_is_returned_as_data(self):
        client = PlatformXeClient(api_key="test")
        resp = _ok(FIXTURES["analyzeRoomFallback"], {"x-idempotency-cache": "skip"})
        with patch.object(client._client, "request", return_value=resp):
            result = self._call(client, idempotency_key="photo-123")
        assert result["aiStatus"] == "FALLBACK"
        assert result == FIXTURES["analyzeRoomFallback"]
        client.close()

    def test_vision_not_configured_surfaces(self):
        client = PlatformXeClient(api_key="test", fail_open=False)
        with patch.object(client._client, "request", return_value=_error("visionNotConfiguredError")):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                self._call(client)
        assert exc_info.value.code == "VISION_NOT_CONFIGURED"
        assert exc_info.value.status_code == 503
        client.close()


# ---------------------------------------------------------------------------
# Async parity
# ---------------------------------------------------------------------------

class TestAsyncAiVision:
    @pytest.mark.asyncio
    async def test_async_complete_sends_the_same_body(self):
        req = FIXTURES["completeRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            result = await client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/complete")
        assert kwargs["json"] == req
        assert result == FIXTURES["completeResult"]
        await client.close()

    @pytest.mark.asyncio
    async def test_async_extract_profile_usage(self):
        req = FIXTURES["extractRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["extractResult"])) as mock_req:
            await client.ai.extract(
                feature_key=req["featureKey"], system_prompt=req["systemPrompt"],
                user_prompt=req["userPrompt"], output_json_schema=req["outputJsonSchema"],
                model_tier=req["modelTier"], images=req["images"], temperature=req["temperature"],
            )
        assert mock_req.call_args[1]["json"] == req

        with patch.object(client._client, "request", return_value=_ok(FIXTURES["profileView"])) as mock_req:
            await client.ai.profile("guest-concierge")
        assert mock_req.call_args[0] == ("GET", "/api/v1/ai/profile")
        assert mock_req.call_args[1]["params"] == {"featureKey": "guest-concierge"}

        with patch.object(client._client, "request", return_value=_ok(FIXTURES["usageSummary"])) as mock_req:
            await client.ai.usage(feature_key="room-vision")
        assert mock_req.call_args[0] == ("GET", "/api/v1/ai/usage")
        assert mock_req.call_args[1]["params"] == {"featureKey": "room-vision"}
        await client.close()

    @pytest.mark.asyncio
    async def test_async_analyze_room_sends_idempotency_header(self):
        req = FIXTURES["analyzeRoomRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["analyzeRoomResult"])) as mock_req:
            await client.vision.analyze_room(
                room_categories=req["roomCategories"], want_alt_text=req["wantAltText"],
                image_url=req["imageUrl"], locale=req["locale"], feature_key=req["featureKey"],
                idempotency_key="photo-123",
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/vision/analyze-room")
        assert kwargs["json"] == req
        assert kwargs["headers"] == {"x-idempotency-key": "photo-123"}
        await client.close()

    @pytest.mark.asyncio
    async def test_async_quota_error_carries_retry_after(self):
        client = AsyncPlatformXeClient(api_key="test", fail_open=False)
        with patch.object(client._client, "request", return_value=_error("quotaExceededError")):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                await client.vision.analyze_room(room_categories=["KITCHEN"], want_alt_text=True, image_url="https://x.test/a.jpg")
        assert exc_info.value.code == "AI_QUOTA_EXCEEDED"
        assert exc_info.value.retry_after == 3600
        await client.close()


# ---------------------------------------------------------------------------
# Per-call options (final review 2026-10-09)
# ---------------------------------------------------------------------------

class TestModelCallOptions:
    def test_complete_waits_155s_and_is_never_retried_or_failed_open(self):
        req = FIXTURES["completeRequest"]
        client = PlatformXeClient(api_key="test", retries=2, fail_open=True)
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("slow")) as mock_req:
            with pytest.raises(Exception) as exc_info:
                client.ai.complete(feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"])
        assert mock_req.call_count == 1  # one billed attempt, no retry
        assert mock_req.call_args.kwargs["timeout"] == 155.0
        assert "1 attempts" in str(exc_info.value)  # raised, not the fail-open placeholder
        client.close()

    def test_extract_carries_the_same_options(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok({"data": {}})) as mock_req:
            client.ai.extract(
                feature_key="document.freeform", system_prompt="s", user_prompt="u",
                output_json_schema={"type": "object"}, model_tier="FAST",
            )
        assert mock_req.call_args.kwargs["timeout"] == 155.0
        client.close()

    def test_analyze_room_is_retried_only_with_an_idempotency_key(self):
        client = PlatformXeClient(api_key="test", retries=2, fail_open=True)
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("slow")) as mock_req:
            client.vision.analyze_room(room_categories=["KITCHEN"], want_alt_text=False, image_url="https://x.test/a.jpg")
        assert mock_req.call_count == 1
        assert mock_req.call_args.kwargs["timeout"] == 35.0
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("slow")) as mock_req:
            client.vision.analyze_room(
                room_categories=["KITCHEN"], want_alt_text=False, image_url="https://x.test/a.jpg",
                idempotency_key="photo-1",
            )
        assert mock_req.call_count == 3
        client.close()

    def test_other_calls_keep_the_client_defaults(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok({})) as mock_req:
            client.ai.profile("ai-canvas")
        assert "timeout" not in mock_req.call_args.kwargs
        client.close()

    @pytest.mark.asyncio
    async def test_async_complete_carries_the_options(self):
        req = FIXTURES["completeRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            await client.ai.complete(feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"])
        assert mock_req.call_args.kwargs["timeout"] == 155.0
        await client.close()
