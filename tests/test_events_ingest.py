# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  Initial (1.13.0, pending): events.ingest sends entityData, the
#   field POST /api/v1/events reads (it sent payload, which the route drops);
#   payload is a deprecated alias, sent as entityData only when entity_data is
#   absent; sync and async send the same request.
# 2026-11-20  Review round 1 (N3): the deprecation warning names the caller's
#   line, through ingest and when build_ingest_body is called directly.
# 2026-11-22  (1.14.1, pending)  entity_data, the custom-parameters object: an
#   empty dict is sent as {}, None is omitted (sync and async).

"""client.events.ingest against POST /api/v1/events."""

import asyncio
import json
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient
from platformxe.services.events import build_ingest_body


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = {"success": True, "data": data}
    resp.text = json.dumps({"success": True, "data": data})
    resp.reason_phrase = "OK"
    return resp


_ANSWER = {
    "eventType": "BOOKING_CONFIRMED",
    "entityType": "BOOKING",
    "entityId": "bk_1",
    "sourceApp": "lettings",
    "triggersEvaluated": 1,
    "triggersMatched": 1,
    "triggersExecuted": 1,
    "results": [{"triggerId": "trg_1", "triggerName": "T", "matched": True, "executed": True}],
}


def test_ingest_sends_entity_data_and_the_optional_fields():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_ANSWER)) as req:
        result = client.events.ingest(
            "BOOKING_CONFIRMED", "BOOKING", "bk_1",
            entity_data={"guestName": "Ade"}, source_app="lettings", metadata={"trace": "t1"},
        )
    args, kwargs = req.call_args
    assert args == ("POST", "/api/v1/events")
    assert kwargs["json"] == {
        "eventType": "BOOKING_CONFIRMED",
        "entityType": "BOOKING",
        "entityId": "bk_1",
        "entityData": {"guestName": "Ade"},
        "sourceApp": "lettings",
        "metadata": {"trace": "t1"},
    }
    assert result["triggersExecuted"] == 1
    client.close()


def test_ingest_sends_only_the_event_type_when_nothing_else_is_given():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_ANSWER)) as req:
        client.events.ingest("BOOKING_CONFIRMED")
    assert req.call_args.kwargs["json"] == {"eventType": "BOOKING_CONFIRMED"}
    client.close()


def test_a_positional_payload_is_sent_as_entity_data_with_a_warning():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_ANSWER)) as req:
        with pytest.warns(DeprecationWarning, match="entity_data"):
            client.events.ingest("BOOKING_CONFIRMED", "BOOKING", "bk_1", {"guestName": "Ade"})
    body = req.call_args.kwargs["json"]
    assert body["entityData"] == {"guestName": "Ade"}
    assert "payload" not in body
    client.close()


def test_the_warning_names_the_callers_line():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_ANSWER)):
        with pytest.warns(DeprecationWarning) as through_ingest:
            client.events.ingest("BOOKING_CONFIRMED", payload={"a": 1})
    client.close()
    with pytest.warns(DeprecationWarning) as direct:
        build_ingest_body("BOOKING_CONFIRMED", payload={"a": 1})
    assert through_ingest[0].filename == __file__
    assert direct[0].filename == __file__


def test_entity_data_wins_over_payload():
    with pytest.warns(DeprecationWarning):
        body = build_ingest_body("BOOKING_CONFIRMED", payload={"old": 1}, entity_data={"new": 2})
    assert body == {"eventType": "BOOKING_CONFIRMED", "entityData": {"new": 2}}


def test_no_warning_without_payload():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert build_ingest_body("BOOKING_CONFIRMED", entity_data={}) == {
            "eventType": "BOOKING_CONFIRMED",
            "entityData": {},
        }


def test_async_ingest_sends_the_same_request():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")
        mock_req = AsyncMock(return_value=_ok(_ANSWER))
        with patch.object(client._client, "request", mock_req):
            await client.events.ingest("BOOKING_CONFIRMED", entity_id="bk_1", entity_data={"a": 1})
            with pytest.warns(DeprecationWarning):
                await client.events.ingest("BOOKING_CONFIRMED", None, None, {"b": 2})
        await client.close()
        return mock_req.call_args_list

    first, legacy = asyncio.run(run())
    assert first.args == ("POST", "/api/v1/events")
    assert first.kwargs["json"] == {"eventType": "BOOKING_CONFIRMED", "entityId": "bk_1", "entityData": {"a": 1}}
    assert legacy.kwargs["json"] == {"eventType": "BOOKING_CONFIRMED", "entityData": {"b": 2}}


def test_ingest_entity_data_empty_dict_is_sent_and_none_is_omitted():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(_ANSWER)) as req:
        client.events.ingest("PAYMENT_RECEIVED", entity_data={})
        client.events.ingest("PAYMENT_RECEIVED", entity_data=None)
    first, second = (c.kwargs["json"] for c in req.call_args_list)
    assert first == {"eventType": "PAYMENT_RECEIVED", "entityData": {}}
    assert second == {"eventType": "PAYMENT_RECEIVED"}
    client.close()


def test_async_ingest_entity_data_empty_dict_is_sent_and_none_is_omitted():
    async def run():
        client = AsyncPlatformXeClient(api_key="test")
        with patch.object(client._client, "request", new=AsyncMock(return_value=_ok(_ANSWER))) as req:
            await client.events.ingest("PAYMENT_RECEIVED", entity_data={})
            await client.events.ingest("PAYMENT_RECEIVED")
        await client.close()
        return [c.kwargs["json"] for c in req.call_args_list]

    first, second = asyncio.run(run())
    assert first == {"eventType": "PAYMENT_RECEIVED", "entityData": {}}
    assert second == {"eventType": "PAYMENT_RECEIVED"}
