"""统一执行、校验并记录 Agent 工具调用。"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.tools.result import (
    ToolBusinessError,
    ToolFailureCode,
    ToolFailureType,
    ToolResult,
)
from edu_ai.db import SessionFactory
from edu_ai.models import AgentToolCall
from edu_ai.repositories.tool import ToolCallRepository

logger = logging.getLogger(__name__)

ToolOperation = Callable[[], Awaitable[Any]]


class ToolExecutor:
    async def execute(
        self,
        runtime_context: AgentRuntimeContext,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        operation: ToolOperation,
        output_schema: Any,
    ) -> str:
        started_at = perf_counter()
        try:
            response_data = await operation()
        except ToolBusinessError as exc:
            tool_result = ToolResult[Any](
                success=False,
                code=exc.code,
                message=exc.message,
                failure_type=ToolFailureType.BUSINESS,
            )
        except Exception:
            logger.exception("工具调用失败 [%s] run=%s", tool_name, runtime_context.run_id)
            tool_result = ToolResult[Any](
                success=False,
                code=ToolFailureCode.TOOL_CALL_FAILED,
                message="暂时无法取得可靠的业务数据，请稍后重试",
                failure_type=ToolFailureType.SERVICE_CALL,
            )
        else:
            tool_result = self._validate_result(response_data, output_schema)

        duration_ms = int((perf_counter() - started_at) * 1000)
        await self._save(
            runtime_context,
            tool_call_id,
            tool_name,
            arguments,
            tool_result,
            duration_ms,
        )
        return json.dumps(
            tool_result.model_dump(mode="json"), ensure_ascii=False
        )

    @staticmethod
    def _validate_result(response_data: Any, output_schema: Any) -> ToolResult[Any]:
        try:
            adapter = TypeAdapter(output_schema)
            validated = adapter.validate_python(response_data)
            return ToolResult[Any](
                success=True,
                code="TOOL_CALL_OK",
                message="查询成功",
                data=adapter.dump_python(validated, mode="json"),
            )
        except ValidationError:
            logger.warning("工具返回数据不符合约定", exc_info=True)
            return ToolResult[Any](
                success=False,
                code=ToolFailureCode.INVALID_TOOL_RESULT,
                message="业务工具返回的数据不符合约定",
                failure_type=ToolFailureType.CONTRACT,
            )

    @staticmethod
    async def _save(
        runtime_context: AgentRuntimeContext,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        tool_result: ToolResult[Any],
        duration_ms: int,
    ) -> None:
        async with SessionFactory() as session:
            repository = ToolCallRepository(session)
            run_pk = UUID(runtime_context.run_pk)
            seq = await repository.next_seq(run_pk)
            repository.add(
                AgentToolCall(
                    run_pk=run_pk,
                    tenant_id=UUID(runtime_context.tenant_id),
                    seq=seq,
                    tool_name=tool_name,
                    arguments=arguments,
                    result=tool_result.model_dump(mode="json"),
                    status="ok" if tool_result.success else "error",
                    error=None if tool_result.success else tool_result.message,
                    duration_ms=duration_ms,
                )
            )
            await session.commit()
