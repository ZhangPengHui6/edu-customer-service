"""会话轮次仓储。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import Conversation, ConversationTurn


class TurnRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_processing(self, conversation_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ConversationTurn.conversation_id == conversation_id,
                        ConversationTurn.status.in_(("COLLECTING", "RUNNING")),
                    )
                )
            )
        )

    async def find_collecting_for_update(
        self, conversation_id: UUID
    ) -> ConversationTurn | None:
        return await self.session.scalar(
            select(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conversation_id,
                ConversationTurn.status == "COLLECTING",
            )
            .with_for_update()
        )

    async def get(self, turn_id: UUID) -> ConversationTurn | None:
        return await self.session.get(ConversationTurn, turn_id)

    async def find_turn_with_conversation(
        self, turn_id: UUID, *, for_update: bool = True
    ) -> tuple[ConversationTurn, Conversation] | None:
        stmt = (
            select(ConversationTurn, Conversation)
            .join(Conversation, Conversation.id == ConversationTurn.conversation_id)
            .where(ConversationTurn.id == turn_id)
        )
        if for_update:
            stmt = stmt.with_for_update(of=Conversation)
        row = (await self.session.execute(stmt)).tuples().one_or_none()
        return row

    async def claim_ready(self, now: datetime) -> tuple[ConversationTurn, Conversation] | None:
        """领取一条到期的 COLLECTING 轮次。

        SKIP LOCKED 让多个 worker 可以并行领取而不会互相等待；会话行不加锁，
        避免阻塞客户继续发消息。会话模式与快照在领取后立即读取。
        """
        turn = await self.session.scalar(
            select(ConversationTurn)
            .join(Conversation, Conversation.id == ConversationTurn.conversation_id)
            .where(
                ConversationTurn.status == "COLLECTING",
                ConversationTurn.collect_until <= now,
                Conversation.mode == "AI",
            )
            .order_by(ConversationTurn.collect_until, ConversationTurn.created_at)
            .limit(1)
            .with_for_update(skip_locked=True, of=ConversationTurn)
        )
        if turn is None:
            return None
        conversation = await self.session.get(Conversation, turn.conversation_id)
        if conversation is None:  # 外键保证不会发生，防御性判断
            return None
        return turn, conversation

    async def list_expired_running(self, now: datetime, limit: int = 50) -> list[ConversationTurn]:
        turns = await self.session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.status == "RUNNING",
                ConversationTurn.locked_until <= now,
            )
            .order_by(ConversationTurn.locked_until)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(turns.all())
