# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================

"""Contextual Messaging (Threads) service — channels, threads, messages, flags, escalation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import PlatformXeClient


class ThreadsService:
    def __init__(self, client: PlatformXeClient):
        self._client = client

    # ── Channels ──────────────────────────────────────────────────────────

    def create_channel(
        self,
        slug: str,
        display_name: str,
        entity_type: str,
        participant_roles: List[str],
        default_visibility: List[str],
        lifecycle_rules: Optional[Dict[str, Any]] = None,
        escalation_config: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post("/api/v1/threads/channels", json={
            "slug": slug,
            "displayName": display_name,
            "entityType": entity_type,
            "participantRoles": participant_roles,
            "defaultVisibility": default_visibility,
            "lifecycleRules": lifecycle_rules,
            "escalationConfig": escalation_config,
            "webhookUrl": webhook_url,
        })

    def list_channels(self) -> Dict[str, Any]:
        return self._client.get("/api/v1/threads/channels")

    def update_channel(self, channel_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/threads/channels/{channel_id}", json=kwargs)

    def get_escalation_config(self, channel_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/threads/channels/{channel_id}/escalation")

    def set_escalation_config(self, channel_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.put(f"/api/v1/threads/channels/{channel_id}/escalation", json=config)

    # ── Threads ───────────────────────────────────────────────────────────

    def create_thread(
        self,
        channel_slug: str,
        entity_id: str,
        participants: List[Dict[str, str]],
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._client.post("/api/v1/threads", json={
            "channelSlug": channel_slug,
            "entityId": entity_id,
            "subject": subject,
            "metadata": metadata,
            "participants": participants,
        })

    def list_threads(self, **params: Any) -> Dict[str, Any]:
        return self._client.get("/api/v1/threads", params=params)

    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/threads/{thread_id}")

    def close_thread(self, thread_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/close", json={"reason": reason})

    def reopen_thread(self, thread_id: str) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/reopen")

    def entity_event(
        self,
        channel_slug: str,
        entity_id: str,
        event: str,
        new_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post("/api/v1/threads/entity-event", json={
            "channelSlug": channel_slug,
            "entityId": entity_id,
            "event": event,
            "newStatus": new_status,
        })

    # ── Messages ──────────────────────────────────────────────────────────

    def send_message(
        self,
        thread_id: str,
        sender_external_id: str,
        sender_role: str,
        content: str,
        visibility: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/messages", json={
            "senderExternalId": sender_external_id,
            "senderRole": sender_role,
            "content": content,
            "visibility": visibility,
        })

    def list_messages(
        self,
        thread_id: str,
        role: str,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return self._client.get(
            f"/api/v1/threads/{thread_id}/messages",
            params={"page": page, "limit": limit},
            headers={"x-participant-role": role},
        )

    def send_system_message(
        self,
        thread_id: str,
        content: str,
        visibility: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/messages/system", json={
            "content": content,
            "visibility": visibility or ["ALL"],
        })

    def edit_message(self, message_id: str, content: str) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/threads/messages/{message_id}", json={"content": content})

    def delete_message(self, message_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/threads/messages/{message_id}")

    # ── Read State & Inbox ────────────────────────────────────────────────

    def mark_read(
        self,
        thread_id: str,
        external_id: str,
        role: str,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/read", json={
            "participantExternalId": external_id,
            "participantRole": role,
            "messageId": message_id,
        })

    def get_read_states(self, thread_id: str) -> Dict[str, Any]:
        return self._client.get(f"/api/v1/threads/{thread_id}/read-state")

    def inbox(
        self,
        external_id: str,
        role: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"externalId": external_id, "role": role, "page": page, "limit": limit}
        if status:
            params["status"] = status
        return self._client.get("/api/v1/threads/inbox", params=params)

    def unread_count(self, external_id: str, role: str) -> Dict[str, Any]:
        return self._client.get("/api/v1/threads/inbox/unread-count", params={
            "externalId": external_id,
            "role": role,
        })

    # ── Flags & Escalation ────────────────────────────────────────────────

    def flag_message(
        self,
        thread_id: str,
        message_id: str,
        reason: str,
        flagged_by_external_id: str,
        flagged_by_role: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.post(
            f"/api/v1/threads/{thread_id}/messages/{message_id}/flag",
            json={
                "reason": reason,
                "note": note,
                "flaggedByExternalId": flagged_by_external_id,
                "flaggedByRole": flagged_by_role,
            },
        )

    def escalate_thread(
        self,
        thread_id: str,
        reason: str,
        escalated_by_external_id: str,
        escalated_by_role: str,
    ) -> Dict[str, Any]:
        return self._client.post(f"/api/v1/threads/{thread_id}/escalate", json={
            "reason": reason,
            "escalatedByExternalId": escalated_by_external_id,
            "escalatedByRole": escalated_by_role,
        })

    def review_flag(
        self,
        flag_id: str,
        status: str,
        reviewed_by_external_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client.patch(f"/api/v1/threads/flags/{flag_id}", json={
            "status": status,
            "reviewedByExternalId": reviewed_by_external_id,
            "note": note,
        })

    def list_flags(self, thread_id: str, status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        return self._client.get(f"/api/v1/threads/{thread_id}/flags", params=params)

    def list_flags_across_threads(
        self,
        status: Optional[str] = None,
        channel_slug: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if channel_slug:
            params["channelSlug"] = channel_slug
        return self._client.get("/api/v1/threads/flags", params=params)

    # ── Participants ─────────────────────────────────────────────────────

    def add_participant(
        self,
        thread_id: str,
        role: str,
        external_id: str,
        display_name: str,
        avatar_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "role": role,
            "externalId": external_id,
            "displayName": display_name,
        }
        if avatar_url is not None:
            body["avatarUrl"] = avatar_url
        return self._client.post(f"/api/v1/threads/{thread_id}/participants", json=body)

    def remove_participant(self, thread_id: str, participant_id: str) -> Dict[str, Any]:
        return self._client.delete(f"/api/v1/threads/{thread_id}/participants/{participant_id}")

    def update_participant(
        self,
        thread_id: str,
        participant_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        is_muted: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if display_name is not None:
            body["displayName"] = display_name
        if avatar_url is not None:
            body["avatarUrl"] = avatar_url
        if is_muted is not None:
            body["isMuted"] = is_muted
        return self._client.patch(
            f"/api/v1/threads/{thread_id}/participants/{participant_id}",
            json=body,
        )

    def update_thread(
        self,
        thread_id: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if subject is not None:
            body["subject"] = subject
        if metadata is not None:
            body["metadata"] = metadata
        return self._client.patch(f"/api/v1/threads/{thread_id}", json=body)
