"""实时事件构建与 Outbox 写入。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import Conversation, Handoff, Message, RealtimeOutbox
from edu_cs.repositories.outbox import OutboxRepository

USER_CHANNEL_PREFIX = "cs:user:"
STAFF_CHANNEL_PREFIX = "cs:staff:"

MESSAGE_CREATED = "message.created"
HANDOFF_CHANGED = "handoff.changed"
CONVERSATION_MODE_CHANGED = "conversation.mode_changed"


def user_channel(user_id: UUID) -> str:
    return f"{USER_CHANNEL_PREFIX}{user_id}"


def staff_channel(tenant_id: UUID) -> str:
    return f"{STAFF_CHANNEL_PREFIX}{tenant_id}"


def message_payload(message: Message) -> dict[str, Any]:
    return {
        "sequence": message.id,
        "message_id": str(message.message_id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "type": message.message_type,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def handoff_payload(handoff: Handoff, conversation: Conversation) -> dict[str, Any]:
    return {
        "handoff_id": str(handoff.id),
        "status": handoff.status,
        "summary": handoff.summary,
        "priority": handoff.priority,
        "assigned_agent_id": str(handoff.assigned_agent_id)
        if handoff.assigned_agent_id
        else None,
        "conversation_mode": conversation.mode,
    }


def build_event(
    sequence: int,
    event_type: str,
    event_data: dict[str, Any],
    conversation_id: UUID | None,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "event_type": event_type,
        "event_data": event_data,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "event_created_at": created_at.isoformat(),
    }


class RealtimeOutboxService:
    """在当前业务事务内写事件，后续由 outbox worker 投递到 Redis。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = OutboxRepository(session)

    def add_message_created(
        self,
        conversation: Conversation,
        message: Message,
        *,
        notify_user: bool,
        notify_staff: bool,
    ) -> None:
        channels: list[str] = []
        if notify_user:
            channels.append(user_channel(conversation.user_id))
        if notify_staff:
            channels.append(staff_channel(conversation.tenant_id))
        for channel in channels:
            self._add(
                conversation,
                channel,
                MESSAGE_CREATED,
                message_payload(message),
            )

    def add_handoff_changed(
        self, conversation: Conversation, handoff: Handoff
    ) -> None:
        data = handoff_payload(handoff, conversation)
        for channel in (
            user_channel(conversation.user_id),
            staff_channel(conversation.tenant_id),
        ):
            self._add(conversation, channel, HANDOFF_CHANGED, data)

    def add_mode_changed(self, conversation: Conversation) -> None:
        data = {
            "conversation_id": str(conversation.id),
            "mode": conversation.mode,
        }
        for channel in (
            user_channel(conversation.user_id),
            staff_channel(conversation.tenant_id),
        ):
            self._add(conversation, channel, CONVERSATION_MODE_CHANGED, data)

    def _add(
        self,
        conversation: Conversation,
        channel: str,
        event_type: str,
        data: dict[str, Any],
    ) -> RealtimeOutbox:
        event = RealtimeOutbox(
            tenant_id=conversation.tenant_id,
            channel=channel,
            event_type=event_type,
            conversation_id=conversation.id,
            data=data,
        )
        self.repository.add(event)
        return event
