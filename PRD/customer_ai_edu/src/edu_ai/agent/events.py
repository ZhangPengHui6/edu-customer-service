"""构建返回给客服服务的事件。"""

from __future__ import annotations

from typing import Any

from edu_ai.agent.errors import RunConflictError
from edu_ai.models import AgentRun


def _build_event(
    run_id: str, event_type: str, event_data: dict[str, Any]
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_data": {"run_id": run_id, **event_data},
    }


def build_response_event(run: AgentRun) -> dict[str, Any]:
    if run.status == "COMPLETED":
        return _build_event(run.run_id, "run_completed", run.output or {})
    if run.status == "HANDED_OFF":
        return _build_event(run.run_id, "run_handoff_requested", run.output or {})
    if run.status == "DECISION_PREPARED":
        return _build_event(run.run_id, "run_decision_prepared", {})
    if run.status == "FAILED":
        return _build_event(run.run_id, "run_failed", run.output or {})
    if run.status == "SUPERSEDED":
        return _build_event(
            run.run_id,
            "run_failed",
            {"code": "RUN_SUPERSEDED", "message": "本次运行已被新消息取代"},
        )
    raise RunConflictError("Agent 运行仍在进行中")
