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
# 2026-11-22  v1.16.0  (pending release, AI gateway T4, NO-DRIFT with types
#   3.18.0) messages() for POST /api/v1/ai/messages (the native Claude
#   Messages shape on the Claude 5.5 models; build_messages_body, shared with
#   the async service); complete() takes `toolsets` (the server-side tool
#   loop) and its result may carry `toolRuns`. The docstring names the five
#   new closed codes (AI_BUDGET_EXCEEDED, AI_REFUSED, AI_TOOLSET_DENIED,
#   AI_TOOL_FAILED, AI_LOOP_LIMIT). Both model calls keep MODEL_CALL_OPTIONS
#   (never retried: every attempt is billed). Amended before release (T5
#   review): docstrings document AI_BUDGET_EXCEEDED details.reason
#   BUDGET_UNAVAILABLE and the loop refusal without a period, the
#   structured-output outputSchema rule, tool_choice with toolsets, the reply
#   after a fallback, the AI_TOOL_FAILED meaning and complete's model slug.
# 2026-11-23  v1.17.0  (pending release, AI gateway P5, NO-DRIFT with types
#   3.19.0) messages() takes ``actor`` ({ref, permissions, grant?}): the
#   person a first-party app's own tools act for; sent as ``actor`` only when
#   given (build_messages_body).
#   Review round 1 (M-13): an actor whose ``permissions`` is missing or None
#   is sent with ``permissions: []``, never null (the server refuses null);
#   the caller's dict is not changed.
# 2026-11-23  v1.18.0  (pending release, AI gateway P6, NO-DRIFT with types
#   3.20.0) messages() takes ``actors`` ({app_id: {ref, permissions, grant}}):
#   Caldera's operator console (a platform key) names one person per Caldera
#   app; each entry reaches only its own app's tools. ``actor`` and ``actors``
#   together raise ValueError (the server answers 400 too); an entry's missing
#   or None ``permissions`` is sent as []; the caller's dicts are not changed.
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
    toolsets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """ProductAiCompleteRequest: {featureKey, provider, messages, model?,
    tools?, toolChoice?, toolsets?}. Messages are wire dicts (role, content,
    and toolCalls / toolCallId on tool-calling turns), passed through unchanged."""
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
    if toolsets is not None:
        body["toolsets"] = toolsets
    return body


