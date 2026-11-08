# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-09-15  v1.6.0  Folder and deletion-override methods now match the real
#   fixed-storage API (POST/GET /api/v1/storage/fixed/folders,
#   POST /overrides, PATCH /overrides/:id):
#   - create_folder(owner_type, owner_id) sends {ownerType, ownerId}. The old
#     (name, parent_id, description) form sent a body the route has never
#     accepted — every call 400'd, so there is no working call to preserve.
#   - get_folder_by_owner(owner_type, owner_id) added. There is no
#     list-all-folders route (GET /folders requires ?ownerType=&ownerId= and
#     returns ONE folder), so list_folders() always 400'd.
#   - request_override()/process_override() gained explicit snake_case
#     parameters matching the request bodies.
# 2026-09-15  v1.6.0  (review fix) Backward compatibility under the minor bump:
#   - request_override/process_override again accept the pre-1.6.0 **kwargs
#     form. Callers who passed the real camelCase field names (documentId=,
#     overrideReason=, rejectionReason=, operatorId=, ...) had working calls;
#     those kwargs are mapped onto the explicit parameters (unknown kwargs are
#     still forwarded verbatim, as before) with a DeprecationWarning.
#   - list_folders() is kept as a deprecated method instead of being removed:
#     with no owner it raises NotImplementedError naming get_folder_by_owner;
#     given owner_type/owner_id it warns and delegates.
#   - The body builders below are shared with AsyncDocumentsService
#     (async_services.py) so the two clients cannot drift again.
# =============================================================================

"""Documents service — fixed documents, folders, and deletion overrides."""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


LIST_FOLDERS_UNSUPPORTED = "platformxe: list_folders is not supported by the API — use get_folder_by_owner"

# (python parameter, JSON field) pairs, in signature order.
_REQUEST_OVERRIDE_FIELDS: Sequence[Tuple[str, str]] = (
    ("document_id", "documentId"),
    ("override_reason", "overrideReason"),
    ("authority_reference", "authorityReference"),
    ("authority_type", "authorityType"),
    ("authority_document", "authorityDocument"),
    ("operator_id", "operatorId"),
)
_PROCESS_OVERRIDE_FIELDS: Sequence[Tuple[str, str]] = (
    ("action", "action"),
    ("rejection_reason", "rejectionReason"),
    ("operator_id", "operatorId"),
)


def _build_body(
    method: str,
    fields: Sequence[Tuple[str, str]],
    explicit: Dict[str, Any],
    legacy_kwargs: Dict[str, Any],
    required: Sequence[str],
) -> Dict[str, Any]:
    """Merge explicit parameters with the deprecated camelCase **kwargs form."""
    legacy = dict(legacy_kwargs)
    if legacy:
        warnings.warn(
            f"{method}(**kwargs) with API field names is deprecated; "
            f"use the explicit parameters ({', '.join(p for p, _ in fields)}).",
            DeprecationWarning,
            stacklevel=4,
        )
    body: Dict[str, Any] = {}
    for param, wire in fields:
        value = explicit.get(param)
        if wire in legacy and wire != param:
            if value is not None:
                raise TypeError(f"{method}() got both '{param}' and '{wire}' for the same field")
            value = legacy.pop(wire)
        if value is not None:
            body[wire] = value
    # The pre-1.6.0 form forwarded every kwarg verbatim — keep doing so for
    # fields this version doesn't name.
    body.update(legacy)
    for param, wire in fields:
        if param in required and wire not in body:
            raise TypeError(f"{method}() missing required argument: '{param}'")
    return body


