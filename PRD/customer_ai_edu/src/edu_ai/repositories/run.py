"""Agent 运行仓储。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.models import AgentRun


class AgentRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, run: AgentRun) -> AgentRun:
        self.session.add(run)
        return run

    async def find_by_run_id(self, run_id: str) -> AgentRun | None:
        return await self.session.scalar(
            select(AgentRun).where(AgentRun.run_id == run_id)
        )

    async def find_by_request_id(self, request_id: str) -> AgentRun | None:
        return await self.session.scalar(
            select(AgentRun).where(AgentRun.request_id == request_id)
        )

    async def list_recent(self, tenant_id: UUID, limit: int = 50) -> list[AgentRun]:
        return await self.list_runs(tenant_id, limit=limit)

    async def list_runs(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        conversation_id: UUID | None = None,
        turn_id: UUID | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        """运营侧按租户查看运行记录；session 与 turn 用于定位单次对话。"""
        conditions = [AgentRun.tenant_id == tenant_id]
        if status is not None:
            conditions.append(AgentRun.status == status)
        if conversation_id is not None:
            conditions.append(AgentRun.conversation_id == conversation_id)
        if turn_id is not None:
            conditions.append(AgentRun.turn_id == turn_id)
        rows = await self.session.scalars(
            select(AgentRun)
            .where(*conditions)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())
