# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Tests for PlatformXe Python SDK — client initialization, HTTP behavior, error handling, and service coverage."""

import json
import pytest
import httpx
from unittest.mock import patch, MagicMock
from pathlib import Path
from platformxe import PlatformXeClient, AsyncPlatformXeClient, PlatformXeError, PlatformXeAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(data=None, success=True, status_code=200, error=None):
    """Build a mock httpx.Response with a JSON body."""
    body = {"success": success}
    if success:
        body["data"] = data or {}
    else:
        body["error"] = error or {"code": "TEST_ERROR", "message": "test"}
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK" if status_code == 200 else "Error"
    return resp


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

class TestClientInit:
    def test_defaults(self):
        client = PlatformXeClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.base_url == "https://platformxe.com"
        assert client.timeout == 10.0
        assert client.retries == 2
        assert client.fail_open is True
        client.close()

    def test_custom_config(self):
        client = PlatformXeClient(
            api_key="test",
            base_url="http://localhost:3000/",
            timeout=5.0,
            retries=0,
            fail_open=False,
        )
        assert client.base_url == "http://localhost:3000"
        assert client.timeout == 5.0
        assert client.retries == 0
        assert client.fail_open is False
        client.close()

    def test_trailing_slash_stripped(self):
        client = PlatformXeClient(api_key="t", base_url="https://example.com///")
        assert client.base_url == "https://example.com"
        client.close()

    def test_context_manager(self):
        with PlatformXeClient(api_key="test") as client:
            assert client.api_key == "test"


# ---------------------------------------------------------------------------
# HTTP behavior
# ---------------------------------------------------------------------------

class TestHTTPBehavior:
    def test_success_returns_data(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"roles": [{"id": "r1"}]})
        with patch.object(client._client, "request", return_value=mock_resp):
            result = client.get("/api/v1/permissions/roles")
        assert result == {"roles": [{"id": "r1"}]}
        client.close()

    def test_api_error_raises(self):
        client = PlatformXeClient(api_key="test", fail_open=False)
        mock_resp = _mock_response(
            success=False, status_code=404,
            error={"code": "NOT_FOUND", "message": "Role not found"},
        )
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.get("/api/v1/permissions/roles/missing")
        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.status_code == 404
        client.close()

    def test_api_error_not_retried(self):
        """API errors (structured error responses) should not be retried."""
        client = PlatformXeClient(api_key="test", retries=3, fail_open=False)
        mock_resp = _mock_response(
            success=False, status_code=400,
            error={"code": "VALIDATION", "message": "Bad input"},
        )
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.raises(PlatformXeAPIError):
                client.post("/api/v1/permissions/roles", json={})
        assert mock_req.call_count == 1  # Not retried
        client.close()

    def test_network_error_retries(self):
        """Network errors should be retried up to the configured count."""
        client = PlatformXeClient(api_key="test", retries=2, fail_open=False)
        with patch.object(
            client._client, "request", side_effect=httpx.ConnectError("connection refused")
        ) as mock_req:
            with pytest.raises(PlatformXeError, match="Request failed after 3 attempts"):
                client.get("/api/health")
        assert mock_req.call_count == 3  # Initial + 2 retries
        client.close()

    def test_fail_open_returns_error_dict(self):
        """When fail_open=True, network errors return an error dict instead of raising."""
        client = PlatformXeClient(api_key="test", retries=0, fail_open=True)
        with patch.object(
            client._client, "request", side_effect=httpx.ConnectError("refused")
        ):
            result = client.get("/api/health")
        assert result.get("_failed") is True
        assert "error" in result
        client.close()

    def test_non_json_response_raises(self):
        """Non-JSON responses should raise a meaningful error."""
        client = PlatformXeClient(api_key="test", retries=0, fail_open=False)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 502
        mock_resp.is_success = False
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.text = "<html>Bad Gateway</html>"
        mock_resp.reason_phrase = "Bad Gateway"
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.get("/api/health")
        assert exc_info.value.code == "HTTP_502"
        client.close()

    def test_post_sends_json_body(self):
        """POST requests should serialize body as JSON."""
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "role_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.post("/api/v1/permissions/roles", json={"name": "Admin"})
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"name": "Admin"}
        client.close()

    def test_request_headers_include_api_key(self):
        """Requests should include the x-api-key header."""
        client = PlatformXeClient(api_key="pxk_test_123")
        assert client._client.headers["x-api-key"] == "pxk_test_123"
        assert client._client.headers["accept"] == "application/json"
        client.close()


