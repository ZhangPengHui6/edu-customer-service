"""工具调用审计仓储。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.models import AgentToolCall


class ToolCallRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def next_seq(self, run_pk: UUID) -> int:
        current = await self.session.scalar(
            select(func.coalesce(func.max(AgentToolCall.seq), 0)).where(
                AgentToolCall.run_pk == run_pk
            )
        )
        return int(current or 0) + 1

    def add(self, call: AgentToolCall) -> AgentToolCall:
        self.session.add(call)
        return call

    async def find(self, run_pk: UUID, seq: int) -> AgentToolCall | None:
        return await self.session.scalar(
            select(AgentToolCall).where(
                AgentToolCall.run_pk == run_pk,
                AgentToolCall.seq == seq,
            )
        )

    async def complete(
        self,
        run_pk: UUID,
        seq: int,
        *,
        result: dict | None,
        status: str,
        error: str | None,
        duration_ms: int,
    ) -> None:
        call = await self.find(run_pk, seq)
        if call is None:
            return
        call.result = result
        call.status = status
        call.error = error
        call.duration_ms = duration_ms

    async def list_by_run(self, run_pk: UUID) -> list[AgentToolCall]:
        rows = await self.session.scalars(
            select(AgentToolCall)
            .where(AgentToolCall.run_pk == run_pk)
            .order_by(AgentToolCall.seq)
        )
        return list(rows.all())
