# PlatformXe Python SDK

Official Python SDK for the [PlatformXe](https://platformxe.com) API — messaging, storage, OCR, PDF, identity, fraud detection, webhooks, workflows, custom events, and authorization (RBAC + ABAC + ReBAC + Federation).

[![Version](https://img.shields.io/badge/version-1.7.0-blue)](https://github.com/calderaxe/platformxe-python/releases/tag/v1.7.0)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

## Install

```bash
pip install "platformxe @ git+https://github.com/calderaxe/platformxe-python@v1.7.0"
```

The package is not yet published on PyPI; install it from the GitHub release tag above.

The SDK supports Python 3.9+ and ships with `httpx` as its only runtime dependency.

## Quick start

```python
from platformxe import PlatformXeClient

client = PlatformXeClient(api_key="pxk_live_…")

# Send a transactional email
client.messaging.send_email(
    to="user@example.com",
    subject="Welcome",
    html="<h1>Hello</h1>",
    from_="Your App <hello@yourapp.com>",
)

# Resolve a Nigerian identity
# The key must name identity:resolve; purpose is required (1.12.0).
profile = client.identity.resolve(
    type="BVN",
    value="22012345678",
    purpose="tenant onboarding",
    consent_reference="consent_abc",
)
```

## Async usage

```python
from platformxe import AsyncPlatformXeClient

async with AsyncPlatformXeClient(api_key="pxk_live_…") as client:
    await client.messaging.send_email(
        to="user@example.com",
        subject="Welcome",
        html="<h1>Hello</h1>",
        from_="Your App <hello@yourapp.com>",
    )
```

## Configuration

```python
client = PlatformXeClient(
    api_key="pxk_live_…",                # required
    base_url="https://platformxe.com",   # optional — defaults to production
    timeout=10.0,                         # optional — seconds
    retries=2,                            # optional — retried on 5xx + network errors
    fail_open=False,                      # optional — return error dict instead of raising
)
```

`base_url` accepts the regional production endpoint or a self-hosted PlatformXe instance.

## Surface

| Namespace | Domain |
|-----------|--------|
| `client.messaging` | Transactional email, SMS, WhatsApp click-to-chat |
| `client.storage` / `client.documents` | Media + fixed-storage upload, signed URLs; `documents.categories` / `documents.settings` (1.12.0) |
| `client.ocr` / `client.pdf` / `client.qr` | OCR, PDF generation (`pdf.generate`: HTML or a stored template to a stored PDF with a signed URL, or base64, 1.14.0), QR encoding (`qr.generate_batch`: stored QR images and an optional zip, 1.14.0) |
| `client.ai` | AI & Vision gateway — `complete` (with `toolsets`, 1.16.0), `messages` (native Claude messages, 1.16.0; `actor`, 1.17.0; `actors`, 1.18.0), `extract`, `profile`, `usage` (1.7.0) |
| `client.ai_tools` | The platform tools a key may use in the server-side tool loop: `list()` (scope `tools:platform.read`, 1.16.0) |
| `client.vision` | Image analysis — `analyze_room` (1.7.0) |
| `client.identity` | Identity resolution + Nigerian KYC (BVN, NIN, liveness, face match) |
| `client.audit` | Decision + mutation audit log query/export |
| `client.webhooks` | Outbound webhook endpoints |
| `client.templates` | Content templates |
| `client.workflows` | Event-driven automations |
| `client.domains` | Sending domain management |
| `client.events` | Built-in event ingestion + log + subscriptions |
| `client.events.custom` | Tenant-defined custom events (Phase 9A) |
| `client.events.custom.marketplace` | Cross-tenant marketplace (Phase 9C, PRO+) |
| `client.events.custom.federation` | Cross-org event fan-out (Phase 9D + Pattern 3, ENTERPRISE) |
| `client.threads` | Caldera Threads contextual messaging |
| `client.exports` | Async data export jobs |
| `client.usage` | Usage + billing reads |
| `client.billing` | The key's organisation's invoices: `list_invoices` / `get_invoice` (scope `billing:read`, money as kobo strings, 1.14.0) |
| `client.license` | The key's organisation's Enterprise License: `get()` (scope `license:read`; effective plan and its source, exemption, and the covering license's state, validity, edition and the plugins granted to this organisation; never money, 1.15.0) |
| `client.search` | Federated search query |
| `client.issues` | Tenant-reported issues / support cases |
| `client.whoami` | API-key resolution + telemetry helpers |
| `register()` | Module-level standalone bootstrap helper |

Fraud Detection (`client.fraud`) and Authorization (`client.permissions`) are documented in the gated sections of [docs.platformxe.com](https://docs.platformxe.com/services/fraud-detection/overview), available on request (sales@platformxe.com).

## Product AI and vision (1.7.0)

Every call runs under the AI profile for *(your API key's caller service, `feature_key`)*, which sets the allowed providers / models, size limits, policy and daily caps. Scopes: `ai:complete` (600 requests/hr/key) for `client.ai`, `vision:analyze` (2,000/hr/key) for `client.vision`.

```python
reply = client.ai.complete(
    feature_key="guest-concierge",
    provider="gemini",
    messages=[{"role": "user", "content": "What time is check-out?"}],
)

invoice = client.ai.extract(
    feature_key="document.freeform",
    system_prompt="Extract the invoice fields.",
    user_prompt=text,
    output_json_schema={"type": "object", "properties": {"total": {"type": "number"}}, "required": ["total"]},
    model_tier="FAST",
)

profile = client.ai.profile("guest-concierge")        # limits + today's usage
usage = client.ai.usage(feature_key="guest-concierge")  # default: last 30 days

room = client.vision.analyze_room(
    room_categories=["KITCHEN", "BEDROOM"],
    want_alt_text=True,
    image_url=image_url,
    idempotency_key=f"photo-{photo_id}",   # sent as x-idempotency-key
)
if room["aiStatus"] == "FALLBACK":
    ...  # provider timeout: a deterministic answer, never cached under the key
```

Errors raise `PlatformXeAPIError` with the closed code set (`BAD_REQUEST`, `AI_PROFILE_NOT_FOUND`, `AI_PROFILE_DISABLED`, `AI_POLICY_DENIED`, `CONFLICT`, `AI_OUTPUT_BLOCKED`, `AI_OUTPUT_INVALID`, `AI_QUOTA_EXCEEDED`, `AI_NOT_CONFIGURED`, `AI_MODEL_UNAVAILABLE`, `VISION_NOT_CONFIGURED`, `AI_UPSTREAM_ERROR`, `SERVER_ERROR`). `err.details["path"]` names the failing value on `AI_OUTPUT_INVALID`; `err.retry_after` is the Retry-After seconds (to the next UTC midnight) on `AI_QUOTA_EXCEEDED`. API errors are never retried by this client. `AI_MODEL_UNAVAILABLE` (503) means the AI gateway account cannot use the requested model — paid gateway credits are required; `err.message` is the fixed text "The AI service account cannot use this model right now." and `err.details["model"]` names the model (not `AI_NOT_CONFIGURED`, which is a missing or rejected key). `CONFLICT` (409) comes from `knowledge.upsert_document` when the collection + source_ref is held by another organisation's document under the same caller service (until the organisation-keyed contract migration); use a different `source_ref`, retrying does not fix it.

### Native messages and server-side tools (1.16.0)

`client.ai.messages(...)` (`POST /api/v1/ai/messages`, scope `ai:complete`) takes the Anthropic Messages request shape on the Claude 5.5 models, governed by the same AI profile as `complete`: `system`, `messages` with content blocks, `effort` (capped by the profile's `maxEffort`), `output_schema` (structured output, when the profile allows it), caller `tools` with `tool_choice` "auto" or "none" ("auto" or left out with `toolsets`), `max_tokens`. No streaming. After a server-side fallback the reply's content starts at the last `fallback` block (that block included). `output_schema` needs an object root, every object node `additionalProperties: False`; `pattern`, `minItems` 0 or 1 and the supported `format`s pass, numeric and length bounds are refused (400). `toolsets=["platform.read"]` (on `messages`, or on `complete` with a Claude 5.5 model named by its gateway slug, e.g. `"anthropic/claude-sonnet-5.5"`; `messages` takes the Anthropic id, e.g. `"claude-sonnet-5-5"`) runs PlatformXe's read-only tools in a loop over the key's own organisation; the key needs `tools:platform.read` and every toolset must be on the profile. The answer's `toolRuns` lists each tool call. `client.ai_tools.list()` (`GET /api/v1/ai/tools`) answers the tools the key may use.

```python
tools = client.ai_tools.list()  # {items: [{name, version, description, inputSchema, dataClasses, toolset}], total}
reply = client.ai.messages(
    feature_key="ops-assistant",
    model="claude-sonnet-5-5",
    messages=[{"role": "user", "content": "How many webhook deliveries failed today?"}],
    toolsets=["platform.read"],
)
text = "".join(b["text"] for b in reply["message"]["content"] if b["type"] == "text")
```

New closed codes: `AI_BUDGET_EXCEEDED` (429, a spend budget; `err.retry_after` runs to the period's end, also on vision; `err.details["reason"]` is `"BUDGET_UNAVAILABLE"` when a hard budget could not be checked, and a tool-loop refusal carries no `period`, so read `err.details.get("period")`), `AI_REFUSED` (422, the model declined; no content, the call is billed; `err.details["category"]`), `AI_TOOLSET_DENIED` (403), `AI_TOOL_FAILED` (502, the tool round trip itself broke) and `AI_LOOP_LIMIT` (422, `err.details["reason"]` TURNS, CALLS or DEADLINE). Model calls are never retried.

### Acting for a person (1.17.0)

`client.ai.messages(..., actor={"ref": ..., "permissions": [...], "grant": ...})` names the person a first-party Caldera app's own tools act for (types 3.19.0 `actor`). `ref` is the person's id in your app (1 to 64 of A-Z a-z 0-9 _ -); `permissions` holds at most 32 canonical prefixed keys (e.g. `"CN:REQUESTS:VIEW"`; missing or `None` is sent as `[]`, never null); `grant` is opaque (at most 4,096 base64url characters), forwarded only to the tool's own app and never stored, logged or returned. A first-party app's tool is offered only when `permissions` holds its `requiredPermission`; `ai_tools.list()` items carry `sourceApp` and `requiredPermission`. Only the app's own organisation can use its tools (scope `tools:{app}.read`, named on the key). When none of the requested toolsets has a usable tool, the call answers 403 `AI_TOOLSET_DENIED` before any model call, and `err.details["reason"]` says why: `"SOURCE_UNAVAILABLE"` (the app's tools are switched off or cannot be read: fall back to a path without tools), `"DATA_CLASS"` (refused by the profile's data classes) or `"NOT_ALLOWED"` (not on the profile, or the key or actor may use none of them). Fall back only on `"SOURCE_UNAVAILABLE"`. With several toolsets requested, the call runs (and is billed) when any one still has a usable tool. `AI_TOOL_FAILED` (502) comes after model spend.

### Caldera's operator console (1.18.0)

`client.ai.messages(..., actors={"lettings": {"ref": ..., "permissions": [...], "grant": ...}, ...})` is for Caldera's own operator console, which calls with a platform key (types 3.20.0 `actors`). One entry per Caldera app (`xadmin`, `lettings`, `concierge`, `chats`): that app's id for the person, at most 64 permission keys with that app's prefix (`XA:`, `LT:`, `CN:`, `CH:`; missing or `None` is sent as `[]`) and that app's own `grant` (required). Each entry is forwarded only to its own app's tools. `actor` and `actors` together raise `ValueError`; an organisation key sending `actors`, or a platform key sending `actor`, is 400.

## Pattern 3 — external webhook peers (1.5.0)

Custom Event Federation supports peers addressed by URL + HMAC secret instead of a tenant org id — useful when the receiving system isn't on PlatformXe.

```python
result = client.events.custom.federation.add_external_peer(
    group_id,
    label="Booking.com",
    webhook_url="https://booking.example.com/inbound/platformxe",
    headers={"Authorization": "Bearer xyz"},
)
secret = result["data"]["secret"]   # 'whsec_…' — store immediately, shown ONCE
peer_id = result["data"]["peer"]["id"]

# Remove later:
client.events.custom.federation.remove_external_peer(peer_id)
```

The receiving endpoint verifies inbound POSTs with `X-Caldera-Signature-V2: sha256=<hex>` = HMAC-SHA256(secret, `{X-Caldera-Timestamp}.{raw body}`), a 5-minute timestamp window and `X-Caldera-Delivery-Id` as the replay key. The legacy body-only `X-Caldera-Signature` (HMAC of the raw body alone) is replayable and is sent for compatibility only until **2027-04-30**, when `X-Caldera-Signature` switches to the V2 value. See the [federation reference](https://docs.platformxe.com/sdk/federation) for the full wire format.

## Error handling

Every method raises `PlatformXeAPIError` on 4xx/5xx responses, or `PlatformXeError` on transport failures. Set `fail_open=True` to receive the API's error envelope as a dict instead — useful for non-blocking permission checks.

```python
from platformxe import PlatformXeError, PlatformXeAPIError

try:
    client.messaging.send_email(to="user@example.com", subject="…", html="…", from_="Your App <hello@yourapp.com>")
except PlatformXeAPIError as err:
    # err.code, err.message, err.status_code — plus err.details (the envelope's
    # error.details, or None) and err.retry_after (Retry-After seconds, or None)
    ...
except PlatformXeError as err:
    # Network / configuration error
    ...
```

`fraud.decide` and `fraud.shadow_decide` raise `PlatformXeAPIError` with status 400 and `err.code == "CARD_NUMBER_REFUSED"` when the request carries a card number or a card field (`pan`, `cvv` ...): send a token, never card data. The message names where the value was, never the value.

## Versioning

| Package | Version |
|---------|---------|
| `platformxe` (this) | **1.18.0** pending, not tagged (2026-11-23, AI gateway P6, NO-DRIFT with types 3.20.0; follows 1.17.0): `actors` on `ai.messages(...)` (sync and async; never with `actor`; an entry's missing permissions sent as `[]`). |
| `platformxe` (1.17.0) | **1.17.0** pending, not tagged (2026-11-23, AI gateway P5, NO-DRIFT with types 3.19.0; follows 1.16.0): `actor` on `ai.messages(...)` (sync and async; missing permissions sent as `[]`), `ai_tools.list()` items carry `sourceApp` and `requiredPermission`. |
| `platformxe` (1.16.0) | **1.16.0** pending, not tagged (2026-11-22, AI gateway, NO-DRIFT with types 3.18.0; follows 1.15.0, the pending Enterprise License release): `ai.messages(...)` (`POST /api/v1/ai/messages`), `ai_tools.list()` (`GET /api/v1/ai/tools`, scope `tools:platform.read`), `toolsets` on `ai.complete` (the answer's `toolRuns`), sync and async; the profile view's governance fields and the five new closed codes are documented. |
| `platformxe` (1.15.0) | **1.15.0** pending, not tagged (2026-11-22, Enterprise License): new `client.license.get()` (`GET /api/v1/license`, scope `license:read`; `{edition: {plan, source}, bypass, license}`). Docs: `fraud.activate` answers `billing` `LICENSED` and 403 `LICENSE_REQUIRED` (after the licensing cut-over, no live license grant naming a fraud pack); `issues.create` answers 409 `CONTACT_LICENSING` for a plan-change request naming PRO or ENTERPRISE (sent to the licensing team as an issue, never a plan change; `details["email"]` is the licensing address, `details["id"]` the request, `details["existing"]` True when an open one was answered); `exports.create_export` of `dataType="invoices"` also needs `billing:read` (403), and `get_export` of one is 404 without it. Sync and async. |
| `platformxe` (1.14.1) | **1.14.1** pending, not tagged (2026-11-22, docs and tests only, no behaviour change): `workflows.evaluate` and `events.ingest` document `entity_data` as your own parameters for the event (what the triggers' conditions and templates read; for a business event type PlatformXe defines no fields): `{}` is sent as `{}`, `None` is omitted, and the API also accepts `null`. `event_type` is one of the values on [Workflow Event Types](https://docs.platformxe.com/services/workflows/event-types); the 400 for any other value, or an unknown entity type, never lists the values. |
| `platformxe` (1.14.0) | Pending with 1.14.0 (2026-11-21, caldera-platformxe spec 03 PM-1): **Fix:** `fraud.decide` / `fraud.shadow_decide` send the body the route reads, `{subject: {id, kind}, action, resource: {kind, id?}, context?}` (they sent flat `subjectId` / `subjectKind` / `resourceKind`: every call was a 400); signatures unchanged. Both document 400 `CARD_NUMBER_REFUSED` (card data in the request). **1.14.0** pending, not tagged (2026-11-20): `pdf.generate(html=None, *, template_id=, data=, options=, idempotency_key=)` (`POST /api/v1/pdf/generate`, scope `pdf:generate`, 100/hr per key; stored answer `{fileId, pdfUrl, expiresAt, size, pages, generatedAt}`, base64 answer `{content, contentType, size, pages, generatedAt}`). **Fix:** `qr.generate_batch(items, *, format=, zip=, url_ttl_seconds=, idempotency_key=)` matches `POST /api/v1/qr/batch` (scope `storage:upload`, 120/hr per key; the route did not exist before, so every call was a 404): each item is stored with a signed URL (`{items, totalGenerated, totalFailed, zip, generatedAt}`). New `client.billing.list_invoices(page=, limit=, status=)` / `get_invoice(invoice_id)` (`GET /api/v1/billing/invoices` and `/{id}`, scope `billing:read`, money as kobo strings). `idempotency_key` sends `x-idempotency-key`. Sync and async. |
| `platformxe` (1.13.0) | **1.13.0** pending, not tagged (2026-11-19): **Fix:** `events.replay` sends `fromTimestamp` / `toTimestamp` (it sent `from` / `to`, which the route never read: every replay was a 400) and takes `event_types`; `events.log` sends `eventTypes` (it sent `eventType`, never read) and takes `event_types`, `from_`, `to`; `events.create_subscription` takes `name` (required by the API) and no longer sends `secret` (never read). `fraud.rules.update` / `transition` take `expected_version` (409 `VERSION_MISMATCH` when the rule was edited since); `fraud.rules.shadow_report` takes `version`. `workflows.dry_run` posts `{entityData}` to `/api/v1/workflows/{id}` (it posted to a `/dry-run` path that does not exist: every call was a 404) and takes `entity_data=`; a context dict is still read (its `entityData` or `payload`); `storage.reorder_files` sends `PATCH` (it sent `POST`, which the route does not take). In `dry_run`, a context whose every key is a trigger-context key (`eventType`, `entityType`, `entityId`, `entityData`, `payload`, `metadata`, `sourceApp`, `dryRun`, `organizationId`, `callerService`) and that carries an `entityData` (else `payload`) object sends that object; any other map is the entity data, sent whole; the workflow id is URL-quoted in `get` / `update` / `delete` / `dry_run`, and an empty id raises `ValueError`. `workflows.list` (sync and async) takes `page`, `limit`, `is_active`, `trigger_type` and `event_type` (it could not reach page 2); `workflows.update` can now change `code`, `triggerType`, `eventType` and `entityType` (409 `DUPLICATE` for a code in use; `None` clears a nullable field). One path filler, `platformxe.services.paths.fill_path(template, **ids)`, URL-quotes each id it fills (`safe=""`) and raises `ValueError` for an empty id, `.` or `..` before any request; it replaces the private `events._fill` and the copies in `subscription_path` and `rule_path`. It covers the workflow, webhook, event-subscription, fraud-rule and custom-events (marketplace, federation) paths only: the other services (permissions, documents and more) still build their paths with f-strings that insert the id unquoted, a known gap left for a separate sweep. **Behaviour change:** `webhook_path` / `redeliver_path` (every `webhooks.*` call by id) now URL-quote the id (they inserted it as given), and an empty id, `.` or `..` raises `ValueError` in the webhooks, event-subscription, fraud-rule, workflow and custom-events calls (custom events sent an empty id before). `events.ingest` sends `entityData` (it sent `payload`, which `POST /api/v1/events` does not read, so no trigger saw the event data) and takes `entity_data=`, `source_app=` and `metadata=`; `entity_type` and `entity_id` are optional; `payload` is a deprecated alias (it warns), sent as `entityData` when `entity_data` is absent. Docs: 400 `RESTRICTED_EVENT_TYPE` and `restrictedEventTypes` on subscriptions; 400 `RESERVED_SEARCH_APP` on `search.index`; 409 `FEED_MISSING` / `FEED_NOT_REALTIME` on a rule publish; a case resolve records its outcome at once. 1.12.0 released (tag `sdk-python/v1.12.0`, 2026-11-18):  `identity.resolve` (sync and async) takes the required keyword-only `purpose` (1 to 200 characters), sent at the top level; the API answers 400 without it, and a key must name the `identity:resolve` scope (a key of an organisation with no scopes or `*` is answered 403). The answer's `outcome` is `found`, `not_found` (billed) or `provider_down` (not billed). `consent.obtainedAt` is sent only when given. **Breaking:** `resolve_linked` now defaults to `False`, as the API (it was `True`, which billed every linked lookup a provider answered); pass `resolve_linked=True` to keep the old behaviour. Also `identity.verify_business` (2026-11-13). **Fix:** `fraud.rules.publish` / `archive` post to `/api/v1/fraud/rules/{id}/transition` with `{target}` (they posted to `/publish` and `/archive`, which do not exist, so every call was a 404); `fraud.rules.transition(rule_id, target)`, `draft` and `shadow` added, and `RULE_TRANSITIONS` names the allowed moves (a draft rule goes to shadow before it can be published). New: `fraud.rules.shadow_report(rule_id, from_=, to=)`; `documents.categories` (`list` / `create` / `update` / `deactivate`, the tenant category registry) and `documents.settings` (`get` / `update`, `enforceCategories`), sync and async; `patch()` takes query `params`. Docs: `identity.lookup` answers `outcome`, `notFound` / `notFoundBy` and `raw: {provider}` only; `identity.dlq.replay` raises 409 `REPLAY_IN_PROGRESS` and a 500 when the replay did not complete (the row stays unreplayed); `fraud.cases.transition` raises 409 `CASE_AT_MLRO_STAGE` at an MLRO stage; `pdf.rasterize` is limited by the 4.5 MB request body (about 3.3 MB of PDF), not 10 MB. |
| `platformxe` (earlier) | **1.11.0** released (tag `sdk-python/v1.11.0`, 2026-11-08): the async client gains `identity.verify_bvn` / `verify_nin` / `verify_account` / `liveness` / `face_match`, `providers_health`, `identity.dlq`, and `messaging.build_whatsapp_link` / `whatsapp_health`, as the sync client has; `liveness` / `face_match` take optional content types; `check_batch` is annotated as the list it returns; fix: the identity verifications, DLQ replay and `fraud.decide` send their idempotency key as `x-idempotency-key` (the `Idempotency-Key` sent before was ignored). 1.10.0 released (tag `sdk-python/v1.10.0`). |
| `@caldera/platformxe-sdk` (TypeScript) | 1.21.0 *(pending, AI gateway P5: `actor`, spoke tools)*; 1.20.0 *(pending, AI gateway, after 1.19.0)*; 1.19.0 *(pending, Enterprise License)*; 1.18.2 released |
| `@caldera/platformxe-types` (TypeScript shapes) | 3.19.0 *(pending, AI gateway P5: `actor`, spoke tools)*; 3.18.0 *(pending, AI gateway, after 3.17.0)*; 3.17.0 *(pending, Enterprise License)*; 3.16.2 released |
| `github.com/calderaxe/platformxe-go` (Go) | v1.17.0 *(pending, AI gateway P5: `Actor`)*, v1.16.0 *(pending, AI gateway)*, v1.15.0 *(pending, Enterprise License)*, v1.14.1, v1.14.0 and v1.13.0 *(pending, not tagged)*; v1.12.0 released |
| `calderaxe/platformxe` (Terraform) | 1.5.4 and 1.5.3 *(pending, not tagged)*; 1.5.2 released |

The PlatformXe ecosystem ships **5 published artefacts** that move in lockstep against every API change (the NO-DRIFT policy). The full coverage matrix lives at [docs.platformxe.com/sdk/alignment](https://docs.platformxe.com/sdk/alignment).

## Distribution

The Python SDK is distributed from the GitHub mirror (PyPI publication is a pending follow-up; the `platformxe` name is not on PyPI yet). The source lives in this monorepo at `packages/sdk-python/` and is mirrored to GitHub at [`calderaxe/platformxe-python`](https://github.com/calderaxe/platformxe-python) on every `sdk-python/v*` tag push.

## Documentation

- **API reference + per-domain SDK guides:** [docs.platformxe.com](https://docs.platformxe.com)
- **OpenAPI 3.1 spec:** `https://api.platformxe.com/api/docs/openapi.json`
- **Status + incidents:** [status.platformxe.com](https://status.platformxe.com)

## License

Proprietary — © 2026 Caldera Technologies Ltd. All rights reserved.
