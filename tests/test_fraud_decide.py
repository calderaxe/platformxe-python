# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-21  Initial (spec 03 PM-1): decide / shadow_decide send the body the
#   route reads (nested subject and resource); 400 CARD_NUMBER_REFUSED raises
#   PlatformXeAPIError carrying the code.

"""fraud.decide / fraud.shadow_decide: the body, and the card-number refusal."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import PlatformXeClient
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


VERDICT = {"decisionId": "dec_1", "verdict": "allow", "score": 0, "reasons": []}


@pytest.mark.parametrize(
    "method,path",
    [("decide", "/api/v1/fraud/decide"), ("shadow_decide", "/api/v1/fraud/shadow-decide")],
)
def test_sends_the_nested_body_the_route_reads(method, path):
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_resp(200, {"success": True, "data": VERDICT})) as req:
        getattr(client.fraud, method)(
            "user_123", "user", "withdraw", "transaction", resource_id="txn_1", context={"amount": {"value": 5, "currency": "NGN"}}
        )
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1] == path
    assert kwargs["json"] == {
        "subject": {"id": "user_123", "kind": "user"},
        "action": "withdraw",
        "resource": {"kind": "transaction", "id": "txn_1"},
        "context": {"amount": {"value": 5, "currency": "NGN"}},
    }


def test_optional_parts_are_left_out():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_resp(200, {"success": True, "data": VERDICT})) as req:
        client.fraud.decide("u1", "user", "login", "session")
    assert req.call_args[1]["json"] == {"subject": {"id": "u1", "kind": "user"}, "action": "login", "resource": {"kind": "session"}}


@pytest.mark.parametrize("method", ["decide", "shadow_decide"])
def test_card_number_refused_carries_the_code(method):
    client = PlatformXeClient(api_key="test")
    body = {
        "success": False,
        "error": {
            "code": "CARD_NUMBER_REFUSED",
            "message": "A value at resource.attributes.pan looks like a card number or card field. Send a token, never card data.",
        },
    }
    with patch.object(client._client, "request", return_value=_resp(400, body)) as req:
        with pytest.raises(PlatformXeAPIError) as info:
            getattr(client.fraud, method)("u1", "user", "transfer", "transaction")
    assert info.value.code == "CARD_NUMBER_REFUSED"
    assert info.value.status_code == 400
    assert req.call_count == 1
