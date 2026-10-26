"""结构化输出与业务事实校验的单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from edu_ai.agent.errors import AgentOutputValidationError, CorrectableErrorCode
from edu_ai.agent.output import AgentOutput, HandoffReason, ReplyType
from edu_ai.agent.tools.result import ToolFailureType
from edu_ai.agent.tools.snapshot import ToolCallSnapshot
from edu_ai.agent.validators.facts import FactCategory, FactChecker
from edu_ai.agent.validators.output import AnswerValidator

ORDER_NO = "ORDER_20251001"


def _answer(text: str) -> AgentOutput:
    return AgentOutput(reply_type=ReplyType.ANSWER, reply_content=text)


def _snapshot(
    data: dict[str, Any] | None,
    *,
    success: bool = True,
    failure_type: ToolFailureType | None = None,
    tool_name: str = "get_order",
    arguments: dict[str, Any] | None = None,
) -> ToolCallSnapshot:
    return ToolCallSnapshot(
        tool_name=tool_name,
        arguments=arguments or {"order_no": ORDER_NO},
        result={
            "success": success,
            "message": (data or {}).get("message"),
            "failure_type": failure_type.value if failure_type else None,
            "data": data,
        },
        success=success,
        failure_type=failure_type,
    )


def test_handoff_requires_request() -> None:
    with pytest.raises(ValueError):
        AgentOutput(reply_type=ReplyType.REQUEST_HANDOFF, reply_content="转人工")


def test_handoff_forbidden_for_answer() -> None:
    with pytest.raises(ValueError):
        AgentOutput(
            reply_type=ReplyType.ANSWER,
            reply_content="好的",
            handoff_request={"reason_code": "COMPLAINT", "summary": "投诉"},
        )


def test_handoff_reason_is_parsed() -> None:
    output = AgentOutput(
        reply_type=ReplyType.REQUEST_HANDOFF,
        reply_content="正在转接",
        handoff_request={"reason_code": "COMPLAINT", "summary": "连续三次故障"},
    )
    assert output.handoff_request is not None
    assert output.handoff_request.reason_code is HandoffReason.COMPLAINT


def test_failed_business_calls_fall_back_to_decline() -> None:
    snapshots = (
        _snapshot(
            {"message": "客服服务超时"},
            success=False,
            failure_type=ToolFailureType.SERVICE_CALL,
        ),
    )
    result = AnswerValidator().validate(_answer("订单已在运输中"), snapshots)
    assert result.reply_type is ReplyType.DECLINE


def test_all_business_rejections_use_latest_message() -> None:
    snapshots = (
        _snapshot(
            {"message": "订单不存在"},
            success=False,
            failure_type=ToolFailureType.BUSINESS,
        ),
    )
    result = AnswerValidator().validate(_answer("订单在运输中"), snapshots)
    assert result.reply_type is ReplyType.ANSWER
    assert result.reply_content == "订单不存在"


def test_unsupported_status_is_rejected() -> None:
    snapshots = (
        _snapshot(
            {
                "order_no": ORDER_NO,
                "status": "paid",
                "status_label": "已付款",
                "total_amount": "299.00",
            }
        ),
    )
    with pytest.raises(AgentOutputValidationError) as error:
        AnswerValidator().validate(
            _answer(f"订单 {ORDER_NO} 已发货，金额 299 元"), snapshots
        )
    assert error.value.code is CorrectableErrorCode.UNSUPPORTED_FACT


def test_supported_facts_pass() -> None:
    snapshots = (
        _snapshot(
            {
                "order_no": ORDER_NO,
                "status": "shipped",
                "status_label": "已发货",
                "total_amount": "299.00",
            }
        ),
    )
    validated = AnswerValidator().validate(
        _answer(f"订单 {ORDER_NO} 已发货，金额 299 元"), snapshots
    )
    assert validated.reply_content.startswith("订单")


def test_fact_checker_requires_identifier_source() -> None:
    unsupported = FactChecker().get_unsupported_facts(
        "订单 ORDER_99999999 已经受理", ()
    )
    assert {fact.category for fact in unsupported} == {FactCategory.IDENTIFIER}
