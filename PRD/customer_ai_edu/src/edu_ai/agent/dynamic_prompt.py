"""按当前技能动态生成系统提示词。"""

from __future__ import annotations

from langchain.agents.middleware import ModelRequest, dynamic_prompt

from edu_ai.agent.prompt import BASE_PROMPT
from edu_ai.agent.skills.catalog import SKILL_CATALOG
from edu_ai.agent.skills.definition import SkillCode


def render_skill_prompt(active_skill_code: SkillCode | None) -> str:
    if active_skill_code is None:
        return (
            "【动态技能路由】\n"
            "先调用 load_skill 加载与用户问题最匹配的售后技能，再使用该技能开放的工具。\n"
            "用户同时询问多个领域时，一次只处理一个技能；完成当前领域后再切换。\n"
            f"可用技能：\n{SKILL_CATALOG.render_index()}"
        )

    skill = SKILL_CATALOG.get_skill(active_skill_code)
    guidance = "\n".join(f"- {item}" for item in skill.guidance)
    return (
        f"【当前技能：{skill.code}】\n"
        f"{guidance}\n"
        "完成当前技能所需的查询和回复后，如果用户切换到其他领域，再调用 load_skill 切换。"
    )


def render_support_prompt(active_skill_code: SkillCode | None) -> str:
    return f"{BASE_PROMPT}\n\n{render_skill_prompt(active_skill_code)}"


@dynamic_prompt
def support_prompt(request: ModelRequest) -> str:
    return render_support_prompt(request.state.get("active_skill_code"))
