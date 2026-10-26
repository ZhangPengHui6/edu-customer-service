"""会话仓储。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import Conversation

OPEN_MODES = ("AI", "QUEUED", "HUMAN", "REPAIR")


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_open(
        self, tenant_id: UUID, user_id: UUID, channel: str
    ) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation).where(
                Conversation.tenant_id == tenant_id,
                Conversation.user_id == user_id,
                Conversation.channel == channel,
                Conversation.mode.in_(OPEN_MODES),
            )
        )

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def get_for_update(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
        )

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    def close(self, conversation: Conversation, reason: str) -> None:
        conversation.mode = "CLOSED"
        conversation.close_reason = reason
        conversation.ended_at = conversation.last_active_at or datetime.now(UTC)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        mode: str | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .order_by(Conversation.last_active_at.desc())
            .limit(limit)
        )
        if mode:
            stmt = stmt.where(Conversation.mode == mode)
        return list((await self.session.scalars(stmt)).all())

    async def count_by_mode(self, tenant_id: UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(Conversation.mode, func.count())
            .where(Conversation.tenant_id == tenant_id)
            .group_by(Conversation.mode)
        )
        return {mode: count for mode, count in result.all()}
