# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-07  Initial: fraud.activate posts to /api/v1/fraud/activate.

"""fraud.activate — turn the Detection Pack on for the key's own organisation."""

import json
from unittest.mock import MagicMock, patch

import httpx

from platformxe import PlatformXeClient


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


ACTIVATION = {
    "detectionPackEnabled": True,
    "detectionPackEnabledAt": "2026-11-07T10:00:00.000Z",
    "alreadyActive": False,
    "billing": "FIRST_PARTY_METERED",
    "invoiceId": None,
    "firstParty": True,
}


def test_activate_posts_to_the_route():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(ACTIVATION)) as req:
        result = client.fraud.activate()
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/api/v1/fraud/activate")
    assert result["billing"] == "FIRST_PARTY_METERED"
    client.close()


def test_activate_passes_an_idempotency_key():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok(ACTIVATION)) as req:
        client.fraud.activate(idempotency_key="errandone-activate-1")
    assert req.call_args.kwargs["headers"]["x-idempotency-key"] == "errandone-activate-1"
    client.close()
