# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  Mount client.ai (AiService) and client.vision
#   (VisionService) on both clients for the AI gateway and vision routes
#   (caldera-platformxe#22, NO-DRIFT). _parse_response now carries the
#   envelope's error.details (e.g. details["path"] on 422 AI_OUTPUT_INVALID)
#   and the Retry-After header (seconds, on 429 AI_QUOTA_EXCEEDED /
#   RATE_LIMITED) onto PlatformXeAPIError.details / .retry_after.
# 2026-10-08  v1.7.0  (pending release, xadmin#29) Mount client.knowledge
#   (KnowledgeService / AsyncKnowledgeService) for /api/v1/ai/knowledge/*;
#   delete() takes optional query params (the knowledge DELETE is keyed by
#   ?collection=&sourceRef=).
# 2026-10-09  (pending release) Final review: _request takes per-call
#   timeout / retries / fail_open overrides, and post() / put() pass them
#   through, so the AI, vision and knowledge methods can wait for routes
#   longer than the 10 s default without being re-sent (every retried model
#   call is billed).
# =============================================================================

"""PlatformXe API client — synchronous and asynchronous."""

from __future__ import annotations
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING
import httpx

from .exceptions import PlatformXeError, PlatformXeAPIError
from .services.permissions import PermissionsService
from .services.identity import IdentityService
from .services.fraud import FraudService
from .services.messaging import MessagingService
from .services.webhooks import WebhooksService
from .services.templates import TemplatesService
from .services.storage import StorageService
from .services.documents import DocumentsService
from .services.workflows import WorkflowsService
from .services.domains import DomainsService
from .services.events import EventsService
from .services.threads import ThreadsService
from .services.exports import ExportsService
from .services.ocr import OcrService
from .services.pdf import PdfService
from .services.qr import QrService
from .services.usage import UsageService
from .services.audit import AuditService
from .services.issues import IssuesService
from .services.search import SearchService
from .services.whoami import WhoamiService
from .services.ai import AiService
from .services.vision import VisionService
from .services.knowledge import KnowledgeService


def _retry_after(response: httpx.Response) -> Optional[int]:
    """The Retry-After header in whole seconds, when present and numeric."""
    raw = response.headers.get("retry-after") or response.headers.get("Retry-After")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _parse_response(response: httpx.Response) -> Dict[str, Any]:
    """Parse an API response, raising on error."""
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        text = response.text[:200]
        if not response.is_success:
            raise PlatformXeAPIError(
                code=f"HTTP_{response.status_code}",
                message=text or response.reason_phrase,
                status_code=response.status_code,
            )
        raise PlatformXeError(f"Expected JSON but received {content_type}: {text}")

    data = response.json()

    if not data.get("success", False):
        error = data.get("error", {})
        details = error.get("details") if isinstance(error, dict) else None
        raise PlatformXeAPIError(
            code=error.get("code", "UNKNOWN"),
            message=error.get("message", "Unknown error"),
            status_code=response.status_code,
            details=details if isinstance(details, dict) else None,
            retry_after=_retry_after(response),
        )

    return data.get("data", data)


def _build_file_tuple(path: Path) -> tuple:
    """Build an (filename, file_bytes, content_type) tuple for multipart upload."""
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return (path.name, path.read_bytes(), content_type)


