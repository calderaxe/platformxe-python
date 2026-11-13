# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  Created (caldera-platformxe#22, NO-DRIFT for the AI
#   gateway routes). AiService.complete / extract / profile / usage for
#   POST /api/v1/ai/complete, POST /api/v1/ai/extract, GET /api/v1/ai/profile
#   and GET /api/v1/ai/usage — scope ai:complete, 600 requests/hr/key.
#   Request bodies mirror ProductAiCompleteRequest / ProductAiExtractRequest
#   and the usage query mirrors AiUsageQuery in @caldera/platformxe-types
#   3.5.0 (src/ai.ts); responses pass through unchanged (camelCase keys),
#   as with every other method on this client. The body / query builders are
#   module-level so AsyncAiService (async_services.py) sends byte-identical
#   requests. The deprecated `sourceApp` alias is deliberately not offered —
#   send `feature_key`.
# 2026-10-08  v1.7.0  (pending release, xadmin#29) complete() takes optional
#   `tools` (function tools, wire shape {name, description?, parameters?})
#   and `tool_choice` ("auto" | "none" | "required" | {"name": ...}); a
#   message may carry `toolCalls` (assistant) or `toolCallId` (role "tool")
#   and is passed through unchanged. The result may carry `toolCalls` and
#   `finishReason`. PlatformXe never executes a tool.
# 2026-10-09  (pending release, xadmin#31) complete() docstring names the new
#   provider "claude" (ADR-0014; ProductAiProvider in the pending
#   @caldera/platformxe-types 3.7.0). Docstring only — provider is a str.
# 2026-10-09  (pending release) Final review: the model calls carry per-call
#   options — complete() / extract() wait up to 155 s (the routes run up to
#   150 s; the client default is 10 s), are never retried (every attempt is a
#   billed model call that counts against the daily cap) and never return
#   the fail-open placeholder (MODEL_CALL_OPTIONS).
# 2026-11-01  (pending release, caldera-platformxe#33) AiService docstring
#   names the new closed code AI_MODEL_UNAVAILABLE (503 — the gateway account
#   cannot use the model; paid credits needed). Docstring only.
# 2026-11-01  (pending release, caldera-platformxe#33 review) the
#   AI_MODEL_UNAVAILABLE message is the fixed "The AI service account cannot
#   use this model right now." (the gateway's reason is no longer returned).
#   Docstring only.
# =============================================================================

"""Product AI gateway service — completion, structured extraction, profile, usage."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient

#: Per-call options for POST /ai/complete and /ai/extract: the routes run up
#: to 150 s, and a retried or fail-open call is a second billed model call.
MODEL_CALL_OPTIONS: Dict[str, Any] = {"timeout": 155.0, "retries": 0, "fail_open": False}


def build_complete_body(
    feature_key: str,
    provider: str,
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """ProductAiCompleteRequest: {featureKey, provider, messages, model?,
    tools?, toolChoice?}. Messages are wire dicts (role, content, and
    toolCalls / toolCallId on tool-calling turns), passed through unchanged."""
    body: Dict[str, Any] = {
        "featureKey": feature_key,
        "provider": provider,
        "messages": messages,
    }
    if model is not None:
        body["model"] = model
    if tools is not None:
        body["tools"] = tools
    if tool_choice is not None:
        body["toolChoice"] = tool_choice
    return body


def build_extract_body(
    feature_key: str,
    system_prompt: str,
    user_prompt: str,
    output_json_schema: Dict[str, Any],
    model_tier: str,
    images: Optional[List[Dict[str, str]]] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """ProductAiExtractRequest: {featureKey, systemPrompt, userPrompt,
    outputJsonSchema, modelTier, images?, temperature?}.

    Each image is ``{"url": ...}`` or ``{"base64": ..., "mediaType": ...}``
    (wire keys, passed through unchanged).
    """
    body: Dict[str, Any] = {
        "featureKey": feature_key,
        "systemPrompt": system_prompt,
        "userPrompt": user_prompt,
        "outputJsonSchema": output_json_schema,
        "modelTier": model_tier,
    }
    if images is not None:
        body["images"] = images
    if temperature is not None:
        body["temperature"] = temperature
    return body


def build_usage_params(
    from_: Optional[str] = None,
    to: Optional[str] = None,
    feature_key: Optional[str] = None,
) -> Dict[str, str]:
    """AiUsageQuery: from / to (ISO-8601) and featureKey, only when given."""
    params: Dict[str, str] = {}
    if from_ is not None:
        params["from"] = from_
    if to is not None:
        params["to"] = to
    if feature_key is not None:
        params["featureKey"] = feature_key
    return params


class AiService:
    """Product AI gateway (scope ``ai:complete``).

    Every call runs under the AI profile for (the API key's caller service,
    ``feature_key``), which sets the allowed providers / models, the size
    limits, the policy and the daily caps. Errors raise
    :class:`~platformxe.exceptions.PlatformXeAPIError` with the closed
    ProductAiErrorCode set as ``code``; ``details`` carries ``path`` on
    ``AI_OUTPUT_INVALID`` and ``retry_after`` the Retry-After seconds on
    ``AI_QUOTA_EXCEEDED``. ``AI_MODEL_UNAVAILABLE`` (503) means the gateway
    account cannot use the model (paid gateway credits are required);
    ``details["model"]`` names it; the message is the fixed "The AI service
    account cannot use this model right now."
    """

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def complete(
        self,
        feature_key: str,
        provider: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run one chat completion (``provider``: "gemini", "grok" or "claude";
        ``messages``: ``[{"role": ..., "content": ...}]``).

        ``tools`` (at most 16, only when the profile allows tools) and
        ``tool_choice`` enable tool calling: the result may then carry
        ``toolCalls`` (``[{id, name, arguments}]``) with ``finishReason``
        "tool_calls". Run each call yourself and send the result back as
        ``{"role": "tool", "toolCallId": ..., "content": ...}`` after the
        assistant message that carried ``toolCalls``.

        Returns ``{content, provider, model, usage?, toolCalls?, finishReason?}``.
        """
        return self._client.post(
            "/api/v1/ai/complete",
            json=build_complete_body(feature_key, provider, messages, model, tools, tool_choice),
            **MODEL_CALL_OPTIONS,
        )

    def extract(
        self,
        feature_key: str,
        system_prompt: str,
        user_prompt: str,
        output_json_schema: Dict[str, Any],
        model_tier: str,
        images: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Structured extraction validated against ``output_json_schema``
        (``model_tier``: "FAST" or "PREMIUM"; at most 4 ``images``, only when
        the profile allows images).

        Returns ``{data, provider, model, usage?, rawContent?}``. An
        off-schema reply raises ``AI_OUTPUT_INVALID`` (422) with
        ``details["path"]``.
        """
        return self._client.post(
            "/api/v1/ai/extract",
            json=build_extract_body(
                feature_key, system_prompt, user_prompt, output_json_schema,
                model_tier, images, temperature,
            ),
            **MODEL_CALL_OPTIONS,
        )

    def profile(self, feature_key: str) -> Dict[str, Any]:
        """The calling service's own AI profile for one feature (AiProfileView:
        status, allow-lists, limits, today's usage; policy text withheld)."""
        return self._client.get("/api/v1/ai/profile", params={"featureKey": feature_key})

    def usage(
        self,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        feature_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The calling service's own AI + vision usage (AiUsageSummary).

        ``from_`` / ``to`` are ISO-8601; default the last 30 days, at most a
        92-day window.
        """
        return self._client.get(
            "/api/v1/ai/usage",
            params=build_usage_params(from_, to, feature_key),
        )
