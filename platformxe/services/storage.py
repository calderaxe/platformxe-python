# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Storage service — media file uploads and management."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class StorageService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    # Media — direct uploads

    def upload_file(
        self,
        file_path: Union[str, Path],
        *,
        module: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a single file via multipart form data."""
        path = Path(file_path)
        fields: Dict[str, Any] = {}
        if module:
            fields["module"] = module
        if entity_id:
            fields["entityId"] = entity_id
        return self._client.upload("/api/v1/storage/media/upload", path, fields=fields)

    def batch_upload(
        self,
        file_paths: Sequence[Union[str, Path]],
        *,
        module: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload multiple files in a single request via multipart form data."""
        paths = [Path(p) for p in file_paths]
        fields: Dict[str, Any] = {}
        if module:
            fields["module"] = module
        if entity_id:
            fields["entityId"] = entity_id
        return self._client.upload_many("/api/v1/storage/media/upload/batch", paths, fields=fields)

    # Media — signed upload flow

    def sign_upload(self, filename: str, content_type: str) -> Dict[str, Any]:
        return self._client.post("/api/v1/storage/media/sign-upload", json={"filename": filename, "contentType": content_type})

    def register_url(self, url: str, filename: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"url": url}
        if filename:
            body["filename"] = filename
        return self._client.post("/api/v1/storage/media/register", json=body)

    def list_files(self, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if page:
            params["page"] = str(page)
        if limit:
            params["limit"] = str(limit)
        return self._client.get("/api/v1/storage/media/files", params=params)

    def get_file(self, file_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/storage/media/files/{file_id}")

    def delete_file(self, file_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/storage/media/files/{file_id}")

    def reorder_files(self, file_ids: List[str]) -> Dict[str, Any]:
        return self._client.post("/api/v1/storage/media/files/reorder", json={"fileIds": file_ids})

    def get_processor(self) -> Dict[str, Any]:
        """Get the storage processor configuration."""
        return self._client.get("/api/v1/storage/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the storage processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/storage/processor", json=body)