# ---------------------------------------------------------------------------
# Upload methods
# ---------------------------------------------------------------------------

class TestUploads:
    def test_upload_file_method_exists(self):
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client.storage, "upload_file", None))
        client.close()

    def test_batch_upload_method_exists(self):
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client.storage, "batch_upload", None))
        client.close()

    def test_upload_sends_multipart(self, tmp_path):
        """upload_file should use multipart form data."""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "file_1", "publicUrl": "https://cdn.example.com/test.png"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = client.storage.upload_file(test_file, module="media")
        assert result["id"] == "file_1"
        _, kwargs = mock_req.call_args
        assert "files" in kwargs
        client.close()


# ---------------------------------------------------------------------------
# Service namespace completeness
# ---------------------------------------------------------------------------

class TestServiceNamespaces:
    def test_all_services_present(self):
        client = PlatformXeClient(api_key="test")
        services = [
            "documents", "domains", "events", "exports", "identity",
            "messaging", "ocr", "pdf", "permissions", "qr",
            "storage", "templates", "threads", "usage", "webhooks", "workflows",
            "ai", "vision",
        ]
        for svc in services:
            assert hasattr(client, svc), f"Missing service: {svc}"
        client.close()

    def test_utility_methods_present(self):
        """Client has send_telemetry and health_check as direct methods."""
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client, "send_telemetry", None))
        assert callable(getattr(client, "health_check", None))
        client.close()

    def test_threads_service_methods(self):
        """Threads service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = [
            "create_channel", "list_channels", "update_channel",
            "get_escalation_config", "set_escalation_config",
            "create_thread", "list_threads", "get_thread", "close_thread", "reopen_thread",
            "entity_event", "send_message", "list_messages", "send_system_message",
            "edit_message", "delete_message", "mark_read", "get_read_states",
            "inbox", "unread_count", "flag_message", "escalate_thread", "review_flag", "list_flags",
        ]
        for method in methods:
            assert hasattr(client.threads, method), f"Missing method: threads.{method}"
        client.close()

    def test_storage_upload_methods(self):
        """Storage service has media-only methods."""
        client = PlatformXeClient(api_key="test")
        methods = [
            "upload_file", "batch_upload", "sign_upload", "register_url",
            "list_files", "get_file", "delete_file", "reorder_files",
        ]
        for method in methods:
            assert hasattr(client.storage, method), f"Missing method: storage.{method}"
        client.close()

    def test_documents_service_methods(self):
        """Documents service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = [
            "list_documents", "get_document", "create_document", "update_document", "delete_document",
            "get_folder_by_owner", "get_folder", "create_folder",
            "request_override", "process_override",
        ]
        for method in methods:
            assert hasattr(client.documents, method), f"Missing method: documents.{method}"
        client.close()

    def test_events_service_methods(self):
        """Events service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = [
            "ingest", "log", "list_subscriptions", "create_subscription",
            "get_subscription", "update_subscription", "delete_subscription", "replay",
        ]
        for method in methods:
            assert hasattr(client.events, method), f"Missing method: events.{method}"
        client.close()

    def test_events_custom_service_methods(self):
        """Tenant custom events surface (events.custom) has all expected methods."""
        client = PlatformXeClient(api_key="test")
        custom_methods = [
            "register", "list", "get", "archive", "emit", "dry_run", "health", "subscribe",
        ]
        for method in custom_methods:
            assert hasattr(client.events.custom, method), f"Missing method: events.custom.{method}"
        client.close()

    def test_events_custom_marketplace_methods(self):
        """Marketplace surface (events.custom.marketplace) has all expected methods."""
        client = PlatformXeClient(api_key="test")
        marketplace_methods = [
            "publish", "list", "get", "unpublish", "republish", "fork",
        ]
        for method in marketplace_methods:
            assert hasattr(client.events.custom.marketplace, method), \
                f"Missing method: events.custom.marketplace.{method}"
        client.close()

    def test_events_custom_federation_methods(self):
        """Federation surface (events.custom.federation) has all expected methods.

        Phase 9D ENTERPRISE-only surface — distinct from the v1.x.x
        permission federation at ``client.permissions.federation``.
        """
        client = PlatformXeClient(api_key="test")
        federation_methods = [
            "create_group", "list_groups", "get_group", "archive_group",
            "invite", "accept", "leave",
            "declare_push", "list_pushes", "undeclare_push",
            # Pattern 3 — external webhook peers (v1.5.0)
            "add_external_peer", "remove_external_peer",
        ]
        for method in federation_methods:
            assert hasattr(client.events.custom.federation, method), \
                f"Missing method: events.custom.federation.{method}"
        client.close()

    def test_exports_service_methods(self):
        """Exports service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = ["create_export", "get_export"]
        for method in methods:
            assert hasattr(client.exports, method), f"Missing method: exports.{method}"
        client.close()

    def test_ocr_service_methods(self):
        """OCR service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client.ocr, "verify_identity", None))
        client.close()

    def test_pdf_service_methods(self):
        """PDF service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = ["generate_offer_letter", "generate_property_flyer", "rasterize"]
        for method in methods:
            assert hasattr(client.pdf, method), f"Missing method: pdf.{method}"
        client.close()

    def test_qr_service_methods(self):
        """QR service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        methods = ["generate", "generate_batch"]
        for method in methods:
            assert hasattr(client.qr, method), f"Missing method: qr.{method}"
        client.close()

    def test_usage_service_methods(self):
        """Usage service has all expected methods."""
        client = PlatformXeClient(api_key="test")
        assert callable(getattr(client.usage, "summary", None))
        client.close()

    def test_permissions_complete(self):
        """Permissions service has the full method surface."""
        client = PlatformXeClient(api_key="test")
        methods = [
            "check", "check_batch", "resolve",
            "list_roles", "create_role", "get_role", "update_role", "delete_role",
            "get_role_capabilities", "set_role_capabilities",
            "get_role_module_permissions", "set_role_module_permissions",
            "list_overrides", "create_override", "delete_override",
            "list_policies", "create_policy", "update_policy", "delete_policy",
            "list_relationships", "update_relationships",
            "register_module", "list_modules",
            "get_audit_logs", "list_change_logs", "export_audit",
            "shadow_check",
            "create_federation_group", "list_federation_groups",
            "get_federation_group", "delete_federation_group",
            "add_federation_member", "accept_federation_membership", "remove_federation_member",
            "pull_federation_modules", "push_federation_permissions",
            "get_federation_status",
        ]
        for method in methods:
            assert hasattr(client.permissions, method), f"Missing method: permissions.{method}"
        client.close()

    def test_no_legacy_services(self):
        """Legacy misc and subscriptions services should not exist."""
        client = PlatformXeClient(api_key="test")
        assert not hasattr(client, "misc"), "Legacy 'misc' service should be removed"
        assert not hasattr(client, "subscriptions"), "Legacy 'subscriptions' service should be removed"
        client.close()


# ---------------------------------------------------------------------------
# Documents: folders and deletion overrides — real request/response shapes
#
# 2026-09-15: create_folder/list_folders (now get_folder_by_owner) and
# request_override/process_override previously sent bodies/params the real
# endpoints reject (or, for the override methods, only "worked" if the
# caller already knew the undocumented exact camelCase JSON field names).
# These pin the ACTUAL wire shape sent to the server, so a regression here
# means the SDK is once again sending something the route will 400 on.
# ---------------------------------------------------------------------------

class TestDocumentsFolderAndOverrideShapes:
    def test_create_folder_sends_owner_type_and_owner_id(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"folderId": "fld_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = client.documents.create_folder(owner_type="AGENT", owner_id="agent_1")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        assert result == {"folderId": "fld_1"}
        client.close()

    def test_get_folder_by_owner_sends_query_params(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "fld_1", "ownerType": "AGENT", "ownerId": "agent_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.documents.get_folder_by_owner(owner_type="AGENT", owner_id="agent_1")
        _, kwargs = mock_req.call_args
        assert kwargs["params"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        client.close()

    def test_request_override_sends_document_id_and_override_reason(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "PENDING"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.documents.request_override(document_id="doc_1", override_reason=reason)
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"documentId": "doc_1", "overrideReason": reason}
        client.close()

    def test_request_override_includes_optional_fields_only_when_given(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.documents.request_override(
                document_id="doc_1",
                override_reason=reason,
                authority_reference="case-123",
                operator_id="steven",
            )
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {
            "documentId": "doc_1",
            "overrideReason": reason,
            "authorityReference": "case-123",
            "operatorId": "steven",
        }
        client.close()

    def test_process_override_approve_sends_action_only(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "APPROVED"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.documents.process_override("ovr_1", action="approve")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "approve"}
        client.close()

    def test_process_override_reject_includes_rejection_reason(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "REJECTED"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.documents.process_override("ovr_1", action="reject", rejection_reason="still active")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "reject", "rejectionReason": "still active"}
        client.close()

    def test_process_override_execute_returns_the_distinct_response_shape(self):
        """action="execute" returns {success, documentId} — a different shape
        than approve/reject/witness's full override record. The method
        itself is shape-agnostic (returns whatever the server sends); this
        pins that the request is still {"action": "execute"} and the
        server's distinct response passes through untouched."""
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"success": True, "documentId": "doc_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = client.documents.process_override("ovr_1", action="execute")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "execute"}
        assert result == {"success": True, "documentId": "doc_1"}
        client.close()


