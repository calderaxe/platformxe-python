# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-19  Initial (1.13.0): event log, subscriptions and replay send what
#   the routes read (replay fromTimestamp / toTimestamp / eventTypes; log
#   eventTypes / from / to; create name), sync and async; a restricted entry
#   is 400 RESTRICTED_EVENT_TYPE.

"""client.events: event log, subscriptions and replay against the routes."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient
from platformxe.exceptions import PlatformXeAPIError


def _resp(status, body):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def _ok(data):
    return _resp(200, {"success": True, "data": data})


def test_replay_sends_from_timestamp_and_to_timestamp():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"replayed": 3})) as req:
        result = client.events.replay("esub_1", "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z")
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/event-subscriptions/esub_1/replay")
    assert kwargs["json"] == {"fromTimestamp": "2026-11-01T00:00:00Z", "toTimestamp": "2026-11-02T00:00:00Z"}
    assert result["replayed"] == 3
    client.close()


def test_replay_takes_event_types_and_an_open_window():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"replayed": 0})) as req:
        client.events.replay("esub_1", "2026-11-01T00:00:00Z", event_types=["messaging.email.sent"])
    assert req.call_args.kwargs["json"] == {
        "fromTimestamp": "2026-11-01T00:00:00Z",
        "eventTypes": ["messaging.email.sent"],
    }
    client.close()


def test_log_sends_event_types_from_and_to():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"items": [], "total": 0})) as req:
        client.events.log("A_SENT", page=2, limit=10, event_types=["B_SENT"], from_="2026-11-01T00:00:00Z")
    args, kwargs = req.call_args
    assert args == ("GET", "/api/v1/event-log")
    assert kwargs["params"] == {"eventTypes": "A_SENT,B_SENT", "from": "2026-11-01T00:00:00Z", "page": "2", "limit": "10"}
    client.close()


def test_create_sends_the_name_and_no_secret():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"subscription": {}, "secret": "s"})) as req:
        client.events.create_subscription(["A"], "https://example.com/hook", "ignored", name="Bookings")
    assert req.call_args.args == ("POST", "/api/v1/event-subscriptions")
    assert req.call_args.kwargs["json"] == {"eventTypes": ["A"], "webhookUrl": "https://example.com/hook", "name": "Bookings"}
    client.close()


def test_a_restricted_event_type_raises_400_restricted_event_type():
    client = PlatformXeClient(api_key="test")
    refusal = _resp(400, {"success": False, "error": {
        "code": "RESTRICTED_EVENT_TYPE", "message": "eventTypes names a restricted event type: FRAUD_*"}})
    with patch.object(client._client, "request", return_value=refusal) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.events.update_subscription("esub_1", eventTypes=["FRAUD_*"])
    assert exc.value.code == "RESTRICTED_EVENT_TYPE"
    assert exc.value.status_code == 400
    assert req.call_args.args == ("PATCH", "/api/v1/event-subscriptions/esub_1")
    client.close()


def test_subscription_ids_are_url_quoted():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({})) as req:
        client.events.get_subscription("a/b")
        client.events.delete_subscription("a/b")
    assert [c.args for c in req.call_args_list] == [
        ("GET", "/api/v1/event-subscriptions/a%2Fb"),
        ("DELETE", "/api/v1/event-subscriptions/a%2Fb"),
    ]
    client.close()


def test_async_events_send_the_same_requests():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")
        mock_req = AsyncMock(return_value=_ok({"replayed": 1}))
        with patch.object(client._client, "request", mock_req):
            await client.events.replay("esub_1", "2026-11-01T00:00:00Z", event_types=["A"])
            await client.events.log(event_types=["A", "B"], to="2026-11-02T00:00:00Z")
            await client.events.create_subscription(["A"], "https://example.com/hook", name="Bookings")
            await client.events.update_subscription("esub_1", status="ACTIVE")
        await client.close()
        return mock_req.call_args_list

    replay, log, create, update = asyncio.run(run())
    assert replay.args == ("POST", "/api/v1/event-subscriptions/esub_1/replay")
    assert replay.kwargs["json"] == {"fromTimestamp": "2026-11-01T00:00:00Z", "eventTypes": ["A"]}
    assert log.kwargs["params"] == {"eventTypes": "A,B", "to": "2026-11-02T00:00:00Z"}
    assert create.kwargs["json"]["name"] == "Bookings"
    assert "secret" not in create.kwargs["json"]
    assert update.args == ("PATCH", "/api/v1/event-subscriptions/esub_1")
