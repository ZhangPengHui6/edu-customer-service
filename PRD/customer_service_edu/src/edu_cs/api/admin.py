"""运营与审计接口。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from edu_cs.api.deps import (
    PrincipalDep,
    SessionDep,
    require_roles,
    resolve_staff_tenant,
)
from edu_cs.clients.ai import (
    AIServiceClient,
    AIServiceError,
    AIServiceNotFoundError,
)
from edu_cs.models import (
    AuditLog,
    ConversationTurn,
    Handoff,
    Message,
    RealtimeOutbox,
)
from edu_cs.repositories.conversations import ConversationRepository
from edu_cs.security import Principal

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

TenantQuery = Annotated[UUID | None, Query()]

RunStatusFilter = Literal[
    "RUNNING",
    "DECISION_PREPARED",
    "COMPLETED",
    "HANDED_OFF",
    "FAILED",
    "SUPERSEDED",
]


def _scoped_tenant(principal: Principal, tenant_id: UUID | None) -> UUID:
    require_roles(principal, "admin")
    resolved, _ = resolve_staff_tenant(principal, tenant_id)
    return resolved


@router.get("/metrics/overview")
async def metrics_overview(
    principal: PrincipalDep,
    session: SessionDep,
    tenant_id: TenantQuery = None,
) -> dict:
    scope = _scoped_tenant(principal, tenant_id)
    since = datetime.now(UTC) - timedelta(hours=24)

    conversation_modes = await ConversationRepository(session).count_by_mode(scope)

    handoff_rows = (
        await session.execute(
            select(Handoff.status, func.count())
            .where(Handoff.tenant_id == scope)
            .group_by(Handoff.status)
        )
    ).all()

    turn_rows = (
        await session.execute(
            select(ConversationTurn.status, func.count())
            .where(
                ConversationTurn.tenant_id == scope,
                ConversationTurn.created_at >= since,
            )
            .group_by(ConversationTurn.status)
        )
    ).all()

    outbox_rows = (
        await session.execute(
            select(RealtimeOutbox.status, func.count())
            .where(RealtimeOutbox.tenant_id == scope)
            .group_by(RealtimeOutbox.status)
        )
    ).all()

    message_count = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.tenant_id == scope, Message.created_at >= since)
    )

    return {
        "tenant_id": str(scope),
        "window_hours": 24,
        "conversations": conversation_modes,
        "handoffs": {status: count for status, count in handoff_rows},
        "turns": {status: count for status, count in turn_rows},
        "realtime_outbox": {status: count for status, count in outbox_rows},
        "messages_last_24h": message_count or 0,
    }


@router.get("/audits")
async def list_audits(
    principal: PrincipalDep,
    session: SessionDep,
    tenant_id: TenantQuery = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    scope = _scoped_tenant(principal, tenant_id)
    rows = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == scope)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    ).all()
    return {
        "tenant_id": str(scope),
        "items": [
            {
                "id": row.id,
                "actor_id": str(row.actor_id) if row.actor_id else None,
                "action": row.action,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "before": row.before,
                "after": row.after,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/ai/runs")
async def list_ai_runs(
    principal: PrincipalDep,
    tenant_id: TenantQuery = None,
    status_filter: Annotated[RunStatusFilter | None, Query(alias="status")] = None,
    conversation_id: Annotated[UUID | None, Query()] = None,
    turn_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    """按租户查看 AI 运行记录，可按会话或轮次过滤。"""
    scope = _scoped_tenant(principal, tenant_id)
    try:
        result = await AIServiceClient().list_runs(
            scope,
            status=status_filter,
            conversation_id=conversation_id,
            turn_id=turn_id,
            limit=limit,
        )
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务暂时不可用",
        ) from exc
    return {"tenant_id": str(scope), **result}


@router.get("/ai/runs/{run_id}")
async def ai_run_detail(
    run_id: str,
    principal: PrincipalDep,
    tenant_id: TenantQuery = None,
) -> dict:
    """查看单次 AI 运行及其工具调用审计。"""
    scope = _scoped_tenant(principal, tenant_id)
    client = AIServiceClient()
    try:
        run = await client.get_run(run_id, tenant_id=scope)
        tool_calls = await client.list_tool_calls(run_id, tenant_id=scope)
    except AIServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务暂时不可用",
        ) from exc
    return {
        "tenant_id": str(scope),
        "run": run,
        "tool_calls": tool_calls.get("items", []),
    }
