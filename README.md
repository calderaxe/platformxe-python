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
)

# Check a permission
result = client.permissions.check(
    admin_id="usr_123",
    path="chat/session",
    action="READ",
)

# Resolve a Nigerian identity
profile = client.identity.resolve(
    type="BVN",
    value="22012345678",
    consent_reference="consent_abc",
)
```

## Async usage

```python
from platformxe import AsyncPlatformXeClient

async with AsyncPlatformXeClient(api_key="pxk_live_…") as client:
    decision = await client.permissions.check(
        admin_id="usr_123",
        path="chat/session",
        action="READ",
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
| `client.storage` / `client.documents` | Media + fixed-storage upload, signed URLs |
| `client.ocr` / `client.pdf` / `client.qr` | OCR, PDF generation, QR encoding |
| `client.ai` | Product AI gateway — `complete`, `extract`, `profile`, `usage` (1.7.0) |
| `client.vision` | Image analysis — `analyze_room` (1.7.0) |
| `client.identity` | Identity resolution + Nigerian KYC (BVN, NIN, liveness, face match) |
| `client.fraud` | Fraud Detection — rules, screens, devices, federation, terms |
| `client.permissions` | RBAC + ABAC + ReBAC + Federation. `check`, `check_batch`, `resolve`, roles, modules, overrides, policies, relationships |
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
| `client.search` | Federated search query |
| `client.issues` | Tenant-reported issues / support cases |
| `client.whoami` | API-key resolution + telemetry helpers |
| `register()` | Module-level standalone bootstrap helper |

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

Errors raise `PlatformXeAPIError` with the closed code set (`BAD_REQUEST`, `AI_PROFILE_NOT_FOUND`, `AI_PROFILE_DISABLED`, `AI_POLICY_DENIED`, `AI_OUTPUT_BLOCKED`, `AI_OUTPUT_INVALID`, `AI_QUOTA_EXCEEDED`, `AI_NOT_CONFIGURED`, `AI_MODEL_UNAVAILABLE`, `VISION_NOT_CONFIGURED`, `AI_UPSTREAM_ERROR`, `SERVER_ERROR`). `err.details["path"]` names the failing value on `AI_OUTPUT_INVALID`; `err.retry_after` is the Retry-After seconds (to the next UTC midnight) on `AI_QUOTA_EXCEEDED`. API errors are never retried by this client. `AI_MODEL_UNAVAILABLE` (503) means the AI gateway account cannot use the requested model — paid gateway credits are required; `err.message` is the fixed text "The AI service account cannot use this model right now." and `err.details["model"]` names the model (not `AI_NOT_CONFIGURED`, which is a missing or rejected key).

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
    client.messaging.send_email(to="user@example.com", subject="…", html="…")
except PlatformXeAPIError as err:
    # err.code, err.message, err.status_code — plus err.details (the envelope's
    # error.details, or None) and err.retry_after (Retry-After seconds, or None)
    ...
except PlatformXeError as err:
    # Network / configuration error
    ...
```

## Versioning

| Package | Version |
|---------|---------|
| `platformxe` (this) | **1.7.0** *(tag `sdk-python/v1.7.0`, 2026-10-11)*; **1.8.0** pending (tag `sdk-python/v1.8.0`): `identity.verify(..., supporting_nin=)` for a `PASSPORT` check, plus the untagged `create_override(replace=)` |
| `@caldera/platformxe-sdk` (TypeScript) | 1.8.0 |
| `@caldera/platformxe-types` (TypeScript shapes) | 3.7.0 |
| `github.com/calderaxe/platformxe-go` (Go) | v1.7.1 *(pending — tag `sdk-go/v1.7.1` cut on merge; v1.7.0 tag `sdk-go/v1.7.0`, 2026-10-11)* |
| `calderaxe/platformxe` (Terraform) | 1.5.1 |

The PlatformXe ecosystem ships **5 published artefacts** that move in lockstep against every API change (the NO-DRIFT policy). The full coverage matrix lives at [docs.platformxe.com/sdk/alignment](https://docs.platformxe.com/sdk/alignment).

## Distribution

The Python SDK is distributed from the GitHub mirror (PyPI publication is a pending follow-up; the `platformxe` name is not on PyPI yet). The source lives in this monorepo at `packages/sdk-python/` and is mirrored to GitHub at [`calderaxe/platformxe-python`](https://github.com/calderaxe/platformxe-python) on every `sdk-python/v*` tag push.

## Documentation

- **API reference + per-domain SDK guides:** [docs.platformxe.com](https://docs.platformxe.com)
- **OpenAPI 3.1 spec:** `https://api.platformxe.com/api/docs/openapi.json`
- **Status + incidents:** [status.platformxe.com](https://status.platformxe.com)

## License

Proprietary — © 2026 Caldera Technologies Ltd. All rights reserved.