class PlatformXeClient:
    """Synchronous client for the PlatformXe API.

    Usage:
        client = PlatformXeClient(api_key="pxk_live_...")
        result = client.permissions.check(admin_id="usr_123", path="chat/session", action="READ")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://platformxe.com",
        timeout: float = 10.0,
        retries: int = 2,
        fail_open: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.fail_open = fail_open
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

        # Service namespaces
        self.documents = DocumentsService(self)
        self.domains = DomainsService(self)
        self.events = EventsService(self)
        self.exports = ExportsService(self)
        self.identity = IdentityService(self)
        self.fraud = FraudService(self)
        self.messaging = MessagingService(self)
        self.ocr = OcrService(self)
        self.pdf = PdfService(self)
        self.permissions = PermissionsService(self)
        self.qr = QrService(self)
        self.storage = StorageService(self)
        self.templates = TemplatesService(self)
        self.threads = ThreadsService(self)
        self.usage = UsageService(self)
        self.webhooks = WebhooksService(self)
        self.workflows = WorkflowsService(self)
        # v1.1.0
        self.audit = AuditService(self)
        self.issues = IssuesService(self)
        self.search = SearchService(self)
        self.whoami = WhoamiService(self)
        # v1.7.0
        self.ai = AiService(self)
        self.vision = VisionService(self)
        self.knowledge = KnowledgeService(self)

    # ── Utility methods (not part of a service resource) ────────────────

    def send_telemetry(
        self,
        source_app: str,
        package_name: str,
        metrics: List[Dict[str, Any]],
        period_start: str,
        period_end: str,
        package_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send SDK telemetry metrics."""
        return self.post("/api/v1/telemetry", json={
            "sourceApp": source_app,
            "packageName": package_name,
            "packageVersion": package_version,
            "metrics": metrics,
            "periodStart": period_start,
            "periodEnd": period_end,
        })

    def health_check(self) -> Dict[str, Any]:
        """Check platform health."""
        return self.get("/api/health")

    # ── HTTP internals ───────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        fail_open: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry and error handling.

        ``timeout`` / ``retries`` / ``fail_open`` override the client's
        settings for this one call (the AI routes run far longer than the
        10 s default and must not be re-sent — every attempt is billed).
        """
        last_error: Optional[Exception] = None
        max_retries = self.retries if retries is None else retries
        if timeout is not None:
            kwargs["timeout"] = timeout

        for attempt in range(max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
                return _parse_response(response)

            except PlatformXeAPIError:
                raise  # Don't retry API errors (4xx)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(0.2 * (2 ** attempt))  # Exponential backoff

        if self.fail_open if fail_open is None else fail_open:
            return {"error": str(last_error), "_failed": True}
        raise PlatformXeError(f"Request failed after {max_retries + 1} attempts: {last_error}")

    def get(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"params": params}
        if headers:
            kwargs["headers"] = headers
        return self._request("GET", path, **kwargs)

    def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **call: Any,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return self._request("POST", path, **call, **kwargs)

    def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **call: Any,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return self._request("PUT", path, **call, **kwargs)

    def patch(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return self._request("PATCH", path, **kwargs)

    def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if params:
            kwargs["params"] = params
        if headers:
            kwargs["headers"] = headers
        return self._request("DELETE", path, **kwargs)

    def upload(self, path: str, file_path: Path, *, fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Upload a single file via multipart form data."""
        files = {"file": _build_file_tuple(file_path)}
        data = fields or {}
        return self._request("POST", path, files=files, data=data)

    def upload_many(self, path: str, file_paths: Sequence[Path], *, fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Upload multiple files via multipart form data."""
        files = [("files", _build_file_tuple(p)) for p in file_paths]
        data = fields or {}
        return self._request("POST", path, files=files, data=data)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "PlatformXeClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncPlatformXeClient:
    """Asynchronous client for the PlatformXe API.

    Usage:
        async with AsyncPlatformXeClient(api_key="pxk_live_...") as client:
            result = await client.permissions.check(admin_id="usr_123", path="chat/session", action="READ")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://platformxe.com",
        timeout: float = 10.0,
        retries: int = 2,
        fail_open: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.fail_open = fail_open
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

        # Async service namespaces
        from .services.async_services import (
            AsyncAiService,
            AsyncDocumentsService,
            AsyncDomainsService,
            AsyncEventsService,
            AsyncExportsService,
            AsyncIdentityService,
            AsyncKnowledgeService,
            AsyncMessagingService,
            AsyncOcrService,
            AsyncPdfService,
            AsyncPermissionsService,
            AsyncQrService,
            AsyncStorageService,
            AsyncTemplatesService,
            AsyncThreadsService,
            AsyncUsageService,
            AsyncVisionService,
            AsyncWebhooksService,
            AsyncWorkflowsService,
        )
        self.documents = AsyncDocumentsService(self)
        self.domains = AsyncDomainsService(self)
        self.events = AsyncEventsService(self)
        self.exports = AsyncExportsService(self)
        self.identity = AsyncIdentityService(self)
        self.messaging = AsyncMessagingService(self)
        self.ocr = AsyncOcrService(self)
        self.pdf = AsyncPdfService(self)
        self.permissions = AsyncPermissionsService(self)
        self.qr = AsyncQrService(self)
        self.storage = AsyncStorageService(self)
        self.templates = AsyncTemplatesService(self)
        self.threads = AsyncThreadsService(self)
        self.usage = AsyncUsageService(self)
        self.webhooks = AsyncWebhooksService(self)
        self.workflows = AsyncWorkflowsService(self)
        # v1.7.0
        self.ai = AsyncAiService(self)
        self.vision = AsyncVisionService(self)
        self.knowledge = AsyncKnowledgeService(self)

    # ── Utility methods (not part of a service resource) ────────────────

    async def send_telemetry(
        self,
        source_app: str,
        package_name: str,
        metrics: List[Dict[str, Any]],
        period_start: str,
        period_end: str,
        package_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send SDK telemetry metrics."""
        return await self.post("/api/v1/telemetry", json={
            "sourceApp": source_app,
            "packageName": package_name,
            "packageVersion": package_version,
            "metrics": metrics,
            "periodStart": period_start,
            "periodEnd": period_end,
        })

    async def health_check(self) -> Dict[str, Any]:
        """Check platform health."""
        return await self.get("/api/health")

    # ── HTTP internals ───────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        fail_open: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make an async HTTP request with retry and error handling (per-call overrides as on the sync client)."""
        import asyncio

        last_error: Optional[Exception] = None
        max_retries = self.retries if retries is None else retries
        if timeout is not None:
            kwargs["timeout"] = timeout

        for attempt in range(max_retries + 1):
            try:
                response = await self._client.request(method, path, **kwargs)
                return _parse_response(response)

            except PlatformXeAPIError:
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(0.2 * (2 ** attempt))

        if self.fail_open if fail_open is None else fail_open:
            return {"error": str(last_error), "_failed": True}
        raise PlatformXeError(f"Request failed after {max_retries + 1} attempts: {last_error}")

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"params": params}
        if headers:
            kwargs["headers"] = headers
        return await self._request("GET", path, **kwargs)

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **call: Any,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return await self._request("POST", path, **call, **kwargs)

    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **call: Any,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return await self._request("PUT", path, **call, **kwargs)

    async def patch(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"json": json or {}}
        if headers:
            kwargs["headers"] = headers
        return await self._request("PATCH", path, **kwargs)

    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if params:
            kwargs["params"] = params
        if headers:
            kwargs["headers"] = headers
        return await self._request("DELETE", path, **kwargs)

    async def upload(self, path: str, file_path: Path, *, fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Upload a single file via multipart form data."""
        files = {"file": _build_file_tuple(file_path)}
        data = fields or {}
        return await self._request("POST", path, files=files, data=data)

    async def upload_many(self, path: str, file_paths: Sequence[Path], *, fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Upload multiple files via multipart form data."""
        files = [("files", _build_file_tuple(p)) for p in file_paths]
        data = fields or {}
        return await self._request("POST", path, files=files, data=data)

    async def close(self) -> None:
        """Close the async HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncPlatformXeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
