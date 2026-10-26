"""AI 服务返回事件的解析测试。"""

from uuid import uuid4

import pytest

from edu_cs.services.ai_events import (
    AIEventError,
    find_run_id,
    has_prepared_decision,
    parse_outcome,
)


def _event(event_type: str, **data) -> dict:
    return {"event_type": event_type, "event_data": data}


def test_find_run_id() -> None:
    assert find_run_id(_event("run_started", run_id="run-1")) == "run-1"
    with pytest.raises(AIEventError):
        find_run_id(_event("run_started"))


def test_prepared_decision_detected() -> None:
    assert has_prepared_decision(_event("run_decision_prepared"))
    assert not has_prepared_decision(_event("run_completed"))


def test_completed_outcome() -> None:
    outcome = parse_outcome(
        _event("run_completed", content={"text": "您的订单已发货"}, message_id=str(uuid4()))
    )
    assert outcome["outcome_type"] == "message"
    assert outcome["content"]["text"] == "您的订单已发货"


def test_handoff_outcome() -> None:
    outcome = parse_outcome(
        _event("run_handoff_requested", summary="设备无法开机", priority="P1")
    )
    assert outcome["outcome_type"] == "handoff"
    assert outcome["summary"] == "设备无法开机"
    assert outcome["priority"] == "P1"


def test_failed_outcome_raises() -> None:
    with pytest.raises(AIEventError):
        parse_outcome(_event("run_failed", message="模型超时"))


def test_completed_without_text_raises() -> None:
    with pytest.raises(AIEventError):
        parse_outcome(_event("run_completed", content={}))
