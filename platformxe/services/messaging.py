# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Messaging service — email, SMS, WhatsApp."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class MessagingService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    def send_email(self, to: Union[str, List[str]], subject: str, html: str, reply_to: Optional[str] = None, attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        }
        if reply_to:
            body["replyTo"] = reply_to
        if attachments:
            body["attachments"] = attachments
        return self._client.post("/api/v1/messaging/email/send", json=body)

    def send_sms(self, to: str, message: str, region_code: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"to": to, "message": message}
        if region_code:
            body["regionCode"] = region_code
        return self._client.post("/api/v1/messaging/sms", json=body)

    def send_whatsapp(
        self,
        to: str,
        message: Optional[str] = None,
        template_name: Optional[str] = None,
        template_params: Optional[Dict[str, str]] = None,
        template_language: Optional[str] = None,
        caller_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a WhatsApp send.

        PlatformXe defaults to click-to-chat mode: when no Meta credentials are
        configured server-side, the response carries `clickToChatUrl` +
        `deepLink` instead of a `messageId`. The calling app is expected to
        surface those URLs to the operator (e.g. as an "Open WhatsApp" button)
        — the operator's own WhatsApp Desktop / mobile app handles the actual
        send. When Meta credentials are configured, the call routes through
        Meta's Graph API and returns a `messageId` instead.
        """
        body: Dict[str, Any] = {"to": to}
        if message is not None:
            body["message"] = message
        if template_name is not None:
            body["templateName"] = template_name
        if template_params is not None:
            body["templateParams"] = template_params
        if template_language is not None:
            body["templateLanguage"] = template_language
        if caller_ref is not None:
            body["callerRef"] = caller_ref
        return self._client.post("/api/v1/messaging/whatsapp", json=body)

    def build_whatsapp_link(self, to: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Build a click-to-chat URL pair (wa.me + whatsapp://) without side effects.

        Use this when you only need the URL — e.g. rendering an "Open WhatsApp"
        button in an agent portal — and don't want the call recorded in the
        transactional message log. Use send_whatsapp() if you do want it logged.
        """
        body: Dict[str, Any] = {"to": to}
        if message is not None:
            body["message"] = message
        return self._client.post("/api/v1/messaging/whatsapp/link", json=body)

    def whatsapp_health(self) -> Dict[str, Any]:
        """Run the WhatsApp diagnostic probe.

        Returns the active operating mode (click_to_chat vs meta_cloud_api),
        per-check results, and the most recent FAILED rows from the
        transactional message log.
        """
        return self._client.get("/api/v1/messaging/whatsapp/health")

    def email_health(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/messaging/email/health")

    def sms_health(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/messaging/sms/health")

    def queue_stats(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/messaging/queue/stats")

    def process_queue(self) -> Dict[str, Any]:
        return self._client.post("/api/v1/messaging/queue/process")

    def get_processor(self) -> Dict[str, Any]:
        """Get the messaging processor configuration."""
        return self._client.get("/api/v1/messaging/processor")

    def update_processor(self, enabled: Optional[bool] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update the messaging processor configuration."""
        body: Dict[str, Any] = {}
        if enabled is not None:
            body["enabled"] = enabled
        if config is not None:
            body["config"] = config
        return self._client.put("/api/v1/messaging/processor", json=body)
