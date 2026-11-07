# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Identity service — resolve, verify, lookup, KYC + DLQ."""

from __future__ import annotations
from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


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
        return self._client.get("/api/v1/identity/dlq", params=params or None)

    def stats(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/identity/dlq/stats")

    def get(self, dlq_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/identity/dlq/{dlq_id}")

    def replay(self, dlq_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post(
            f"/api/v1/identity/dlq/{dlq_id}/replay",
            json={},
            headers=headers,
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
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "bvn": bvn,
            "matchAgainst": {"firstName": first_name, "lastName": last_name},
        }
        if date_of_birth:
            body["matchAgainst"]["dateOfBirth"] = date_of_birth
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/identity/verify-bvn", json=body, headers=headers)

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
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "nin": nin,
            "matchAgainst": {
                "firstName": first_name,
                "lastName": last_name,
                "dateOfBirth": date_of_birth,
            },
        }
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/identity/verify-nin", json=body, headers=headers)

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
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "accountNumber": account_number,
            "bankCode": bank_code,
            "expectedName": {"firstName": first_name, "lastName": last_name},
        }
        if threshold is not None:
            body["threshold"] = threshold
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post(
            "/api/v1/identity/verify-account",
            json=body,
            headers=headers,
        )

    def liveness(
        self,
        subject_id: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        image: Dict[str, Any] = {}
        if image_url:
            image["url"] = image_url
        if image_base64:
            image["base64"] = image_base64
        body = {"subjectId": subject_id, "image": image}
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/identity/liveness", json=body, headers=headers)

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
    ) -> Dict[str, Any]:
        """Face match. ``reference_verification_id`` (v1.10.0) compares the
        selfie with the registry photo PlatformXe kept from that verified NIN
        check for the same subject, in place of a reference image."""
        selfie: Dict[str, Any] = {}
        reference: Dict[str, Any] = {}
        if reference_verification_id:
            reference["verificationId"] = reference_verification_id
        if selfie_url:
            selfie["url"] = selfie_url
        if selfie_base64:
            selfie["base64"] = selfie_base64
        if reference_url:
            reference["url"] = reference_url
        if reference_base64:
            reference["base64"] = reference_base64
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "selfie": selfie,
            "reference": reference,
        }
        if threshold is not None:
            body["threshold"] = threshold
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.post("/api/v1/identity/face-match", json=body, headers=headers)

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
