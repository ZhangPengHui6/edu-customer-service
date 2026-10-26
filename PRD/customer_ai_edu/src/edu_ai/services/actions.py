"""写操作：准备、确认执行与取消。"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.tools.cs_client import CustomerServiceClient
from edu_ai.agent.tools.result import ActionPreparedData, ToolBusinessError
from edu_ai.db import SessionFactory
from edu_ai.models import ActionRequest
from edu_ai.repositories.action import ActionRepository

REPAIR_ACTION = "create_repair_ticket"
CANCEL_ACTION = "cancel_unshipped_order"


def _idempotency_key(context: AgentRuntimeContext, action_type: str, resource: str) -> str:
    """同一轮次内同一资源重复准备时复用同一个键。

    客服侧会用该键确定性生成维修单号，因此 AI 重试不会产生重复工单。
    """
    raw = f"{context.turn_id}:{action_type}:{resource}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ActionService:
    @staticmethod
    async def prepare(
        context: AgentRuntimeContext,
        *,
        action_type: str,
        resource: str,
        payload: dict[str, Any],
    ) -> ActionPreparedData:
        key = _idempotency_key(context, action_type, resource)
        async with SessionFactory() as session:
            repository = ActionRepository(session)
            existing = await repository.find_by_key(key)
            if existing is not None:
                # 同一轮次重试会复用幂等键：动作必须跟随当前运行，才能被确认执行。
                if existing.status == "cancelled":
                    existing.status = "prepared"
                    existing.result = None
                if existing.status == "prepared" and existing.run_id != context.run_id:
                    existing.run_id = context.run_id
                await session.commit()
                return ActionPreparedData(
                    action_id=str(existing.id),
                    action_type=existing.action_type,
                    status=existing.status,
                    detail=existing.payload,
                )

            action = ActionRequest(
                tenant_id=UUID(context.tenant_id),
                run_id=context.run_id,
                conversation_id=UUID(context.conversation_id),
                action_type=action_type,
                payload=payload,
                status="prepared",
                idempotency_key=key,
            )
            repository.add(action)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await repository.find_by_key(key)
                if existing is None:
                    raise
                return ActionPreparedData(
                    action_id=str(existing.id),
                    action_type=existing.action_type,
                    status=existing.status,
                    detail=existing.payload,
                )
            await session.refresh(action)
            return ActionPreparedData(
                action_id=str(action.id),
                action_type=action.action_type,
                status=action.status,
                detail=action.payload,
            )

    @staticmethod
    async def execute(
        action: ActionRequest,
        context: AgentRuntimeContext,
    ) -> dict[str, Any]:
        client = CustomerServiceClient(context)
        if action.action_type == REPAIR_ACTION:
            return await client.post(
                "/internal/v1/tools/repairs",
                {
                    **action.payload,
                    "conversation_id": str(action.conversation_id),
                },
                idempotency_key=action.idempotency_key,
            )
        if action.action_type == CANCEL_ACTION:
            order_no = str(action.payload.get("order_no", ""))
            return await client.post(
                f"/internal/v1/tools/orders/{order_no}/cancel",
                {"reason": action.payload.get("reason")},
                idempotency_key=action.idempotency_key,
            )
        raise ToolBusinessError("UNSUPPORTED_ACTION", "不支持的写操作类型")
