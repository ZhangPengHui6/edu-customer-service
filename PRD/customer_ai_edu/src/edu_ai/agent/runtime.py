"""单次 Agent 运行的运行时上下文与图状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, NotRequired

from langchain.agents import AgentState

from edu_ai.agent.output import AgentOutput
from edu_ai.agent.skills.definition import SkillCode


@dataclass(frozen=True)
class AgentRuntimeContext:
    """提供给工具的单次运行身份；工具不得从模型参数接收租户或用户。"""

    run_id: str
    run_pk: str
    tenant_id: str
    user_id: str
    conversation_id: str
    turn_id: str
    customer_texts: tuple[str, ...] = ()


def _last_skill(
    left: SkillCode | None, right: SkillCode | None
) -> SkillCode | None:
    """模型可能在一轮里同时加载多个技能，用最后一个，避免并发写状态报错。"""
    return right if right is not None else left


class AgentExecutionState(AgentState[AgentOutput]):  # type: ignore[misc]
    active_skill_code: NotRequired[Annotated[SkillCode, _last_skill]]
