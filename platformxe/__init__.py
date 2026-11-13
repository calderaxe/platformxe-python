# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""PlatformXe Python SDK — messaging, storage, authorization, identity resolution, product AI, vision."""

from .client import PlatformXeClient, AsyncPlatformXeClient
from .exceptions import PlatformXeError, PlatformXeAPIError
from .types import APIResponse, PaginationMeta
from .register import register
from .services.workflows import WORKFLOW_ACTION_STATUSES, WORKFLOW_STEP_STATUSES, normalize_workflow_status

__version__ = "1.12.0"
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
