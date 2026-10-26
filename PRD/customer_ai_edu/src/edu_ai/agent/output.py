"""结构化输出：模型必须返回的回复格式。"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplyType(StrEnum):
    ANSWER = "ANSWER"
    CLARIFY = "CLARIFY"
    DECLINE = "DECLINE"
    REQUEST_HANDOFF = "REQUEST_HANDOFF"


class HandoffReason(StrEnum):
    USER_REQUESTED = "USER_REQUESTED"
    COMPLAINT = "COMPLAINT"
    RISK_REVIEW = "RISK_REVIEW"


PRIORITY_BY_REASON = {
    HandoffReason.USER_REQUESTED: "P2",
    HandoffReason.COMPLAINT: "P1",
    HandoffReason.RISK_REVIEW: "P0",
}


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: HandoffReason = Field(description="转人工原因")
    summary: str = Field(
        min_length=1,
        max_length=500,
        description="给人工客服的问题摘要，包含设备 SN、订单号等已知信息",
    )


class AgentOutput(BaseModel):
    """模型每轮的最终结构化回复。"""

    reply_type: ReplyType = Field(description="本轮回复类型")
    reply_content: str = Field(
        min_length=1,
        max_length=4000,
        description="可以直接展示给用户的完整回复",
    )
    handoff_request: HandoffRequest | None = Field(
        default=None,
        description="仅 REQUEST_HANDOFF 时提供",
    )

    @model_validator(mode="after")
    def validate_handoff(self) -> Self:
        is_handoff = self.reply_type == ReplyType.REQUEST_HANDOFF
        if is_handoff and self.handoff_request is None:
            raise ValueError("REQUEST_HANDOFF 必须提供 handoff_request")
        if not is_handoff and self.handoff_request is not None:
            raise ValueError("只有 REQUEST_HANDOFF 可以提供 handoff_request")
        return self
