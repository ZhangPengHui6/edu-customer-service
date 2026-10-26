"""用轻量模型识别转人工意图。

显式转人工不能靠关键词硬匹配：用户会说“给我接个人”“叫真人”“那转人工吧”，
也可能在投诉语境里要求升级。这里先让 fast 模型做一次轻量分类，
命中后直接进入转接流程，避免主 Agent 先查一堆工具再决定。
分类失败时返回 None，交给主 Agent 正常处理，不影响回复。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from edu_ai.agent.llm import ModelAdapter
from edu_ai.agent.output import HandoffReason
from edu_ai.schemas.run import AgentRunRequest

logger = logging.getLogger(__name__)

_ROUTER_PROMPT = """你在做客服会话的意图识别，只判断用户最新的一条消息，不回答用户问题。

判定为需要人工（needs_human=true）的情况：
1. 用户明确要求人工客服、真人、客服专员，例如“转人工”“给我接个人”“叫个真人”。
2. 用户明确要求投诉升级、监管投诉（12315）、媒体曝光，或已经陷入退款争议且拒绝继续自助处理。

判定为不需要人工（needs_human=false）的情况：
1. 普通的订单、物流、设备、保修、维修、政策咨询。
2. 单纯表达不满、催促、抱怨，但没有要求人工或升级处理。
3. 含糊的“怎么办”“然后呢”等需要继续沟通的消息。

reason_code 取值：
- USER_REQUESTED：用户主动要求人工客服。
- COMPLAINT：投诉、要求升级处理。
- RISK_REVIEW：涉及监管、媒体曝光或严重安全风险。

summary 用一句话概括用户要转人工的原因和已知信息（订单号、设备型号、故障现象等），
不超过 200 字，不要编造用户没有提供的信息。"""


class HandoffIntent(BaseModel):
    needs_human: bool = Field(
        description="用户最新消息是否明确要求人工客服或投诉升级"
    )
    reason_code: HandoffReason = Field(
        default=HandoffReason.USER_REQUESTED, description="转人工原因"
    )
    summary: str = Field(
        default="", max_length=400, description="一句话概括转人工原因和已知信息"
    )


class HandoffRouter:
    def __init__(
        self,
        model_factory: Callable[[], object] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._model_factory = model_factory or (
            lambda: ModelAdapter.create_fast_model().with_structured_output(
                HandoffIntent
            )
        )
        self.timeout_seconds = timeout_seconds

    async def detect(self, request: AgentRunRequest) -> HandoffIntent | None:
        transcript = self._render_transcript(request)
        if not transcript:
            return None
        try:
            model = self._model_factory()
            decision = await asyncio.wait_for(
                model.ainvoke(  # type: ignore[attr-defined]
                    [
                        SystemMessage(content=_ROUTER_PROMPT),
                        HumanMessage(content=transcript),
                    ]
                ),
                timeout=self.timeout_seconds,
            )
        except Exception:  # noqa: BLE001 - 分类失败不能影响正常对话
            logger.warning("handoff intent detection failed; fall back to agent", exc_info=True)
            return None

        if isinstance(decision, dict):
            try:
                decision = HandoffIntent.model_validate(decision)
            except ValidationError:
                logger.warning("handoff intent payload invalid: %s", decision)
                return None
        if not isinstance(decision, HandoffIntent) or not decision.needs_human:
            return None
        return decision

    @staticmethod
    def _render_transcript(request: AgentRunRequest) -> str:
        """带上最近几条上下文，便于理解“那转人工吧”这类省略表达。"""
        lines: list[str] = []
        for message in request.history[-4:]:
            text = str(message.content.get("text", "")).strip()
            if text and message.type == "text":
                speaker = "用户" if message.role == "customer" else "客服"
                lines.append(f"{speaker}：{text[:300]}")
        for message in request.messages:
            text = str(message.content.get("text", "")).strip()
            if text and message.type == "text":
                speaker = "用户" if message.role == "customer" else "客服"
                lines.append(f"{speaker}：{text[:300]}")
        if not lines:
            return ""
        return "最近对话：\n" + "\n".join(lines[-8:]) + "\n\n请判断，并在 summary 中引用用户最新一条消息的关键信息。"
