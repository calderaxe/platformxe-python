# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  Created (calderasuite/caldera-xadmin#29). Contract tests
#   for client.knowledge (upsert_document / delete_document / list_documents /
#   search) and tool calling on client.ai.complete, sync and async, against
#   the shared tests/fixtures/ai_vision.json (identical copy in
#   packages/sdk-go/testdata/). Each test pins method, path, query and the
#   exact camelCase body, and the passthrough of the fixture response.
# =============================================================================

"""Contract tests for the knowledge service and tool calling."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeAPIError, PlatformXeClient

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "ai_vision.json").read_text(encoding="utf-8"))


def _response(status_code, body, headers=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = {"content-type": "application/json", **(headers or {})}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK" if resp.is_success else "Error"
    return resp


def _ok(data):
    return _response(200, {"success": True, "data": data})


def _upsert(client_knowledge, req):
    return client_knowledge.upsert_document(
        feature_key=req["featureKey"],
        collection=req["collection"],
        source_ref=req["sourceRef"],
        title=req["title"],
        text=req["text"],
        url=req["url"],
        acl=req["acl"],
    )


class TestKnowledgeService:
    def test_namespace_present(self):
        client = PlatformXeClient(api_key="test")
        for method in ["upsert_document", "delete_document", "list_documents", "search"]:
            assert callable(getattr(client.knowledge, method, None)), f"Missing knowledge.{method}"
        client.close()

    def test_upsert_sends_the_fixture_request(self):
        req = FIXTURES["knowledgeUpsertRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeUpsertResult"])) as mock_req:
            result = _upsert(client.knowledge, req)
        args, kwargs = mock_req.call_args
        assert args == ("PUT", "/api/v1/ai/knowledge/documents")
        assert kwargs["json"] == req
        assert result == FIXTURES["knowledgeUpsertResult"]
        client.close()

    def test_upsert_omits_url_and_acl_when_not_given(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeUpsertResult"])) as mock_req:
            client.knowledge.upsert_document(
                feature_key="ai-canvas", collection="hr", source_ref="a", title="A", text="body",
            )
        body = mock_req.call_args[1]["json"]
        assert "url" not in body and "acl" not in body
        client.close()

    def test_delete_sends_the_document_ref_as_query(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeDeleteResult"])) as mock_req:
            result = client.knowledge.delete_document("hr-policies", "policy/annual-leave")
        args, kwargs = mock_req.call_args
        assert args == ("DELETE", "/api/v1/ai/knowledge/documents")
        assert kwargs["params"] == {"collection": "hr-policies", "sourceRef": "policy/annual-leave"}
        assert result == FIXTURES["knowledgeDeleteResult"]
        client.close()

    def test_list_sends_collection_cursor_and_limit(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeDocumentList"])) as mock_req:
            result = client.knowledge.list_documents("hr-policies", cursor="abc", limit=50)
        args, kwargs = mock_req.call_args
        assert args == ("GET", "/api/v1/ai/knowledge/documents")
        assert kwargs["params"] == {"collection": "hr-policies", "cursor": "abc", "limit": "50"}
        assert result == FIXTURES["knowledgeDocumentList"]

        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeDocumentList"])) as mock_req:
            client.knowledge.list_documents("hr-policies")
        assert mock_req.call_args[1]["params"] == {"collection": "hr-policies"}
        client.close()

    def test_search_sends_the_fixture_request(self):
        req = FIXTURES["knowledgeSearchRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeSearchResult"])) as mock_req:
            result = client.knowledge.search(
                feature_key=req["featureKey"], collections=req["collections"], query=req["query"],
                acl_tags=req["aclTags"], k=req["k"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/knowledge/search")
        assert kwargs["json"] == req
        assert result == FIXTURES["knowledgeSearchResult"]
        client.close()

    def test_search_omits_k_when_not_given(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeSearchResult"])) as mock_req:
            client.knowledge.search(feature_key="ai-canvas", collections=["hr"], query="leave", acl_tags=[])
        body = mock_req.call_args[1]["json"]
        assert "k" not in body
        assert body["aclTags"] == []
        client.close()

    @pytest.mark.parametrize("status,code", [
        (403, "AI_PROFILE_NOT_FOUND"),
        (403, "AI_POLICY_DENIED"),
        (400, "BAD_REQUEST"),
    ])
    def test_search_errors_surface(self, status, code):
        client = PlatformXeClient(api_key="test", fail_open=False)
        resp = _response(status, {"success": False, "error": {"code": code, "message": "refused"}})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(PlatformXeAPIError) as exc_info:
                client.knowledge.search(feature_key="ai-canvas", collections=["hr"], query="q", acl_tags=[])
        assert exc_info.value.code == code
        assert exc_info.value.status_code == status
        client.close()


class TestToolCalling:
    def test_complete_with_tools_sends_the_fixture_request(self):
        req = FIXTURES["completeWithToolsRequest"]
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeWithToolsResult"])) as mock_req:
            result = client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
                tools=req["tools"], tool_choice=req["toolChoice"],
            )
        args, kwargs = mock_req.call_args
        assert args == ("POST", "/api/v1/ai/complete")
        assert kwargs["json"] == req
        assert result["toolCalls"][0]["name"] == "hr.leave_balance"
        assert result["finishReason"] == "tool_calls"
        client.close()

    def test_complete_without_tools_sends_no_tool_fields(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeResult"])) as mock_req:
            client.ai.complete(feature_key="ai-canvas", provider="gemini", messages=[{"role": "user", "content": "hi"}])
        body = mock_req.call_args[1]["json"]
        assert "tools" not in body and "toolChoice" not in body
        client.close()

    def test_forced_tool_choice_is_sent_as_object(self):
        client = PlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeWithToolsResult"])) as mock_req:
            client.ai.complete(
                feature_key="ai-canvas", provider="gemini", messages=[{"role": "user", "content": "hi"}],
                tools=[{"name": "a.b"}], tool_choice={"name": "a.b"},
            )
        assert mock_req.call_args[1]["json"]["toolChoice"] == {"name": "a.b"}
        client.close()


class TestAsyncKnowledgeAndTools:
    @pytest.mark.asyncio
    async def test_async_knowledge_methods_send_the_same_requests(self):
        client = AsyncPlatformXeClient(api_key="test")
        req = FIXTURES["knowledgeUpsertRequest"]
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeUpsertResult"])) as mock_req:
            await _upsert(client.knowledge, req)
        assert mock_req.call_args[0] == ("PUT", "/api/v1/ai/knowledge/documents")
        assert mock_req.call_args[1]["json"] == req

        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeDeleteResult"])) as mock_req:
            await client.knowledge.delete_document("hr-policies", "policy/annual-leave")
        assert mock_req.call_args[0] == ("DELETE", "/api/v1/ai/knowledge/documents")
        assert mock_req.call_args[1]["params"] == {"collection": "hr-policies", "sourceRef": "policy/annual-leave"}

        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeDocumentList"])) as mock_req:
            await client.knowledge.list_documents("hr-policies", limit=10)
        assert mock_req.call_args[0] == ("GET", "/api/v1/ai/knowledge/documents")
        assert mock_req.call_args[1]["params"] == {"collection": "hr-policies", "limit": "10"}

        search = FIXTURES["knowledgeSearchRequest"]
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["knowledgeSearchResult"])) as mock_req:
            result = await client.knowledge.search(
                feature_key=search["featureKey"], collections=search["collections"], query=search["query"],
                acl_tags=search["aclTags"], k=search["k"],
            )
        assert mock_req.call_args[0] == ("POST", "/api/v1/ai/knowledge/search")
        assert mock_req.call_args[1]["json"] == search
        assert result == FIXTURES["knowledgeSearchResult"]
        await client.close()

    @pytest.mark.asyncio
    async def test_async_complete_with_tools(self):
        req = FIXTURES["completeWithToolsRequest"]
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", return_value=_ok(FIXTURES["completeWithToolsResult"])) as mock_req:
            await client.ai.complete(
                feature_key=req["featureKey"], provider=req["provider"], messages=req["messages"],
                tools=req["tools"], tool_choice=req["toolChoice"],
            )
        assert mock_req.call_args[1]["json"] == req
        await client.close()
