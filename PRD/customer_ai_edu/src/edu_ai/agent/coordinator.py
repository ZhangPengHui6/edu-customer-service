"""Agent 运行协调器：创建、执行、确认与取消。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.agent.errors import (
    ActionExecutionError,
    AgentExecutionError,
    RunConflictError,
    RunNotFoundError,
    TerminalErrorCode,
)
from edu_ai.agent.events import build_response_event
from edu_ai.agent.executor import AgentExecutor
from edu_ai.agent.handoff_router import HandoffIntent, HandoffRouter
from edu_ai.agent.output import (
    PRIORITY_BY_REASON,
    HandoffReason,
    HandoffRequest,
    ReplyType,
)
from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.tools.cs_client import CustomerServiceError
from edu_ai.agent.tools.snapshot import ToolCallReader
from edu_ai.agent.validators.output import AgentOutputValidator, ValidatedAgentOutput
from edu_ai.config import get_settings
from edu_ai.models import AgentRun
from edu_ai.repositories.action import ActionRepository
from edu_ai.repositories.run import AgentRunRepository
from edu_ai.repositories.tool import ToolCallRepository
from edu_ai.schemas.run import AgentRunRequest
from edu_ai.services.actions import ActionService

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class AgentRunCoordinator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.runs = AgentRunRepository(session)
        self.actions = ActionRepository(session)
        self.executor = AgentExecutor(
            AgentOutputValidator(ToolCallReader(ToolCallRepository(session)))
        )
        self.handoff_router = HandoffRouter()

    async def start_run(self, request: AgentRunRequest) -> dict[str, Any]:
        existing = await self.runs.find_by_request_id(request.request_id)
        if existing is not None:
            await self._recover_stale_run(existing)
            return build_response_event(existing)

        run = AgentRun(
            run_id=uuid4().hex,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            user_id=request.user_id,
            status="RUNNING",
            input_revision=request.input_revision,
            snapshot_revision=request.input_revision,
            main_model=self.settings.main_model,
            fast_model=self.settings.fast_model,
        )
        self.runs.add(run)
        try:
            await self.session.commit()
        except IntegrityError:
            # 同一 request_id 并发到达时只保留先落库的运行。
            await self.session.rollback()
            existing = await self.runs.find_by_request_id(request.request_id)
            if existing is None:
                raise
            return build_response_event(existing)

        context = self._runtime_context(request, run)
        try:
            validated = await self._decide(request, context)
            prepared = await self.actions.find_prepared(run.run_id)
            await self._persist_success(run, validated, prepared)
        except TimeoutError:
            # 模型或工具卡住时必须有终态，否则同一 request_id 会一直返回 409。
            logger.warning(
                "agent run timed out run_id=%s after %ss",
                run.run_id,
                self.settings.agent_execution_timeout_seconds,
            )
            await self.session.rollback()
            run = await self.runs.find_by_run_id(run.run_id) or run
            await self._persist_failure(
                run,
                TerminalErrorCode.AGENT_EXECUTION_FAILED,
                "AI 处理超时，请稍后重试",
            )
        except AgentExecutionError as exc:
            logger.warning(
                "agent run failed [%s] run_id=%s: %s", exc.code, run.run_id, exc
            )
            await self._persist_failure(run, exc.code, str(exc))
        except Exception:
            logger.exception("agent run crashed run_id=%s", run.run_id)
            await self._persist_failure(
                run, TerminalErrorCode.AGENT_EXECUTION_FAILED, "Agent 执行异常"
            )

        await self.session.commit()
        return build_response_event(run)

    async def confirm_run(
        self, run_id: str, input_revision: int | None
    ) -> dict[str, Any]:
        run = await self.runs.find_by_run_id(run_id)
        if run is None:
            raise RunNotFoundError("Agent 运行不存在")
        if run.status in ("COMPLETED", "HANDED_OFF", "FAILED", "SUPERSEDED"):
            return build_response_event(run)
        if run.status != "DECISION_PREPARED":
            raise RunConflictError("Agent 运行尚未准备写操作")

        if input_revision is not None and input_revision != run.input_revision:
            raise RunConflictError("会话快照已变化，不能确认本次写操作")

        action = await self.actions.find_prepared(run.run_id)
        if action is None:
            await self._persist_failure(
                run,
                TerminalErrorCode.ACTION_EXECUTION_FAILED,
                "没有可确认的写操作",
            )
            await self.session.commit()
            return build_response_event(run)

        context = AgentRuntimeContext(
            run_id=run.run_id,
            run_pk=str(run.id),
            tenant_id=str(run.tenant_id),
            user_id=str(run.user_id),
            conversation_id=str(run.conversation_id),
            turn_id=str(run.turn_id),
        )
        try:
            result = await ActionService.execute(action, context)
        except CustomerServiceError as exc:
            if 400 <= exc.status_code < 500:
                action.status = "failed"
                action.result = {
                    "status_code": exc.status_code,
                    "error": exc.detail,
                }
                run.status = "COMPLETED"
                run.completed_at = _now()
                run.output = {
                    "message_id": str(uuid4()),
                    "content": {
                        "text": exc.detail,
                        "reply_type": ReplyType.ANSWER.value,
                        "action_status": "rejected",
                    },
                }
                await self.session.commit()
                return build_response_event(run)

            await self.session.rollback()
            raise ActionExecutionError("客服系统暂时无法确认写操作") from exc

        action.status = "confirmed"
        action.result = result
        message = str(
            result.get("message")
            or "操作已提交成功，请留意后续通知。"
        )
        run.status = "COMPLETED"
        run.completed_at = _now()
        run.output = {
            "message_id": str(uuid4()),
            "content": {
                "text": message,
                "reply_type": ReplyType.ANSWER.value,
                "action": {
                    "action_type": action.action_type,
                    **{
                        key: value
                        for key, value in result.items()
                        if key in ("repair_no", "order_no", "status")
                    },
                },
            },
        }
        await self.session.commit()
        return build_response_event(run)

    async def cancel_run(self, run_id: str) -> None:
        run = await self.runs.find_by_run_id(run_id)
        if run is None:
            raise RunNotFoundError("Agent 运行不存在")
        if run.status in ("COMPLETED", "HANDED_OFF", "FAILED", "SUPERSEDED"):
            return

        run.status = "SUPERSEDED"
        run.completed_at = _now()
        for action in await self.actions.list_by_run(run.run_id):
            if action.status == "prepared":
                action.status = "cancelled"
                action.result = {"reason": "run_superseded"}
        await self.session.commit()

    async def get_run(self, run_id: str) -> AgentRun:
        run = await self.runs.find_by_run_id(run_id)
        if run is None:
            raise RunNotFoundError("Agent 运行不存在")
        return run

    def _runtime_context(
        self, request: AgentRunRequest, run: AgentRun
    ) -> AgentRuntimeContext:
        customer_texts = tuple(
            str(message.content.get("text", ""))
            for message in (*request.history[-6:], *request.messages)
            if message.role == "customer" and message.type == "text"
        )
        return AgentRuntimeContext(
            run_id=run.run_id,
            run_pk=str(run.id),
            tenant_id=str(run.tenant_id),
            user_id=str(run.user_id),
            conversation_id=str(run.conversation_id),
            turn_id=str(run.turn_id),
            customer_texts=customer_texts,
        )

    async def _decide(
        self, request: AgentRunRequest, context: AgentRuntimeContext
    ) -> ValidatedAgentOutput:
        """先让轻量模型识别转人工意图，命中后直接转接，其余交给主 Agent。"""
        intent = await self.handoff_router.detect(request)
        if intent is not None:
            return self._handoff_output(intent)
        return await asyncio.wait_for(
            self.executor.execute(request, context),
            timeout=self.settings.agent_execution_timeout_seconds,
        )

    @staticmethod
    def _handoff_output(intent: HandoffIntent) -> ValidatedAgentOutput:
        summary = intent.summary.strip() or "用户明确要求转人工客服。"
        return ValidatedAgentOutput(
            reply_type=ReplyType.REQUEST_HANDOFF,
            reply_content="好的，正在为您转接人工客服，请稍候。",
            handoff_request=HandoffRequest(
                reason_code=intent.reason_code,
                summary=summary[:500],
            ),
        )

    async def _recover_stale_run(self, run: AgentRun) -> None:
        """进程重启或执行卡死会留下 RUNNING 运行，超时后按失败收尾。"""
        if run.status != "RUNNING":
            return
        created = run.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        # created_at 由数据库时钟写入，应用服务器与数据库可能有时间偏差，
        # 所以用数据库当前时间比较，避免把正常运行误判为陈旧。
        db_now = await self.session.scalar(select(func.now())) or _now()
        age = (db_now - created).total_seconds()
        if age < self.settings.agent_run_stale_seconds:
            return
        logger.warning(
            "agent run %s stuck in RUNNING for %.0fs, marking failed",
            run.run_id,
            age,
        )
        await self._persist_failure(
            run,
            TerminalErrorCode.AGENT_EXECUTION_FAILED,
            "运行超时未完成，请重试",
        )
        await self.session.commit()

    async def _persist_success(
        self,
        run: AgentRun,
        validated,
        prepared,
    ) -> None:
        run.usage = validated.token_usage
        run.output = {
            "message_id": str(uuid4()),
            "content": {
                "text": validated.reply_content,
                "reply_type": validated.reply_type.value,
            },
        }

        if validated.reply_type == ReplyType.REQUEST_HANDOFF:
            handoff = validated.handoff_request
            run.status = "HANDED_OFF"
            run.completed_at = _now()
            priority = PRIORITY_BY_REASON[handoff.reason_code]
            run.output = {
                "message_id": str(uuid4()),
                "reason_code": handoff.reason_code.value,
                "summary": handoff.summary,
                "message": validated.reply_content,
                "priority": priority,
            }
            await self._cancel_prepared(prepared)
            return

        if prepared is not None and validated.reply_type == ReplyType.ANSWER:
            run.status = "DECISION_PREPARED"
            run.decision = {
                "action_id": str(prepared.id),
                "action_type": prepared.action_type,
                "payload": prepared.payload,
            }
            return

        await self._cancel_prepared(prepared)
        run.status = "COMPLETED"
        run.completed_at = _now()

    async def _persist_failure(
        self, run: AgentRun, code, message: str
    ) -> None:
        run.status = "FAILED"
        run.error = message[:2000]
        run.completed_at = _now()
        run.output = {
            "code": str(code),
            "message": "AI 服务处理失败，请稍后重试",
        }

    @staticmethod
    async def _cancel_prepared(prepared) -> None:
        if prepared is not None and prepared.status == "prepared":
            prepared.status = "cancelled"
            prepared.result = {"reason": "not_selected_by_model"}
