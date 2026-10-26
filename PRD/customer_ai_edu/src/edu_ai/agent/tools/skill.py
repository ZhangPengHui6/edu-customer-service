"""技能加载工具。"""

from __future__ import annotations

from typing import Annotated

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from edu_ai.agent.runtime import AgentExecutionState, AgentRuntimeContext
from edu_ai.agent.skills.catalog import SKILL_CATALOG
from edu_ai.agent.skills.definition import SkillCode, SkillDefinition
from edu_ai.agent.tools.result import ToolResult


@tool
async def load_skill(
    skill_code: Annotated[SkillCode, "与用户问题最匹配的售后技能编码"],
    runtime: ToolRuntime[AgentRuntimeContext, AgentExecutionState],
) -> Command:
    """加载售后领域技能，加载后才会开放该领域的业务工具。"""
    skill = SKILL_CATALOG.get_skill(skill_code)
    result_json = ToolResult[SkillDefinition](
        success=True,
        code="SKILL_LOADED",
        message="技能已加载",
        data=skill,
    ).model_dump_json()

    return Command(
        update={
            "active_skill_code": skill_code,
            "messages": [
                ToolMessage(
                    content=result_json,
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )
