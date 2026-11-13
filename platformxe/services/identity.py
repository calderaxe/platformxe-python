# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

#
# CHANGELOG:
# 2026-11-08  v1.11.0  The request bodies, DLQ query and Idempotency-Key
#   header are built by the module-level helpers below, shared with
#   AsyncIdentityService (async_services.py), so the two clients cannot
#   drift. liveness() and face_match() take optional content types for a
#   base64 image (image_content_type, selfie_content_type,
#   reference_content_type).
# 2026-11-08  v1.11.0  Fix: the idempotency key is sent as x-idempotency-key,
#   the header PlatformXe's withIdempotency reads. It was sent as
#   Idempotency-Key, which the identity routes ignore, so a retried check
#   ran (and was billed) again.
# 2026-11-13  v1.12.0  verify_business (POST /api/v1/identity/verify-business,
#   scope business:verify): a Nigerian business registration (RC / BN / IT)
#   and optional TIN; body built by verify_business_body, shared with the
#   async client.

"""Identity service — resolve, verify, lookup, KYC + DLQ."""

from __future__ import annotations
from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


# --- shared builders (sync and async) -------------------------------------

def idempotency_headers(idempotency_key: Optional[str]) -> Optional[Dict[str, str]]:
    """``x-idempotency-key``, the header the identity routes read (withIdempotency)."""
    return {"x-idempotency-key": idempotency_key} if idempotency_key else None


def dlq_list_params(
    unreplayed_only: bool = False,
    subject_id: Optional[str] = None,
    kind: Optional[str] = None,
    country_code: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if unreplayed_only:
        params["unreplayedOnly"] = "true"
    if subject_id:
        params["subjectId"] = subject_id
    if kind:
        params["kind"] = kind
    if country_code:
        params["countryCode"] = country_code
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


def verify_bvn_body(
    subject_id: str, bvn: str, first_name: str, last_name: str, date_of_birth: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "subjectId": subject_id,
        "bvn": bvn,
        "matchAgainst": {"firstName": first_name, "lastName": last_name},
    }
    if date_of_birth:
        body["matchAgainst"]["dateOfBirth"] = date_of_birth
    return body


def verify_nin_body(
    subject_id: str, nin: str, first_name: str, last_name: str, date_of_birth: str,
) -> Dict[str, Any]:
    return {
        "subjectId": subject_id,
        "nin": nin,
        "matchAgainst": {
            "firstName": first_name,
            "lastName": last_name,
            "dateOfBirth": date_of_birth,
        },
    }


def verify_account_body(
    subject_id: str,
    account_number: str,
    bank_code: str,
    first_name: str,
    last_name: str,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "subjectId": subject_id,
        "accountNumber": account_number,
        "bankCode": bank_code,
        "expectedName": {"firstName": first_name, "lastName": last_name},
    }
    if threshold is not None:
        body["threshold"] = threshold
    return body


def verify_business_body(
    subject_id: str,
    registration_type: str,
    registration_number: str,
    expected_name: str,
    tin: Optional[str] = None,
    threshold: Optional[float] = None,
    country: str = "NG",
) -> Dict[str, Any]:
    """Body for POST /api/v1/identity/verify-business (company registration check)."""
    body: Dict[str, Any] = {
        "subjectId": subject_id,
        "country": country,
        "registrationType": registration_type,
        "registrationNumber": registration_number,
        "expectedName": expected_name,
    }
    if tin is not None:
        body["tin"] = tin
    if threshold is not None:
        body["threshold"] = threshold
    return body


def _image(url: Optional[str], base64: Optional[str], content_type: Optional[str]) -> Dict[str, Any]:
    image: Dict[str, Any] = {}
    if url:
        image["url"] = url
    if base64:
        image["base64"] = base64
    if content_type:
        image["contentType"] = content_type
    return image


def liveness_body(
    subject_id: str,
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_content_type: Optional[str] = None,
) -> Dict[str, Any]:
    return {"subjectId": subject_id, "image": _image(image_url, image_base64, image_content_type)}


def face_match_body(
    subject_id: str,
    selfie_url: Optional[str] = None,
    selfie_base64: Optional[str] = None,
    reference_url: Optional[str] = None,
    reference_base64: Optional[str] = None,
    threshold: Optional[float] = None,
    reference_verification_id: Optional[str] = None,
    selfie_content_type: Optional[str] = None,
    reference_content_type: Optional[str] = None,
) -> Dict[str, Any]:
    reference: Dict[str, Any] = {}
    if reference_verification_id:
        reference["verificationId"] = reference_verification_id
    reference.update(_image(reference_url, reference_base64, reference_content_type))
    body: Dict[str, Any] = {
        "subjectId": subject_id,
        "selfie": _image(selfie_url, selfie_base64, selfie_content_type),
        "reference": reference,
    }
    if threshold is not None:
        body["threshold"] = threshold
    return body


class IdentityDlqService:
    """Identity verification dead-letter queue (Phase 6F.5b)."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client

    def list(
        self,
        unreplayed_only: bool = False,
        subject_id: Optional[str] = None,
        kind: Optional[str] = None,
        country_code: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._client.get(
            "/api/v1/identity/dlq",
            params=dlq_list_params(unreplayed_only, subject_id, kind, country_code, limit, offset),
        )

    def stats(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/identity/dlq/stats")

    def get(self, dlq_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/identity/dlq/{dlq_id}")

    def replay(self, dlq_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post(
            f"/api/v1/identity/dlq/{dlq_id}/replay",
            json={},
            headers=idempotency_headers(idempotency_key),
        )


class IdentityService:
    """Identity Resolution Service — resolve, verify, KYC, biometrics, DLQ."""

    def __init__(self, client: "PlatformXeClient"):
        self._client = client
        self.dlq = IdentityDlqService(client)

    # --- legacy resolve / verify / lookup ------------------------------

    def resolve(
        self,
        type: str,
        value: str,
        resolve_linked: bool = True,
        consent_reference: str = "",
        consent_obtained_at: str = "",
    ) -> Dict[str, Any]:
        return self._client.post("/api/v1/identity/resolve", json={
            "type": type, "value": value, "resolveLinked": resolve_linked,
            "consent": {
                "granted": True,
                "reference": consent_reference,
                "obtainedAt": consent_obtained_at,
            },
        })

    def verify(
        self,
        type: str,
        value: str,
        first_name: str,
        last_name: str,
        date_of_birth: Optional[str] = None,
        supporting_nin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/identity/verify.

        ``supporting_nin`` (1.8.0) is the holder's 11-digit NIN, sent as
        ``supporting.nin`` and accepted only for ``type="PASSPORT"`` (any
        other type is a 400). With ``date_of_birth`` (YYYY-MM-DD) PlatformXe
        runs the Nigerian passport check on its primary provider.
        """
        body: Dict[str, Any] = {
            "type": type, "value": value,
            "matchAgainst": {"firstName": first_name, "lastName": last_name},
        }
        if date_of_birth:
            body["matchAgainst"]["dateOfBirth"] = date_of_birth
        if supporting_nin is not None:
            body["supporting"] = {"nin": supporting_nin}
        return self._client.post("/api/v1/identity/verify", json=body)

    def lookup(self, type: str, value: str, purpose: str, consent_reference: str) -> Dict[str, Any]:
        """Raw registry lookup (v1.10.0). Needs the identity:lookup scope, the
        Detection Pack and its terms, and a purpose and consent reference
        (1 to 200 characters each), which PlatformXe logs; each call is
        metered. The answer never carries a photo."""
        return self._client.get(
            "/api/v1/identity/lookup",
            params={
                "type": type,
                "value": value,
                "purpose": purpose,
                "consentReference": consent_reference,
            },
        )

    # --- providers -----------------------------------------------------

    def providers(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/identity/providers")

    def providers_health(self) -> Dict[str, Any]:
        """Phase 6F.5: per-(country, provider) breaker + latency rollup."""
        return self._client.get("/api/v1/identity/providers/health")

    # --- per-kind verifications (Phase 6F) -----------------------------

    def verify_bvn(
        self,
        subject_id: str,
        bvn: str,
        first_name: str,
        last_name: str,
        date_of_birth: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post(
            "/api/v1/identity/verify-bvn",
            json=verify_bvn_body(subject_id, bvn, first_name, last_name, date_of_birth),
            headers=idempotency_headers(idempotency_key),
        )

    def verify_nin(
        self,
        subject_id: str,
        nin: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """NIN check (v1.10.0: ``date_of_birth``, YYYY-MM-DD, is required).
        ``status`` is ``verified`` only when the first name, the last name and
        the date of birth all match; the answer carries ``checks`` and
        ``reason``, and ``profile`` only when verified."""
        return self._client.post(
            "/api/v1/identity/verify-nin",
            json=verify_nin_body(subject_id, nin, first_name, last_name, date_of_birth),
            headers=idempotency_headers(idempotency_key),
        )

    def verify_account(
        self,
        subject_id: str,
        account_number: str,
        bank_code: str,
        first_name: str,
        last_name: str,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post(
            "/api/v1/identity/verify-account",
            json=verify_account_body(subject_id, account_number, bank_code, first_name, last_name, threshold),
            headers=idempotency_headers(idempotency_key),
        )

    def verify_business(
        self,
        subject_id: str,
        registration_type: str,
        registration_number: str,
        expected_name: str,
        tin: Optional[str] = None,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check a Nigerian business registration (RC, BN or IT) and optional TIN.

        Needs the ``business:verify`` scope. Returns ``status`` (verified, failed,
        provider_down), ``reason`` (name_mismatch, not_found, inactive,
        tin_mismatch or None), ``matchScore``, ``registeredName``,
        ``registrationStatus``, ``registeredAt``, ``tinStatus``, ``provider`` and
        ``verificationId``."""
        return self._client.post(
            "/api/v1/identity/verify-business",
            json=verify_business_body(
                subject_id, registration_type, registration_number, expected_name, tin, threshold,
            ),
            headers=idempotency_headers(idempotency_key),
        )

    def liveness(
        self,
        subject_id: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        image_content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Liveness check. ``image_content_type`` (v1.11.0) names a base64
        image's type: ``image/jpeg`` or ``image/png``."""
        return self._client.post(
            "/api/v1/identity/liveness",
            json=liveness_body(subject_id, image_url, image_base64, image_content_type),
            headers=idempotency_headers(idempotency_key),
        )

    def face_match(
        self,
        subject_id: str,
        selfie_url: Optional[str] = None,
        selfie_base64: Optional[str] = None,
        reference_url: Optional[str] = None,
        reference_base64: Optional[str] = None,
        threshold: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        reference_verification_id: Optional[str] = None,
        selfie_content_type: Optional[str] = None,
        reference_content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Face match. ``reference_verification_id`` (v1.10.0) compares the
        selfie with the registry photo PlatformXe kept from that verified NIN
        check for the same subject, in place of a reference image.
        ``selfie_content_type`` / ``reference_content_type`` (v1.11.0) name a
        base64 image's type (``image/jpeg`` or ``image/png``; webp is a 400)."""
        return self._client.post(
            "/api/v1/identity/face-match",
            json=face_match_body(
                subject_id, selfie_url, selfie_base64, reference_url, reference_base64,
                threshold, reference_verification_id, selfie_content_type, reference_content_type,
            ),
            headers=idempotency_headers(idempotency_key),
        )

    # --- processor (legacy) --------------------------------------------

    def get_processor(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/identity/processor")

    def update_processor(
        self,
        enabled: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/identity/processor", json=body)
