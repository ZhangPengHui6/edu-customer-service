"""创建共享 Agent。"""

from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy

from edu_ai.agent.dynamic_prompt import support_prompt
from edu_ai.agent.llm import ModelAdapter
from edu_ai.agent.output import AgentOutput
from edu_ai.agent.runtime import AgentExecutionState, AgentRuntimeContext
from edu_ai.agent.skills.middleware import SkillScopeMiddleware
from edu_ai.agent.tools.catalog import TOOL_CATALOG
from edu_ai.config import get_settings


@lru_cache(maxsize=2)
def _build_agent(vision: bool):
    settings = get_settings()
    return create_agent(
        model=ModelAdapter.create_model(vision=vision),
        tools=TOOL_CATALOG.get_agent_tools(),
        response_format=ToolStrategy(AgentOutput),
        state_schema=AgentExecutionState,
        context_schema=AgentRuntimeContext,
        middleware=[
            support_prompt,
            SkillScopeMiddleware(),
            ToolCallLimitMiddleware(
                run_limit=settings.max_tool_calls,
                exit_behavior="error",
            ),
        ],
        name=settings.agent_name,
    )


def create_support_agent(*, vision: bool = False):
    return _build_agent(vision)