class TestDocumentsBackwardCompat:
    """The pre-1.6.0 **kwargs call forms that actually worked against the API
    (real camelCase field names) must keep working under a minor bump —
    mapped onto the explicit parameters, with a DeprecationWarning."""

    def test_request_override_legacy_camelcase_kwargs_still_send_the_same_body(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "PENDING"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="request_override"):
                client.documents.request_override(
                    documentId="doc_1", overrideReason=reason,
                    authorityReference="case-123", authorityType="COURT_ORDER",
                    authorityDocument="doc_court", operatorId="steven",
                )
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {
            "documentId": "doc_1", "overrideReason": reason,
            "authorityReference": "case-123", "authorityType": "COURT_ORDER",
            "authorityDocument": "doc_court", "operatorId": "steven",
        }
        client.close()

    def test_request_override_explicit_form_emits_no_warning(self):
        import warnings
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                client.documents.request_override(document_id="doc_1", override_reason="x" * 500)
        client.close()

    def test_request_override_missing_required_raises_type_error(self):
        client = PlatformXeClient(api_key="test")
        with pytest.raises(TypeError, match="document_id"):
            client.documents.request_override(override_reason="x" * 500)
        client.close()

    def test_request_override_same_field_in_both_forms_raises_type_error(self):
        client = PlatformXeClient(api_key="test")
        with pytest.warns(DeprecationWarning), pytest.raises(TypeError, match="documentId"):
            client.documents.request_override(document_id="a", documentId="b", override_reason="x" * 500)
        client.close()

    def test_process_override_legacy_camelcase_kwargs_still_send_the_same_body(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "REJECTED"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="process_override"):
                client.documents.process_override(
                    "ovr_1", action="reject", rejectionReason="still active", operatorId="amaka",
                )
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "reject", "rejectionReason": "still active", "operatorId": "amaka"}
        client.close()

    def test_process_override_unknown_legacy_kwargs_are_still_forwarded(self):
        """The old form forwarded every kwarg verbatim; keep that for fields
        this SDK version doesn't name (the server ignores unknown fields)."""
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning):
                client.documents.process_override("ovr_1", action="approve", note="ok")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "approve", "note": "ok"}
        client.close()

    def test_process_override_missing_action_raises_type_error(self):
        client = PlatformXeClient(api_key="test")
        with pytest.raises(TypeError, match="action"):
            client.documents.process_override("ovr_1")
        client.close()

    def test_list_folders_without_owner_raises_not_implemented(self):
        client = PlatformXeClient(api_key="test")
        with pytest.raises(NotImplementedError, match="get_folder_by_owner"):
            client.documents.list_folders()
        client.close()

    def test_list_folders_with_owner_warns_and_delegates_to_get_folder_by_owner(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "fld_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="list_folders"):
                result = client.documents.list_folders(owner_type="AGENT", owner_id="agent_1")
        args, kwargs = mock_req.call_args
        assert args[0] == "GET"
        assert kwargs["params"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        assert result == {"id": "fld_1"}
        client.close()


class TestAsyncDocumentsFolderAndOverrideShapes:
    """AsyncDocumentsService must send exactly what DocumentsService sends."""

    @pytest.mark.asyncio
    async def test_create_folder_sends_owner_type_and_owner_id(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"folderId": "fld_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = await client.documents.create_folder(owner_type="AGENT", owner_id="agent_1")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        assert result == {"folderId": "fld_1"}
        await client.close()

    @pytest.mark.asyncio
    async def test_get_folder_by_owner_sends_query_params(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "fld_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.documents.get_folder_by_owner(owner_type="AGENT", owner_id="agent_1")
        _, kwargs = mock_req.call_args
        assert kwargs["params"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        await client.close()

    @pytest.mark.asyncio
    async def test_request_override_sends_document_id_and_override_reason(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "PENDING"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.documents.request_override(document_id="doc_1", override_reason=reason)
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"documentId": "doc_1", "overrideReason": reason}
        await client.close()

    @pytest.mark.asyncio
    async def test_request_override_includes_optional_fields_only_when_given(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.documents.request_override(
                document_id="doc_1", override_reason=reason,
                authority_reference="case-123", operator_id="steven",
            )
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {
            "documentId": "doc_1", "overrideReason": reason,
            "authorityReference": "case-123", "operatorId": "steven",
        }
        await client.close()

    @pytest.mark.asyncio
    async def test_process_override_approve_sends_action_only(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "APPROVED"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.documents.process_override("ovr_1", action="approve")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "approve"}
        await client.close()

    @pytest.mark.asyncio
    async def test_process_override_reject_includes_rejection_reason(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1", "status": "REJECTED"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.documents.process_override("ovr_1", action="reject", rejection_reason="still active")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "reject", "rejectionReason": "still active"}
        await client.close()

    @pytest.mark.asyncio
    async def test_process_override_execute_returns_the_distinct_response_shape(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"success": True, "documentId": "doc_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = await client.documents.process_override("ovr_1", action="execute")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "execute"}
        assert result == {"success": True, "documentId": "doc_1"}
        await client.close()

    @pytest.mark.asyncio
    async def test_request_override_legacy_camelcase_kwargs_warn_and_send_the_same_body(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        reason = "x" * 500
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="request_override"):
                await client.documents.request_override(documentId="doc_1", overrideReason=reason)
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"documentId": "doc_1", "overrideReason": reason}
        await client.close()

    @pytest.mark.asyncio
    async def test_process_override_legacy_camelcase_kwargs_warn_and_send_the_same_body(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "ovr_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="process_override"):
                await client.documents.process_override("ovr_1", action="reject", rejectionReason="no")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"action": "reject", "rejectionReason": "no"}
        await client.close()

    @pytest.mark.asyncio
    async def test_list_folders_without_owner_raises_not_implemented(self):
        client = AsyncPlatformXeClient(api_key="test")
        with pytest.raises(NotImplementedError, match="get_folder_by_owner"):
            await client.documents.list_folders()
        await client.close()

    @pytest.mark.asyncio
    async def test_list_folders_with_owner_warns_and_delegates(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"id": "fld_1"})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            with pytest.warns(DeprecationWarning, match="list_folders"):
                await client.documents.list_folders(owner_type="AGENT", owner_id="agent_1")
        _, kwargs = mock_req.call_args
        assert kwargs["params"] == {"ownerType": "AGENT", "ownerId": "agent_1"}
        await client.close()


# ---------------------------------------------------------------------------
# PDF: rasterize — real request/response shape
#
# 2026-09-21: pins the ACTUAL wire shape PdfService.rasterize/AsyncPdfService.
# rasterize send/receive against src/app/api/v1/pdf/rasterize/route.ts's
# RasterizePdfRequest ({pdfBase64, format, page?, dpi?}) and
# RasterizePdfResponse ({imageBase64, contentType, width, height, pageCount}).
# ---------------------------------------------------------------------------

class TestPdfRasterizeShape:
    def test_rasterize_sends_pdf_base64_as_pdfBase64(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={
            "imageBase64": "aW1n", "contentType": "image/jpeg",
            "width": 1240, "height": 1754, "pageCount": 3,
        })
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = client.pdf.rasterize(pdf_base64="JVBERi0=", format="jpeg")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"pdfBase64": "JVBERi0=", "format": "jpeg"}
        assert result == {
            "imageBase64": "aW1n", "contentType": "image/jpeg",
            "width": 1240, "height": 1754, "pageCount": 3,
        }
        client.close()

    def test_rasterize_includes_page_and_dpi_only_when_given(self):
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"imageBase64": "x", "contentType": "image/png", "width": 1, "height": 1, "pageCount": 1})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.pdf.rasterize(pdf_base64="JVBERi0=", format="png", page=2, dpi=300)
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"pdfBase64": "JVBERi0=", "format": "png", "page": 2, "dpi": 300}
        client.close()

    def test_rasterize_accepts_pdfBase64_kwarg_directly(self):
        """A caller passing the wire field name verbatim (pdfBase64=) still
        works — the pdf_base64-> pdfBase64 mapping only fires when the
        snake_case form is used, unknown/camelCase kwargs pass through."""
        client = PlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"imageBase64": "x", "contentType": "image/jpeg", "width": 1, "height": 1, "pageCount": 1})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.pdf.rasterize(pdfBase64="JVBERi0=", format="jpeg")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"pdfBase64": "JVBERi0=", "format": "jpeg"}
        client.close()

    def test_rasterize_error_propagates_as_api_error(self):
        """413 PAYLOAD_TOO_LARGE (oversized PDF / too many pages) surfaces as
        PlatformXeAPIError like every other endpoint's error path."""
        client = PlatformXeClient(api_key="test", fail_open=False)
        mock_resp = _mock_response(
            success=False, status_code=413,
            error={"code": "PAYLOAD_TOO_LARGE", "message": "Decoded PDF is too large"},
        )
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.pdf.rasterize(pdf_base64="JVBERi0=", format="jpeg")
        assert exc_info.value.code == "PAYLOAD_TOO_LARGE"
        assert exc_info.value.status_code == 413
        client.close()


