"""AI 服务事件解析。"""

from __future__ import annotations

from typing import Any

RUN_COMPLETED = "run_completed"
RUN_HANDOFF_REQUESTED = "run_handoff_requested"
RUN_DECISION_PREPARED = "run_decision_prepared"
RUN_FAILED = "run_failed"


class AIEventError(RuntimeError):
    pass


def find_run_id(event: dict[str, Any]) -> str:
    run_id = event.get("event_data", {}).get("run_id")
    if not run_id:
        raise AIEventError("AI 事件缺少 run_id")
    return str(run_id)


def has_prepared_decision(event: dict[str, Any]) -> bool:
    return event.get("event_type") == RUN_DECISION_PREPARED


def parse_outcome(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("event_type")
    data = event.get("event_data") or {}

    if event_type == RUN_FAILED:
        raise AIEventError(str(data.get("message") or "AI 处理失败"))

    if event_type == RUN_COMPLETED:
        content = data.get("content")
        if not isinstance(content, dict) or not content.get("text"):
            raise AIEventError("AI 完成事件缺少消息内容")
        return {
            "outcome_type": "message",
            "content": content,
            "message_id": data.get("message_id"),
        }

    if event_type == RUN_HANDOFF_REQUESTED:
        return {
            "outcome_type": "handoff",
            "summary": str(data.get("summary") or "用户请求人工客服"),
            "priority": str(data.get("priority") or "P2"),
            "content": {
                "text": str(data.get("message") or "正在为您转接人工客服，请稍候。")
            },
        }

    raise AIEventError(f"AI 事件类型不在约定范围内：{event_type}")
