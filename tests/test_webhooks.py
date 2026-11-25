# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-20  (pending release) Created (webhooks v2, NO-DRIFT train). Pins the
#   method, path, query, headers and body of every client.webhooks call, sync
#   and async: create with engine_version / recipient_ref, list with the
#   recipient_ref filter, dispatch with the x-idempotency-key header,
#   deliveries and redeliver, plus the unchanged CRUD / rotate / test paths.
#   Secrets in the fixtures are obvious placeholders.
# 2026-10-20  (pending release) Review fix wave 2: limit / page of 0 are not
#   sent (the server default, as the Go SDK); a None data is sent as {}.
# =============================================================================

"""Contract tests for the webhooks service (v1 + v2 recipient endpoints)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from platformxe import AsyncPlatformXeClient, PlatformXeClient


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = {"content-type": "application/json"}
    body = {"success": True, "data": data}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def _call(method, *args, **kwargs):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"ok": True})) as mock_req:
        result = getattr(client.webhooks, method)(*args, **kwargs)
    client.close()
    return mock_req.call_args, result


class TestWebhooksService:
    def test_create_v1_body_is_unchanged(self):
        (args, kwargs), _ = _call("create", "Orders", "https://example.com/hook", ["custom.x"])
        assert args == ("POST", "/api/v1/webhooks")
        assert kwargs["json"] == {"name": "Orders", "url": "https://example.com/hook", "events": ["custom.x"]}

    def test_create_v2_recipient_endpoint(self):
        (args, kwargs), _ = _call(
            "create", "Host hook", "https://example.com/hook", ["custom.x"],
            engine_version=2, recipient_ref="host:1",
        )
        assert args == ("POST", "/api/v1/webhooks")
        assert kwargs["json"] == {
            "name": "Host hook", "url": "https://example.com/hook", "events": ["custom.x"],
            "engineVersion": 2, "recipientRef": "host:1",
        }

    def test_list_filters_by_recipient(self):
        (args, kwargs), _ = _call("list", recipient_ref="host:1", limit=50, page=2)
        assert args == ("GET", "/api/v1/webhooks")
        assert kwargs["params"] == {"recipientRef": "host:1", "limit": "50", "page": "2"}

    def test_list_without_filters_sends_no_query(self):
        (_, kwargs), _ = _call("list")
        assert kwargs["params"] is None

    def test_list_zero_limit_and_page_use_the_server_default(self):
        (_, kwargs), _ = _call("list", limit=0, page=0)
        assert kwargs["params"] is None
        (_, kwargs), _ = _call("list", recipient_ref="host:1", limit=0, page=2)
        assert kwargs["params"] == {"recipientRef": "host:1", "page": "2"}
        (_, kwargs), _ = _call("deliveries", "wh_1", limit=-1, page=0)
        assert kwargs["params"] is None

    def test_get_update_delete_paths(self):
        (args, _), _ = _call("get", "wh_1")
        assert args == ("GET", "/api/v1/webhooks/wh_1")
        (args, kwargs), _ = _call("update", "wh_1", status="PAUSED")
        assert args == ("PATCH", "/api/v1/webhooks/wh_1")
        assert kwargs["json"] == {"status": "PAUSED"}
        (args, _), _ = _call("delete", "wh_1")
        assert args == ("DELETE", "/api/v1/webhooks/wh_1")

    def test_rotate_and_test_paths(self):
        (args, _), _ = _call("rotate_secret", "wh_1")
        assert args == ("POST", "/api/v1/webhooks/wh_1/rotate")
        (args, _), _ = _call("test", "wh_1")
        assert args == ("POST", "/api/v1/webhooks/wh_1/test")

    def test_dispatch_sends_body_and_idempotency_header(self):
        (args, kwargs), _ = _call(
            "dispatch", "host:1", "custom.booking.created", "evt_1", {"bookingId": "b1"},
            idempotency_key="idem-1",
        )
        assert args == ("POST", "/api/v1/webhooks/dispatch")
        assert kwargs["json"] == {
            "recipientRef": "host:1", "eventType": "custom.booking.created",
            "eventId": "evt_1", "data": {"bookingId": "b1"},
        }
        assert kwargs["headers"] == {"x-idempotency-key": "idem-1"}

    def test_dispatch_without_key_sends_no_idempotency_header(self):
        (_, kwargs), _ = _call("dispatch", "host:1", "custom.x", "evt_1", {})
        assert "x-idempotency-key" not in (kwargs.get("headers") or {})

    def test_dispatch_sends_none_data_as_an_empty_object(self):
        (_, kwargs), _ = _call("dispatch", "host:1", "booking.created", "evt_1", None)
        assert kwargs["json"]["data"] == {}

    def test_deliveries_path_and_paging(self):
        (args, kwargs), _ = _call("deliveries", "wh_1", limit=10, page=3)
        assert args == ("GET", "/api/v1/webhooks/wh_1/deliveries")
        assert kwargs["params"] == {"limit": "10", "page": "3"}

    def test_redeliver_path(self):
        (args, _), _ = _call("redeliver", "dlv_9")
        assert args == ("POST", "/api/v1/webhooks/deliveries/dlv_9/redeliver")


class TestAsyncWebhooksService:
    def test_async_calls_send_the_same_requests(self):
        async def run():
            client = AsyncPlatformXeClient(api_key="test")
            mock_req = AsyncMock(return_value=_ok({"ok": True}))
            with patch.object(client._client, "request", mock_req):
                await client.webhooks.create(
                    "Host hook", "https://example.com/hook", ["custom.x"],
                    engine_version=2, recipient_ref="host:1",
                )
                create_call = mock_req.call_args
                await client.webhooks.dispatch("host:1", "custom.x", "evt_1", {}, idempotency_key="idem-1")
                dispatch_call = mock_req.call_args
                await client.webhooks.deliveries("wh_1", limit=5)
                deliveries_call = mock_req.call_args
                await client.webhooks.redeliver("dlv_9")
                redeliver_call = mock_req.call_args
                await client.webhooks.list(recipient_ref="host:1")
                list_call = mock_req.call_args
            await client.close()
            return create_call, dispatch_call, deliveries_call, redeliver_call, list_call

        create_call, dispatch_call, deliveries_call, redeliver_call, list_call = asyncio.run(run())
        assert create_call.args == ("POST", "/api/v1/webhooks")
        assert create_call.kwargs["json"]["recipientRef"] == "host:1"
        assert create_call.kwargs["json"]["engineVersion"] == 2
        assert dispatch_call.args == ("POST", "/api/v1/webhooks/dispatch")
        assert dispatch_call.kwargs["headers"] == {"x-idempotency-key": "idem-1"}
        assert deliveries_call.args == ("GET", "/api/v1/webhooks/wh_1/deliveries")
        assert deliveries_call.kwargs["params"] == {"limit": "5"}
        assert redeliver_call.args == ("POST", "/api/v1/webhooks/deliveries/dlv_9/redeliver")
        assert list_call.kwargs["params"] == {"recipientRef": "host:1"}
