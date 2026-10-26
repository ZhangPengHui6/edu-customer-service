"""写操作请求仓储。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.models import ActionRequest


class ActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, action: ActionRequest) -> ActionRequest:
        self.session.add(action)
        return action

    async def get(self, action_id: UUID) -> ActionRequest | None:
        return await self.session.get(ActionRequest, action_id)

    async def find_by_key(self, idempotency_key: str) -> ActionRequest | None:
        return await self.session.scalar(
            select(ActionRequest).where(
                ActionRequest.idempotency_key == idempotency_key
            )
        )

    async def find_prepared(self, run_id: str) -> ActionRequest | None:
        return await self.session.scalar(
            select(ActionRequest)
            .where(
                ActionRequest.run_id == run_id,
                ActionRequest.status == "prepared",
            )
            .order_by(ActionRequest.created_at.desc())
        )

    async def list_by_run(self, run_id: str) -> list[ActionRequest]:
        rows = await self.session.scalars(
            select(ActionRequest)
            .where(ActionRequest.run_id == run_id)
            .order_by(ActionRequest.created_at)
        )
        return list(rows.all())