def build_messages_body(
    feature_key: str,
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[Union[str, List[Dict[str, Any]]]] = None,
    effort: Optional[str] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    toolsets: Optional[List[str]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = None,
    max_tokens: Optional[int] = None,
    actor: Optional[Dict[str, Any]] = None,
    actors: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """ProductAiMessagesRequest: {featureKey, messages, model?, system?,
    effort?, outputSchema?, toolsets?, tools?, toolChoice?, maxTokens?,
    actor?, actors?}.

    ``actor`` and ``actors`` cannot be combined (ValueError).

    ``messages`` (content as a string or Anthropic content blocks), ``system``
    blocks and ``tools`` (``{name, description?, input_schema}``) are wire
    dicts, passed through unchanged. Optional fields are sent only when given.
    """
    body: Dict[str, Any] = {"featureKey": feature_key, "messages": messages}
    if model is not None:
        body["model"] = model
    if system is not None:
        body["system"] = system
    if effort is not None:
        body["effort"] = effort
    if output_schema is not None:
        body["outputSchema"] = output_schema
    if toolsets is not None:
        body["toolsets"] = toolsets
    if tools is not None:
        body["tools"] = tools
    if tool_choice is not None:
        body["toolChoice"] = tool_choice
    if max_tokens is not None:
        body["maxTokens"] = max_tokens
    if actor is not None:
        # permissions is required on the wire; None / missing is sent as [] (never null).
        if actor.get("permissions") is None:
            actor = {**actor, "permissions": []}
        body["actor"] = actor
    if actors is not None:
        if actor is not None:
            raise ValueError("actor and actors cannot be combined in one request")
        # Each entry's permissions is required on the wire; None / missing is sent as [] (never null).
        body["actors"] = {
            app: ({**entry, "permissions": []} if entry.get("permissions") is None else entry)
            for app, entry in actors.items()
        }
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

    Since 1.16.0: ``AI_BUDGET_EXCEEDED`` (429, a spend budget of the
    organisation or caller service; ``retry_after`` = seconds to the period's
    end, ``details["period"]``; ``details["reason"]`` is
    ``"BUDGET_UNAVAILABLE"`` when a hard budget could not be checked, with
    ``retry_after`` 60; a tool loop stopped by its budget between model calls
    has ``details == {"retryAfterSeconds": 60}`` and no ``period``, so read
    it with ``.get``), ``AI_REFUSED`` (422, the model declined; no content,
    the call is billed; ``details["category"]``), ``AI_TOOLSET_DENIED``
    (403), ``AI_TOOL_FAILED`` (502: the server-side tool round trip itself
    broke; a tool's own failure goes back to the model as an error result)
    and ``AI_LOOP_LIMIT`` (422, ``details["reason"]``: TURNS, CALLS or
    DEADLINE).
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
        toolsets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run one chat completion (``provider``: "gemini", "grok" or "claude";
        ``messages``: ``[{"role": ..., "content": ...}]``).

        ``toolsets`` (e.g. ``["platform.read"]``, a Claude 5.5 ``model`` only,
        named by its gateway slug such as ``"anthropic/claude-sonnet-5.5"``)
        runs PlatformXe's server-side tool loop: each toolset must be on the
        profile and the key needs ``tools:platform.read``; the result's
        ``toolRuns`` lists every tool call. Not together with ``tools``;
        ``tool_choice`` must then be "auto" or left out (400 otherwise).

        ``tools`` (at most 16, only when the profile allows tools) and
        ``tool_choice`` enable tool calling: the result may then carry
        ``toolCalls`` (``[{id, name, arguments}]``) with ``finishReason``
        "tool_calls". Run each call yourself and send the result back as
        ``{"role": "tool", "toolCallId": ..., "content": ...}`` after the
        assistant message that carried ``toolCalls``.

        Returns ``{content, provider, model, usage?, toolCalls?, finishReason?, toolRuns?}``.
        """
        return self._client.post(
            "/api/v1/ai/complete",
            json=build_complete_body(feature_key, provider, messages, model, tools, tool_choice, toolsets),
            **MODEL_CALL_OPTIONS,
        )

    def messages(
        self,
        feature_key: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        system: Optional[Union[str, List[Dict[str, Any]]]] = None,
        effort: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        toolsets: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        max_tokens: Optional[int] = None,
        actor: Optional[Dict[str, Any]] = None,
        actors: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """One native Claude Messages request (Anthropic Messages shape) on a
        Claude 5.5 model (``model``: "claude-haiku-5-5", "claude-sonnet-5-5"
        or "claude-opus-5-5", as the profile allows), governed by the AI
        profile exactly as :meth:`complete`.

        ``effort`` ("low" to "max") is capped by the profile's ``maxEffort``;
        ``output_schema`` needs the profile's ``allowStructuredOutput`` and an
        object root whose every object node has ``additionalProperties:
        False`` (``required`` optional); ``pattern``, ``minProperties`` /
        ``maxProperties``, ``minItems`` 0 or 1 and the formats date-time,
        time, date, duration, email, hostname, uri, ipv4, ipv6 and uuid are
        accepted; numeric and length bounds, ``maxItems``, ``uniqueItems``,
        ``minContains`` / ``maxContains``, ``minItems`` above 1 and other
        formats are refused (400). ``tool_choice`` is "auto" or "none" only
        ("auto" or left out with ``toolsets``). Caller ``tools`` come back as
        ``tool_use`` blocks for you to run; ``toolsets`` run the server-side
        tool loop. Pass thinking blocks back unchanged. No streaming. After a
        server-side fallback the reply's content starts at the last
        ``fallback`` block (that block included); send the turn back as
        returned (a ``fallback`` block's ``trigger`` is at most 512
        characters as JSON; only ``type`` and ``category`` are kept).

        Since 1.17.0, ``actor`` (``{"ref", "permissions", "grant"?}``) is the
        person a first-party Caldera app's own tools act for: such a tool is
        offered only when ``permissions`` (at most 32 canonical prefixed keys,
        e.g. "CN:REQUESTS:VIEW") holds its ``requiredPermission``. ``ref`` is
        1 to 64 of A-Z a-z 0-9 _ -; ``grant`` is opaque (at most 4,096
        base64url characters), forwarded only to that app, never stored.

        Since 1.18.0, ``actors`` (``{"lettings": {"ref", "permissions",
        "grant"}, ...}``, keys ``xadmin``, ``lettings``, ``concierge``,
        ``chats``) is for Caldera's operator console (a platform key): one
        person per app, each ``permissions`` (at most 64) with that app's
        prefix (``XA:``, ``LT:``, ``CN:``, ``CH:``) and that app's ``grant``
        (required). Each entry reaches only its own app's tools. Never with
        ``actor`` (ValueError); an organisation key sending ``actors`` is 400.

        Returns ``{message: {id, role, content, stop_reason, stop_details},
        model, usage, toolRuns?}``. A refusal raises ``AI_REFUSED`` (422).
        """
        return self._client.post(
            "/api/v1/ai/messages",
            json=build_messages_body(
                feature_key, messages, model, system, effort, output_schema,
                toolsets, tools, tool_choice, max_tokens, actor, actors,
            ),
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
