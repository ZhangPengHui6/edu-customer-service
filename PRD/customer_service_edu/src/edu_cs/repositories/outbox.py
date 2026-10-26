"""实时事件 Outbox 仓储。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import OutboxDeadLetter, RealtimeOutbox


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, event: RealtimeOutbox) -> RealtimeOutbox:
        self.session.add(event)
        return event

    async def claim_batch(self, limit: int = 100) -> list[RealtimeOutbox]:
        """锁定一批尚未发布的事件，发布成功后同一事务内标记。"""
        events = await self.session.scalars(
            select(RealtimeOutbox)
            .where(RealtimeOutbox.published_at.is_(None))
            .order_by(RealtimeOutbox.sequence)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(events.all())

    @staticmethod
    def mark_published(event: RealtimeOutbox) -> None:
        event.published_at = datetime.now(UTC)

    @staticmethod
    def mark_failed(event: RealtimeOutbox, error: Exception | str) -> None:
        event.attempts += 1
        event.last_error = str(error)[:2000]

    def dead_letter(self, event: RealtimeOutbox) -> None:
        self.session.add(
            OutboxDeadLetter(
                sequence=event.sequence,
                payload={
                    "channel": event.channel,
                    "event_type": event.event_type,
                    "conversation_id": str(event.conversation_id)
                    if event.conversation_id
                    else None,
                    "data": event.data,
                },
                error=event.last_error or "unknown",
            )
        )
        event.published_at = datetime.now(UTC)
