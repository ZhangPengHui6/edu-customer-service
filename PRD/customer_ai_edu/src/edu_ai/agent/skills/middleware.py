"""按当前技能限制模型可见工具。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)

from edu_ai.agent.output import AgentOutput
from edu_ai.agent.runtime import AgentExecutionState, AgentRuntimeContext
from edu_ai.agent.skills.catalog import SKILL_CATALOG


class SkillScopeMiddleware(
    AgentMiddleware[AgentExecutionState, AgentRuntimeContext, AgentOutput]
):
    async def awrap_model_call(
        self,
        request: ModelRequest[AgentRuntimeContext],
        handler: Callable[
            [ModelRequest[AgentRuntimeContext]],
            Awaitable[ModelResponse[AgentOutput]],
        ],
    ) -> ModelResponse[AgentOutput]:
        active_skill_code = request.state.get("active_skill_code")
        if active_skill_code is None:
            allowed_tool_names = {"load_skill"}
        else:
            skill = SKILL_CATALOG.get_skill(active_skill_code)
            allowed_tool_names = {"load_skill", *skill.tools}

        scoped_request = request.override(
            tools=[tool for tool in request.tools if tool.name in allowed_tool_names],
            model_settings={
                **request.model_settings,
                "parallel_tool_calls": False,
            },
        )
        return await handler(scoped_request)
