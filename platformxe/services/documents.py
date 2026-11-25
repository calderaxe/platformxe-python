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
# 2026-11-18  v1.12.0  documents.categories (list / create / update /
#   deactivate: /api/v1/storage/fixed/categories) and documents.settings
#   (get / update: /api/v1/storage/fixed/settings), the tenant category
#   registry and its enforcement switch. Both are per caller service within
#   the key's organisation. Bodies and params are built by the helpers below,
#   shared with the async client.
# =============================================================================

"""Documents service — fixed documents, folders, deletion overrides, and the
category registry and settings."""

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


# --- category registry and settings (1.12.0) --------------------------------

CATEGORIES_PATH = "/api/v1/storage/fixed/categories"
SETTINGS_PATH = "/api/v1/storage/fixed/settings"

# Retention types and who may delete (the API's enums; a value outside them is 400).
RETENTION_TYPES = ("NONE", "STANDARD", "EXTENDED", "LEGAL", "PERMANENT")
DELETABLE_BY = ("OWNER", "ADMIN", "SUPER_ADMIN", "NONE")


class _Unset:
    """Marks an update field that was not passed (None is sent: it clears the field)."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "UNSET"


UNSET: Any = _Unset()

# (python parameter, JSON field) pairs for a category body.
_CATEGORY_FIELDS: Sequence[Tuple[str, str]] = (
    ("label", "label"),
    ("description", "description"),
    ("sort_order", "sortOrder"),
    ("color", "color"),
    ("is_active", "isActive"),
    ("retention_type", "retentionType"),
    ("retention_days", "retentionDays"),
    ("deletable_by", "deletableBy"),
    ("requires_override", "requiresOverride"),
    ("requires_witness", "requiresWitness"),
)


def category_body(values: Dict[str, Any], *, send_none: bool) -> Dict[str, Any]:
    """The JSON body of a category create (``send_none=False``: None is not
    sent) or update (``send_none=True``: None is sent and clears the field).
    UNSET is never sent."""
    body: Dict[str, Any] = {}
    for param, wire in _CATEGORY_FIELDS:
        if param not in values:
            continue
        value = values[param]
        if value is UNSET or (value is None and not send_none):
            continue
        body[wire] = value
    return body


def category_key_params(key: str) -> Dict[str, str]:
    """The ``?key=`` query of the PATCH and DELETE category calls."""
    return {"key": key}


def category_list_params(include_inactive: bool) -> Optional[Dict[str, str]]:
    return {"includeInactive": "true"} if include_inactive else None


class DocumentCategoriesService:
    """The tenant category registry (``/api/v1/storage/fixed/categories``).

    Categories belong to the key's caller service within its organisation:
    another tenant using the same caller name never sees or changes them. A
    field of the wrong type is 400 ``BAD_REQUEST`` naming the field; a key
    that normalises to nothing is 400 ``VALIDATION_ERROR``; a duplicate key
    on create is 409 ``CONFLICT``; an unknown key on update / deactivate 404.
    """

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def list(self, include_inactive: bool = False) -> Dict[str, Any]:
        """GET: ``{"categories": [...]}``, active ones only unless asked."""
        return self._client.get(CATEGORIES_PATH, params=category_list_params(include_inactive))

    def create(
        self,
        key: str,
        label: str,
        *,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
        color: Optional[str] = None,
        retention_type: Optional[str] = None,
        retention_days: Optional[int] = None,
        deletable_by: Optional[str] = None,
        requires_override: Optional[bool] = None,
        requires_witness: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """POST: register a category (201, ``{"category": {...}}``). The key is
        stored in UPPER_SNAKE. ``retention_type`` is one of RETENTION_TYPES,
        ``deletable_by`` one of DELETABLE_BY, ``retention_days`` a
        non-negative integer; a field left None is not sent (the platform
        default applies)."""
        body: Dict[str, Any] = {"key": key}
        body.update(category_body({
            "label": label, "description": description, "sort_order": sort_order,
            "color": color, "retention_type": retention_type,
            "retention_days": retention_days, "deletable_by": deletable_by,
            "requires_override": requires_override, "requires_witness": requires_witness,
        }, send_none=False))
        return self._client.post(CATEGORIES_PATH, json=body)

    def update(
        self,
        key: str,
        *,
        label: Any = UNSET,
        description: Any = UNSET,
        sort_order: Any = UNSET,
        color: Any = UNSET,
        is_active: Any = UNSET,
        retention_type: Any = UNSET,
        retention_days: Any = UNSET,
        deletable_by: Any = UNSET,
        requires_override: Any = UNSET,
        requires_witness: Any = UNSET,
    ) -> Dict[str, Any]:
        """PATCH ``?key=``: change only the fields passed. None clears
        ``description``, ``color``, ``retention_type``, ``retention_days`` or
        ``deletable_by`` (back to the platform default); the other fields do
        not take None (400)."""
        body = category_body({
            "label": label, "description": description, "sort_order": sort_order,
            "color": color, "is_active": is_active, "retention_type": retention_type,
            "retention_days": retention_days, "deletable_by": deletable_by,
            "requires_override": requires_override, "requires_witness": requires_witness,
        }, send_none=True)
        return self._client.patch(CATEGORIES_PATH, json=body, params=category_key_params(key))

    def deactivate(self, key: str) -> Dict[str, Any]:
        """DELETE ``?key=``: soft-disable the category; its documents keep it."""
        return self._client.delete(CATEGORIES_PATH, params=category_key_params(key))


class DocumentSettingsService:
    """Fixed-storage settings (``/api/v1/storage/fixed/settings``), per caller
    service within the key's organisation."""

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def get(self) -> Dict[str, Any]:
        """GET: ``{"settings": {"enforceCategories": bool}}`` (off by default)."""
        return self._client.get(SETTINGS_PATH)

    def update(self, enforce_categories: bool) -> Dict[str, Any]:
        """PATCH ``{"enforceCategories": bool}``. When on, a document whose
        category is not registered and active is refused (``INVALID_CATEGORY``).
        A non-boolean is 400."""
        return self._client.patch(SETTINGS_PATH, json={"enforceCategories": enforce_categories})


class DocumentsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client
        self.categories = DocumentCategoriesService(client)
        self.settings = DocumentSettingsService(client)

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
