# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.13.0, pending)  Created (re-review R4, N-R1): fill_path, the
#   one path filler, and every helper that now calls it (subscription_path,
#   rule_path, webhook_path, redeliver_path; the workflow and custom-event
#   routes call it directly).
# =============================================================================

"""Contract tests for platformxe.services.paths.fill_path and its callers."""

from unittest.mock import patch

import pytest

from platformxe import PlatformXeClient
from platformxe.services.events import EVENT_SUBSCRIPTION_BY_ID_PATH, subscription_path
from platformxe.services.fraud import FRAUD_RULE_BY_ID_PATH, rule_path
from platformxe.services.paths import fill_path
from platformxe.services.webhooks import WEBHOOK_BY_ID_PATH, redeliver_path, webhook_path

from tests.test_workflows import _ok


def test_fill_path_quotes_every_reserved_character():
    assert fill_path("/a/{id}", id="x/y?z#w %") == "/a/x%2Fy%3Fz%23w%20%25"
    assert fill_path("/g/{id}/m/{orgId}", id="g 1", orgId="o/2") == "/g/g%201/m/o%2F2"
    assert fill_path("/a/{id}", id="trg_abc123") == "/a/trg_abc123"


@pytest.mark.parametrize("bad", ["", ".", ".."])
def test_fill_path_refuses_an_empty_or_dot_segment_id(bad):
    with pytest.raises(ValueError):
        fill_path("/a/{id}", id=bad)


def test_fill_path_refuses_a_non_string_id():
    with pytest.raises(ValueError):
        fill_path("/a/{id}", id=None)  # type: ignore[arg-type]


def test_fill_path_names_the_placeholder_in_the_error():
    with pytest.raises(ValueError, match="orgId is required"):
        fill_path("/g/{id}/m/{orgId}", id="g", orgId="")


def test_every_helper_fills_through_fill_path():
    assert subscription_path(EVENT_SUBSCRIPTION_BY_ID_PATH, "s/1") == "/api/v1/event-subscriptions/s%2F1"
    assert rule_path(FRAUD_RULE_BY_ID_PATH, "r?1") == "/api/v1/fraud/rules/r%3F1"
    # webhook_path and redeliver_path did not quote before 1.13.0.
    assert webhook_path(WEBHOOK_BY_ID_PATH, "w/1") == "/api/v1/webhooks/w%2F1"
    assert redeliver_path("d/1") == "/api/v1/webhooks/deliveries/d%2F1/redeliver"
    for helper in (
        lambda: subscription_path(EVENT_SUBSCRIPTION_BY_ID_PATH, ""),
        lambda: rule_path(FRAUD_RULE_BY_ID_PATH, ".."),
        lambda: webhook_path(WEBHOOK_BY_ID_PATH, ""),
        lambda: redeliver_path("."),
    ):
        with pytest.raises(ValueError):
            helper()


def test_custom_event_routes_quote_and_refuse_before_any_request():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({})) as req:
        client.events.custom.get("reg/1")
        assert req.call_args[0] == ("GET", "/api/v1/events/custom/reg%2F1")
        calls = req.call_count
        with pytest.raises(ValueError):
            client.events.custom.get("")
        assert req.call_count == calls
    client.close()
