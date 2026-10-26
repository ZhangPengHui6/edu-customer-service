"""从数据库读取工具调用快照，供输出校验使用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from edu_ai.agent.tools.result import ToolFailureType
from edu_ai.models import AgentToolCall
from edu_ai.repositories.tool import ToolCallRepository


@dataclass(frozen=True)
class ToolCallSnapshot:
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    success: bool | None
    failure_type: ToolFailureType | None = None

    @classmethod
    def from_tool_call(cls, tool_call: AgentToolCall) -> ToolCallSnapshot:
        result = dict(tool_call.result) if tool_call.result is not None else None
        failure_type = None
        if result is not None and result.get("failure_type"):
            failure_type = ToolFailureType(result["failure_type"])
        return cls(
            tool_name=tool_call.tool_name,
            arguments=dict(tool_call.arguments),
            result=result,
            success=bool(result.get("success")) if result is not None else None,
            failure_type=failure_type,
        )


class ToolCallReader:
    def __init__(self, repository: ToolCallRepository):
        self.repository = repository

    async def read_by_run_pk(
        self, run_pk: UUID | str
    ) -> tuple[ToolCallSnapshot, ...]:
        calls = await self.repository.list_by_run(UUID(str(run_pk)))
        return tuple(ToolCallSnapshot.from_tool_call(call) for call in calls)
