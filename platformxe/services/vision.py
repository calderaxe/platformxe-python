# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-10-08  v1.7.0  Created (caldera-platformxe#22, NO-DRIFT for the vision
#   route). VisionService.analyze_room for POST /api/v1/vision/analyze-room —
#   scope vision:analyze, 2,000 requests/hr/key. The body mirrors
#   AnalyzeRoomRequest in @caldera/platformxe-types 3.5.0 (src/vision.ts).
#   ``idempotency_key`` is sent as the ``x-idempotency-key`` header:
#   PlatformXe replays the stored answer for 24 h, except a degraded
#   ``aiStatus: "FALLBACK"`` answer (marked ``X-Idempotency-Cache: skip``,
#   never stored), so a retry under the same key after a FALLBACK reaches
#   the provider again. The builders are module-level so AsyncVisionService
#   sends identical requests.
# 2026-10-09  (pending release) Final review: analyze_room waits up to 35 s
#   (the route runs up to 30 s) and is not retried without an idempotency
#   key — a retry is a second billed analysis (analyze_room_call_options).
# =============================================================================

"""Vision service — property-photo room category + alt text."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


def build_analyze_room_body(
    room_categories: List[str],
    want_alt_text: bool,
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None,
    locale: Optional[str] = None,
    feature_key: Optional[str] = None,
) -> Dict[str, Any]:
    """AnalyzeRoomRequest: {roomCategories, wantAltText, imageUrl? | imageBase64?,
    locale?, featureKey?}. Exactly one of image_url / image_base64 — the
    server answers 400 BAD_REQUEST otherwise."""
    body: Dict[str, Any] = {
        "roomCategories": room_categories,
        "wantAltText": want_alt_text,
    }
    if image_url is not None:
        body["imageUrl"] = image_url
    if image_base64 is not None:
        body["imageBase64"] = image_base64
    if locale is not None:
        body["locale"] = locale
    if feature_key is not None:
        body["featureKey"] = feature_key
    return body


def analyze_room_call_options(idempotency_key: Optional[str]) -> Dict[str, Any]:
    """Per-call options for POST /vision/analyze-room: the route runs up to
    30 s (the client default is 10 s); without an idempotency key a retry is
    a second billed analysis, so it is not retried."""
    return {"timeout": 35.0} if idempotency_key else {"timeout": 35.0, "retries": 0}


def idempotency_headers(idempotency_key: Optional[str]) -> Optional[Dict[str, str]]:
    """``x-idempotency-key`` when a key is given, else no extra headers."""
    return {"x-idempotency-key": idempotency_key} if idempotency_key else None


class VisionService:
    """Image analysis (scope ``vision:analyze``)."""

    def __init__(self, client: PlatformXeClient):
        self._client = client

    def analyze_room(
        self,
        room_categories: List[str],
        want_alt_text: bool,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        locale: Optional[str] = None,
        feature_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a property photo into one of ``room_categories`` and
        (when ``want_alt_text``) write alt text.

        ``image_url`` must be public https; ``image_base64`` is at most
        8 MiB decoded. ``feature_key`` defaults server-side to "room-vision".
        A provider timeout is not an error: it returns 200 with
        ``aiStatus == "FALLBACK"``. Returns AnalyzeRoomResult
        ``{roomCategory, roomConfidence, altText, detectedFeatures,
        modelVersion, cached, aiStatus?, provider?, metrics?}``.
        """
        return self._client.post(
            "/api/v1/vision/analyze-room",
            json=build_analyze_room_body(
                room_categories, want_alt_text, image_url, image_base64, locale, feature_key,
            ),
            headers=idempotency_headers(idempotency_key),
            **analyze_room_call_options(idempotency_key),
        )
