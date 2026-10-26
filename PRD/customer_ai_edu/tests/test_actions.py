"""写操作幂等键测试。"""

from __future__ import annotations

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.services.actions import CANCEL_ACTION, REPAIR_ACTION, _idempotency_key


def _context(turn_id: str = "turn-1") -> AgentRuntimeContext:
    return AgentRuntimeContext(
        run_id="run-1",
        run_pk="pk-1",
        tenant_id="tenant-1",
        user_id="user-1",
        conversation_id="conv-1",
        turn_id=turn_id,
    )


def test_key_is_stable_within_turn() -> None:
    first = _idempotency_key(_context(), REPAIR_ACTION, "SNX5000001")
    second = _idempotency_key(_context(), REPAIR_ACTION, "SNX5000001")
    assert first == second
    assert len(first) == 64


def test_key_depends_on_action_and_resource() -> None:
    context = _context()
    keys = {
        _idempotency_key(context, REPAIR_ACTION, "SNX5000001"),
        _idempotency_key(context, CANCEL_ACTION, "ORDER_20251001"),
        _idempotency_key(context, REPAIR_ACTION, "SNX5000002"),
        _idempotency_key(_context("turn-2"), REPAIR_ACTION, "SNX5000001"),
    }
    assert len(keys) == 4
