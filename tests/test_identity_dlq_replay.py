# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-18  Initial (1.12.0): identity.dlq.replay raises 409
#   REPLAY_IN_PROGRESS and the 500 a replay that did not complete answers,
#   once each (the client never re-sends an API error); identity.lookup
#   returns the answer as the API sends it (outcome, raw.provider).

"""identity.dlq.replay errors and the lookup answer."""

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


@pytest.mark.parametrize(
    "status,code",
    [(409, "REPLAY_IN_PROGRESS"), (500, "INTERNAL_ERROR"), (503, "SERVICE_UNAVAILABLE")],
)
def test_replay_errors_raise_once(status, code):
    client = PlatformXeClient(api_key="test")
    refusal = _resp(status, {"success": False, "error": {"code": code, "message": "x"}})
    with patch.object(client._client, "request", return_value=refusal) as req:
        with pytest.raises(PlatformXeAPIError) as exc:
            client.identity.dlq.replay("idlq_1", idempotency_key="r1")
    assert exc.value.code == code
    assert exc.value.status_code == status
    assert req.call_count == 1
    client.close()


def test_lookup_returns_the_public_answer():
    client = PlatformXeClient(api_key="test")
    answer = {
        "found": False, "notFound": True, "notFoundBy": "prembly",
        "outcome": "not_found", "profile": None, "raw": {"provider": "prembly"},
    }
    with patch.object(client._client, "request", return_value=_resp(200, {"success": True, "data": answer})) as req:
        result = client.identity.lookup("NIN", "12345678901", "kyc", "consent_1")
    assert req.call_args.args == ("GET", "/api/v1/identity/lookup")
    assert result["outcome"] == "not_found"
    assert result["raw"] == {"provider": "prembly"}
    client.close()
