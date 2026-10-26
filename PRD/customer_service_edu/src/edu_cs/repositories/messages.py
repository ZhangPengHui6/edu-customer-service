"""消息仓储。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import Conversation, Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_message_id(
        self, message_id: UUID
    ) -> tuple[Message, Conversation] | None:
        return (
            await self.session.execute(
                select(Message, Conversation)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Message.message_id == message_id)
            )
        ).tuples().one_or_none()

    def add(self, message: Message) -> Message:
        self.session.add(message)
        return message

    async def find_current_range(
        self,
        conversation_id: UUID,
        start_revision: int,
        snapshot_revision: int,
    ) -> list[Message]:
        """当前轮次覆盖的客户消息（按输入版本范围）。"""
        messages = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.input_revision.is_not(None),
                Message.input_revision >= start_revision,
                Message.input_revision <= snapshot_revision,
            )
            .order_by(Message.input_revision, Message.id)
        )
        return list(messages.all())

    async def history_before(
        self, conversation_id: UUID, before_id: int, limit: int
    ) -> list[Message]:
        messages = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id < before_id,
            )
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(reversed(messages.all()))

    async def list_after(
        self, conversation_id: UUID, after_id: int, limit: int
    ) -> list[Message]:
        messages = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id > after_id,
            )
            .order_by(Message.id)
            .limit(limit)
        )
        return list(messages.all())

    async def latest_for_conversation(
        self, conversation_id: UUID, limit: int = 50
    ) -> list[Message]:
        messages = await self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(reversed(messages.all()))