def build_request_override_body(explicit: Dict[str, Any], legacy_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """JSON body for POST /api/v1/storage/fixed/overrides (shared by sync + async)."""
    return _build_body(
        "request_override", _REQUEST_OVERRIDE_FIELDS, explicit, legacy_kwargs,
        required=("document_id", "override_reason"),
    )


def build_process_override_body(explicit: Dict[str, Any], legacy_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """JSON body for PATCH /api/v1/storage/fixed/overrides/:id (shared by sync + async)."""
    return _build_body(
        "process_override", _PROCESS_OVERRIDE_FIELDS, explicit, legacy_kwargs,
        required=("action",),
    )


def folder_owner_params(owner_type: str, owner_id: str) -> Dict[str, str]:
    """Query params / body for the owner-scoped folder endpoints."""
    return {"ownerType": owner_type, "ownerId": owner_id}


def check_deprecated_list_folders(owner_type: Optional[str], owner_id: Optional[str]) -> None:
    """list_folders() has no API route. Raise without an owner; warn with one."""
    if not owner_type or not owner_id:
        raise NotImplementedError(LIST_FOLDERS_UNSUPPORTED)
    warnings.warn(
        "list_folders(owner_type, owner_id) is deprecated — use get_folder_by_owner(owner_type, owner_id); "
        "it returns ONE folder, not a list.",
        DeprecationWarning,
        stacklevel=3,
    )


class DocumentsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list_documents(self, folder_id: Optional[str] = None, page: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if folder_id:
            params["folderId"] = folder_id
        if page:
            params["page"] = str(page)
        return self._client.get("/api/v1/storage/fixed/documents", params=params)

    def get_document(self, document_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/storage/fixed/documents/{document_id}")

    def create_document(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new fixed document."""
        return self._client.post("/api/v1/storage/fixed/documents", json=kwargs)

    def update_document(self, document_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Update a fixed document."""
        return self._client.patch(f"/api/v1/storage/fixed/documents/{document_id}", json=kwargs)

    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a fixed document. Retention-protected documents answer
        DELETE_BLOCKED — see request_override()/process_override() to
        request and execute a deletion override instead of retrying this
        call; approval does not change this document's own fields, so
        retrying delete_document() will not succeed on its own."""
        return self._client.delete(f"/api/v1/storage/fixed/documents/{document_id}")

    def get_folder_by_owner(self, owner_type: str, owner_id: str) -> Dict[str, Any]:
        """Get the folder for a given owner (one folder per owner_type+owner_id).

        owner_type must be one of "ADMIN", "AGENT", "PARTNER", "SYSTEM".
        """
        return self._client.get("/api/v1/storage/fixed/folders", params=folder_owner_params(owner_type, owner_id))

    def list_folders(self, owner_type: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
        """Deprecated — the API has no list-folders route.

        Without an owner this raises NotImplementedError; with owner_type and
        owner_id it warns and returns get_folder_by_owner(owner_type, owner_id).
        """
        check_deprecated_list_folders(owner_type, owner_id)
        return self.get_folder_by_owner(owner_type, owner_id)  # type: ignore[arg-type]

    def get_folder(self, folder_id: str) -> Dict[str, Any]:
        """Get a folder by ID."""
        return self._client.get(f"/api/v1/storage/fixed/folders/{folder_id}")

    def create_folder(self, owner_type: str, owner_id: str) -> Dict[str, Any]:
        """Create (or idempotently return) a storage folder for an owner.

        owner_type must be one of "ADMIN", "AGENT", "PARTNER", "SYSTEM".
        Returns {"folderId": "..."} — the new or existing folder's ID.
        """
        return self._client.post("/api/v1/storage/fixed/folders", json=folder_owner_params(owner_type, owner_id))

    def request_override(
        self,
        document_id: Optional[str] = None,
        override_reason: Optional[str] = None,
        authority_reference: Optional[str] = None,
        authority_type: Optional[str] = None,
        authority_document: Optional[str] = None,
        operator_id: Optional[str] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """Request a deletion override for a protected document.

        document_id and override_reason are required; override_reason must be
        at least 500 characters (audit/compliance requirement). operator_id,
        if given, identifies the human operator for four-eyes separation — it
        is always namespaced under your authenticated caller service
        server-side.

        The pre-1.6.0 form (documentId=..., overrideReason=..., ...) still
        works but emits a DeprecationWarning.
        """
        body = build_request_override_body(
            {
                "document_id": document_id,
                "override_reason": override_reason,
                "authority_reference": authority_reference,
                "authority_type": authority_type,
                "authority_document": authority_document,
                "operator_id": operator_id,
            },
            legacy_kwargs,
        )
        return self._client.post("/api/v1/storage/fixed/overrides", json=body)

    def process_override(
        self,
        override_id: str,
        action: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """Approve, reject, witness, or execute a deletion override.

        action is required: one of "approve", "reject", "witness", "execute".
        rejection_reason is required when action == "reject". Approve and
        witness must each be performed by a caller distinct from the
        requester (witness must also differ from the approver) — the API
        rejects self-approval/self-witnessing.

        Note: action == "execute" returns a DIFFERENT response shape
        ({"success": bool, "documentId": str}) than approve/reject/witness
        (the full override record) — this performs the actual soft-delete
        of the document as part of the call.

        The pre-1.6.0 form (rejectionReason=..., operatorId=...) still works
        but emits a DeprecationWarning.
        """
        body = build_process_override_body(
            {"action": action, "rejection_reason": rejection_reason, "operator_id": operator_id},
            legacy_kwargs,
        )
        return self._client.patch(f"/api/v1/storage/fixed/overrides/{override_id}", json=body)
