"""返回事件映射测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from edu_ai.agent.errors import RunConflictError
from edu_ai.agent.events import build_response_event


def _run(status: str, output: dict | None = None):
    return SimpleNamespace(run_id="run-1", status=status, output=output)


def test_completed_event_carries_message() -> None:
    event = build_response_event(
        _run("COMPLETED", {"message_id": "m1", "content": {"text": "你好"}})
    )
    assert event == {
        "event_type": "run_completed",
        "event_data": {"run_id": "run-1", "message_id": "m1", "content": {"text": "你好"}},
    }


def test_handoff_event_carries_summary() -> None:
    event = build_response_event(
        _run(
            "HANDED_OFF",
            {"reason_code": "COMPLAINT", "summary": "投诉", "priority": "P1", "message": "转人工"},
        )
    )
    assert event["event_type"] == "run_handoff_requested"
    assert event["event_data"]["priority"] == "P1"


def test_prepared_event_has_only_run_id() -> None:
    event = build_response_event(_run("DECISION_PREPARED"))
    assert event == {
        "event_type": "run_decision_prepared",
        "event_data": {"run_id": "run-1"},
    }


def test_superseded_maps_to_failure() -> None:
    event = build_response_event(_run("SUPERSEDED"))
    assert event["event_type"] == "run_failed"
    assert event["event_data"]["code"] == "RUN_SUPERSEDED"


def test_running_run_is_not_returnable() -> None:
    with pytest.raises(RunConflictError):
        build_response_event(_run("RUNNING"))