class TestAsyncPdfRasterizeShape:
    @pytest.mark.asyncio
    async def test_rasterize_sends_pdf_base64_as_pdfBase64(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={
            "imageBase64": "aW1n", "contentType": "image/jpeg",
            "width": 1240, "height": 1754, "pageCount": 3,
        })
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = await client.pdf.rasterize(pdf_base64="JVBERi0=", format="jpeg")
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"pdfBase64": "JVBERi0=", "format": "jpeg"}
        assert result["pageCount"] == 3
        await client.close()

    @pytest.mark.asyncio
    async def test_rasterize_includes_page_and_dpi_only_when_given(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"imageBase64": "x", "contentType": "image/png", "width": 1, "height": 1, "pageCount": 1})
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            await client.pdf.rasterize(pdf_base64="JVBERi0=", format="png", page=2, dpi=300)
        _, kwargs = mock_req.call_args
        assert kwargs["json"] == {"pdfBase64": "JVBERi0=", "format": "png", "page": 2, "dpi": 300}
        await client.close()


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------

class TestAsyncClient:
    def test_async_client_initialization(self):
        client = AsyncPlatformXeClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.base_url == "https://platformxe.com"

    def test_async_services_present(self):
        client = AsyncPlatformXeClient(api_key="test")
        services = [
            "documents", "domains", "events", "exports", "identity",
            "messaging", "ocr", "pdf", "permissions", "qr",
            "storage", "templates", "threads", "usage", "webhooks", "workflows",
            "ai", "vision",
        ]
        for svc in services:
            assert hasattr(client, svc), f"Missing async service: {svc}"

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncPlatformXeClient(api_key="test") as client:
            assert client.api_key == "test"

    @pytest.mark.asyncio
    async def test_async_success_response(self):
        client = AsyncPlatformXeClient(api_key="test")
        mock_resp = _mock_response(data={"status": "ok"})
        with patch.object(client._client, "request", return_value=mock_resp):
            result = await client.get("/api/health")
        assert result == {"status": "ok"}
        await client.close()

    @pytest.mark.asyncio
    async def test_async_api_error(self):
        client = AsyncPlatformXeClient(api_key="test", fail_open=False)
        mock_resp = _mock_response(
            success=False, status_code=403,
            error={"code": "FORBIDDEN", "message": "denied"},
        )
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                await client.get("/api/v1/permissions/check")
        assert exc_info.value.code == "FORBIDDEN"
        await client.close()


# ---------------------------------------------------------------------------
# Types module
# ---------------------------------------------------------------------------

class TestTypes:
    def test_api_response_import(self):
        from platformxe import APIResponse, PaginationMeta
        resp = APIResponse(success=True, data={"id": "1"})
        assert resp.success is True
        assert resp.data == {"id": "1"}

    def test_pagination_meta(self):
        from platformxe import PaginationMeta
        meta = PaginationMeta(page=2, limit=10, total=55)
        assert meta.page == 2
        assert meta.total == 55
