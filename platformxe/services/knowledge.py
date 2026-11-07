# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  Created (pending release, calderasuite/caldera-xadmin#29).
#   KnowledgeService.upsert_document / delete_document / list_documents /
#   search for PUT / DELETE / GET /api/v1/ai/knowledge/documents and POST
#   /api/v1/ai/knowledge/search — scope ai:knowledge, 1,200 requests/hr/key.
#   Bodies mirror KnowledgeUpsertDocumentRequest / KnowledgeSearchRequest in
#   @caldera/platformxe-types 3.6.0; responses pass through unchanged
#   (camelCase keys). The builders are module-level so AsyncKnowledgeService
#   (async_services.py) sends byte-identical requests.
# 2026-10-09  (pending release) Final review: upsert_document waits up to 65 s
#   and search up to 35 s (UPSERT_CALL_OPTIONS / SEARCH_CALL_OPTIONS) — the
#   routes embed inline and run longer than the client's 10 s default.
# =============================================================================

"""Knowledge retrieval service — index, list, delete and search documents."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


#: Per-call timeouts: an upsert embeds inline (route limit 60 s), a search
#: embeds the query (route limit 30 s); the client default is 10 s.
UPSERT_CALL_OPTIONS: Dict[str, Any] = {"timeout": 65.0}
SEARCH_CALL_OPTIONS: Dict[str, Any] = {"timeout": 35.0}


def build_upsert_document_body(
    feature_key: str,
    collection: str,
    source_ref: str,
    title: str,
    text: str,
    url: Optional[str] = None,
    acl: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """KnowledgeUpsertDocumentRequest: {featureKey, collection, sourceRef,
    title, text, url?, acl?}."""
    body: Dict[str, Any] = {
        "featureKey": feature_key,
        "collection": collection,
        "sourceRef": source_ref,
        "title": title,
    }
    if url is not None:
        body["url"] = url
    if acl is not None:
        body["acl"] = acl
    body["text"] = text
    return body


def build_document_ref_params(collection: str, source_ref: str) -> Dict[str, str]:
    """DELETE query: collection + sourceRef."""
    return {"collection": collection, "sourceRef": source_ref}


def build_list_params(
    collection: str,
    cursor: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, str]:
    """GET query: collection, then cursor / limit only when given."""
    params: Dict[str, str] = {"collection": collection}
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = str(limit)
    return params


def build_search_body(
    feature_key: str,
    collections: List[str],
    query: str,
    acl_tags: List[str],
    k: Optional[int] = None,
) -> Dict[str, Any]:
    """KnowledgeSearchRequest: {featureKey, collections, query, k?, aclTags}."""
    body: Dict[str, Any] = {
        "featureKey": feature_key,
        "collections": collections,
        "query": query,
    }
    if k is not None:
        body["k"] = k
    body["aclTags"] = acl_tags
    return body


class KnowledgeService:
    """Knowledge retrieval (scope ``ai:knowledge``).

    Documents belong to the API key's caller service. Text is stored as sent
    — PlatformXe does NOT redact personal data at index time, so never send
    Tier-1 / Tier-2 personal data. ``acl`` tags are opaque: a searcher sees a
    document when its ``acl_tags`` hold ANY of the document's tags, or when
    the document has none. Errors raise
    :class:`~platformxe.exceptions.PlatformXeAPIError` with the closed
    ProductAiErrorCode set as ``code``.
    """

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def upsert_document(
        self,
        feature_key: str,
        collection: str,
        source_ref: str,
        title: str,
        text: str,
        url: Optional[str] = None,
        acl: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or replace one document (``text`` ≤ 400,000 characters,
        markdown or plain). Returns ``{collection, sourceRef, changed,
        chunkCount, pendingEmbeddings}``."""
        return self._client.put(
            "/api/v1/ai/knowledge/documents",
            json=build_upsert_document_body(feature_key, collection, source_ref, title, text, url, acl),
            **UPSERT_CALL_OPTIONS,
        )

    def delete_document(self, collection: str, source_ref: str) -> Dict[str, Any]:
        """Delete one document (idempotent). Returns ``{collection, sourceRef, deleted}``."""
        return self._client.delete(
            "/api/v1/ai/knowledge/documents",
            params=build_document_ref_params(collection, source_ref),
        )

    def list_documents(
        self,
        collection: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """One page of a collection's documents (no text). Returns
        ``{items, nextCursor}``; pass ``nextCursor`` back as ``cursor``."""
        return self._client.get(
            "/api/v1/ai/knowledge/documents",
            params=build_list_params(collection, cursor, limit),
        )

    def search(
        self,
        feature_key: str,
        collections: List[str],
        query: str,
        acl_tags: List[str],
        k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Hybrid search (``k`` 1-20, default 8). Returns ``{mode, hits}``;
        each hit carries ``sourceRef`` + ``ordinal`` for citation."""
        return self._client.post(
            "/api/v1/ai/knowledge/search",
            json=build_search_body(feature_key, collections, query, acl_tags, k),
            **SEARCH_CALL_OPTIONS,
        )
