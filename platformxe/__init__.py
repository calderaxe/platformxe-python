# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
#
# CHANGELOG:
# 2026-11-23  v1.18.0 (pending)  AI gateway P6 (NO-DRIFT, types 3.20.0):
#   ai.messages(..., actors=) for Caldera's operator console (one person per
#   app; never with actor); version 1.18.0.
# 2026-11-23  v1.17.0 (pending)  AI gateway P5 (NO-DRIFT, types 3.19.0):
#   ai.messages(..., actor=) for first-party app tools; ai_tools.list items
#   carry sourceApp and requiredPermission; version 1.17.0.
# 2026-11-22  v1.16.0 (pending)  AI gateway T4 (NO-DRIFT, types 3.18.0):
#   ai.messages, ai_tools.list, toolsets on ai.complete; version 1.16.0
#   (1.15.0 is the pending Enterprise License release).
# 2026-11-22  v1.14.1 (pending)  Docs and tests only, no behaviour change:
#   workflows.evaluate and events.ingest document entity_data as your own
#   parameters for the event ({} sent, None omitted: unchanged since 1.12.0
#   for evaluate and since 1.13.0 for ingest) and event_type as a value on
#   the Workflow Event Types page.
# =============================================================================

"""PlatformXe Python SDK — messaging, storage, authorization, identity resolution, product AI, vision."""

from .client import PlatformXeClient, AsyncPlatformXeClient
from .exceptions import PlatformXeError, PlatformXeAPIError
from .types import APIResponse, PaginationMeta
from .register import register
from .services.workflows import WORKFLOW_ACTION_STATUSES, WORKFLOW_STEP_STATUSES, normalize_workflow_status

__version__ = "1.18.0"
__all__ = [
    "PlatformXeClient",
    "AsyncPlatformXeClient",
    "PlatformXeError",
    "PlatformXeAPIError",
    "APIResponse",
    "PaginationMeta",
    # v1.1.0
    "register",
    # pending (Task 4, wave 2)
    "WORKFLOW_ACTION_STATUSES",
    "WORKFLOW_STEP_STATUSES",
    "normalize_workflow_status",
]

# v1.6.0 (2026-09-15): documents.create_folder/list_folders and
# documents.request_override/process_override now send the real
# ownerType/ownerId and overrideReason/action shapes the fixed-storage API
# actually accepts, instead of fields it always rejected (create_folder,
# list_folders) or undocumented camelCase kwargs (request_override,
# process_override). list_folders is renamed get_folder_by_owner — the old
# name always 400'd against the live API, so there was no working behavior
# to preserve under the old name.

# v1.15.0 (2026-11-22, pending release): client.license.get (GET
#   /api/v1/license, scope license:read: the key's organisation's
#   Enterprise License state, validity, edition and granted plugins; never
#   money). Docs: fraud.activate answers billing LICENSED and 403
#   LICENSE_REQUIRED (after the licensing cut-over, no live license grant);
#   issues.create answers 409 CONTACT_LICENSING for a plan-change request
#   naming PRO or ENTERPRISE; exports.create_export of dataType invoices
#   also needs billing:read (403), and get_export of one is 404 without it.
#   Sync and async.

# v1.14.0 (2026-11-20, pending release): pdf.generate (POST
#   /api/v1/pdf/generate, scope pdf:generate: HTML or a stored template to a
#   stored PDF with a signed URL, or base64); qr.generate_batch reshaped for
#   POST /api/v1/qr/batch (format / zip / url_ttl_seconds keywords; items
#   stored with signed URLs; the route did not exist before, so every call
#   was a 404); new client.billing (list_invoices / get_invoice, scope
#   billing:read, money as kobo strings). pdf.generate and
#   qr.generate_batch take idempotency_key (x-idempotency-key). Sync and
#   async.

# v1.13.0 (2026-11-19, pending release): fraud.rules.update / transition take
#   expected_version (409 VERSION_MISMATCH), shadow_report takes version;
#   events.replay sends fromTimestamp / toTimestamp (it sent from / to, which
#   the route never read) and takes event_types; events.log sends eventTypes
#   and takes from_ / to; create_subscription takes name (the API requires
#   it). Docs: RESTRICTED_EVENT_TYPE, restrictedEventTypes,
#   RESERVED_SEARCH_APP, FEED_MISSING, FEED_NOT_REALTIME.
#   Fidelity register fixes (2026-11-20): workflows.dry_run posts {entityData}
#   to /api/v1/workflows/{id} (the /dry-run path it used does not exist: every
#   call was a 404) and takes entity_data=; storage.reorder_files sends PATCH
#   (the route takes no POST). Sync and async. Fix rounds: a dry_run context
#   whose keys are all trigger-context keys sends its entityData (else
#   payload) object, any other dict is sent whole (as the Go SDK); workflow
#   ids are URL-quoted and an empty id raises ValueError.
#   Fidelity W2 (2026-11-20): events.ingest sends entityData
#   (entity_data=; it sent payload, which POST /api/v1/events does not read,
#   so no trigger saw the event data), plus source_app / metadata; payload is
#   a deprecated alias sent as entityData when entity_data is absent.

# v1.12.0 (2026-11-13, pending release): identity.verify_business, sync and
#   async (POST /api/v1/identity/verify-business, scope business:verify).

# v1.11.0 (2026-11-08, pending release): the async client gains the identity
#   verifications (verify_bvn / verify_nin / verify_account / liveness /
#   face_match), providers_health and identity.dlq, and messaging
#   build_whatsapp_link / whatsapp_health, as the sync client has; both share
#   identity.py's body builders. liveness / face_match take optional content
#   types. check_batch is annotated as the list the route answers. Fix: the
#   identity verifications, the DLQ replay and fraud.decide send the
#   idempotency key as x-idempotency-key, the header PlatformXe reads; the
#   Idempotency-Key sent before was ignored, so a retry ran again.
# v1.10.0 (2026-11-07, released): identity.lookup() takes purpose and
#   consent_reference (required by the route); verify_nin() requires
#   date_of_birth; face_match(reference_verification_id=) compares with a
#   verified NIN check's registry photo (types 3.11.0).
# v1.9.0 (2026-11-07, pending release): fraud.activate() turns the Detection
# Pack on for the key's own organisation (POST /api/v1/fraud/activate), and
# fraud.terms.status() now answers detectionPackEnabled / detectionPackEnabledAt
# (also before the pack is on).

# v1.8.0 (2026-11-07, pending release): identity.verify(..., supporting_nin=)
# sends supporting.nin, the holder's NIN a PASSPORT check needs (with
# date_of_birth) to reach the primary provider. Also ships the untagged changes since
# v1.7.0 (create_override replace, AI_MODEL_UNAVAILABLE).

# v1.7.0 (2026-10-08): client.ai (complete / extract / profile / usage) and
# client.vision (analyze_room) for the AI gateway and vision routes
# (caldera-platformxe#22). PlatformXeAPIError carries .details (the envelope's
# error.details) and .retry_after (the Retry-After header, seconds).

# v1.7.0 (2026-10-08, pending release): client.knowledge (upsert_document /
# delete_document / list_documents / search) for /api/v1/ai/knowledge/*, and
# tool calling on client.ai.complete (tools / tool_choice) —
# calderasuite/caldera-xadmin#29.
