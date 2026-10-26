"""AI 服务内部接口：仅供客服服务以受信身份调用。"""

from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.agent.coordinator import AgentRunCoordinator
from edu_ai.agent.errors import (
    ActionExecutionError,
    RunConflictError,
    RunNotFoundError,
    RunStatus,
)
from edu_ai.config import get_settings
from edu_ai.db import get_session
from edu_ai.models import AgentRun, AgentToolCall
from edu_ai.repositories.run import AgentRunRepository
from edu_ai.repositories.tool import ToolCallRepository
from edu_ai.schemas.run import AgentRunRequest, ConfirmRunRequest, RunSummary

router = APIRouter(prefix="/internal/v1/agent", tags=["internal"])


def require_internal_token(
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    expected = get_settings().internal_service_token
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="无效的内部服务凭据")


InternalAuth = Annotated[None, Depends(require_internal_token)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_coordinator(session: SessionDep) -> AgentRunCoordinator:
    return AgentRunCoordinator(session)


CoordinatorDep = Annotated[AgentRunCoordinator, Depends(get_coordinator)]


@router.post("/runs", summary="启动一次 Agent 运行")
async def start_run(
    payload: AgentRunRequest, _: InternalAuth, coordinator: CoordinatorDep
) -> dict:
    try:
        return await coordinator.start_run(payload)
    except RunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/confirm", summary="确认已准备的写操作")
async def confirm_run(
    run_id: str,
    payload: ConfirmRunRequest,
    _: InternalAuth,
    coordinator: CoordinatorDep,
) -> dict:
    try:
        return await coordinator.confirm_run(run_id, payload.input_revision)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActionExecutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/runs/{run_id}/cancel",
    status_code=204,
    response_class=Response,
    summary="取消运行并作废未执行的写操作",
)
async def cancel_run(
    run_id: str, _: InternalAuth, coordinator: CoordinatorDep
) -> Response:
    try:
        await coordinator.cancel_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/runs", summary="按租户查询 Agent 运行")
async def list_runs(
    session: SessionDep,
    _: InternalAuth,
    tenant_id: UUID,
    status: RunStatus | None = None,
    conversation_id: UUID | None = None,
    turn_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    runs = await AgentRunRepository(session).list_runs(
        tenant_id,
        status=status.value if status else None,
        conversation_id=conversation_id,
        turn_id=turn_id,
        limit=limit,
    )
    return {"items": [_to_summary(run).model_dump(mode="json") for run in runs]}


@router.get("/runs/{run_id}/tool-calls", summary="查询运行的业务工具调用")
async def list_tool_calls(
    run_id: str,
    session: SessionDep,
    _: InternalAuth,
    tenant_id: UUID | None = None,
) -> dict:
    run = await AgentRunRepository(session).find_by_run_id(run_id)
    if run is None or (tenant_id is not None and run.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Agent 运行不存在")
    calls = await ToolCallRepository(session).list_by_run(run.id)
    return {
        "run_id": run_id,
        "items": [_to_tool_call(call) for call in calls],
    }


@router.get("/runs/{run_id}", response_model=RunSummary, summary="查询运行状态")
async def get_run(
    run_id: str,
    _: InternalAuth,
    coordinator: CoordinatorDep,
    tenant_id: UUID | None = None,
) -> RunSummary:
    try:
        run = await coordinator.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if tenant_id is not None and run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Agent 运行不存在")
    return _to_summary(run)


def _to_summary(run: AgentRun) -> RunSummary:
    return RunSummary(
        run_id=run.run_id,
        request_id=run.request_id,
        tenant_id=run.tenant_id,
        conversation_id=run.conversation_id,
        turn_id=run.turn_id,
        status=run.status,
        intent=run.intent,
        skill_code=run.skill_code,
        input_revision=run.input_revision,
        output=run.output,
        usage=run.usage,
        error=run.error,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _to_tool_call(call: AgentToolCall) -> dict:
    return {
        "seq": call.seq,
        "tool_name": call.tool_name,
        "status": call.status,
        "arguments": call.arguments,
        "result": call.result,
        "error": call.error,
        "duration_ms": call.duration_ms,
        "created_at": call.created_at.isoformat(),
    }
