"""转人工意图识别测试。

识别由 fast 模型完成，这里用假模型验证路由逻辑，不依赖真实大模型。
"""

from __future__ import annotations

from uuid import uuid4

from edu_ai.agent.coordinator import AgentRunCoordinator
from edu_ai.agent.handoff_router import HandoffIntent, HandoffRouter
from edu_ai.agent.output import HandoffReason, ReplyType
from edu_ai.schemas.run import AgentRunRequest


class FakeStructuredModel:
    def __init__(self, result: object):
        self.result = result
        self.calls: list[object] = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request(*texts: str, history: list[dict] | None = None) -> AgentRunRequest:
    return AgentRunRequest(
        request_id=f"req-{uuid4().hex}",
        tenant_id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        turn_id=uuid4(),
        input_revision=1,
        messages=[
            {
                "message_id": f"m{index}",
                "role": "customer",
                "type": "text",
                "content": {"text": text},
            }
            for index, text in enumerate(texts, start=1)
        ],
        history=history or [],
    )


async def test_router_returns_intent_when_model_says_handoff() -> None:
    model = FakeStructuredModel(
        HandoffIntent(
            needs_human=True,
            reason_code=HandoffReason.USER_REQUESTED,
            summary="用户要求转人工客服。",
        )
    )
    router = HandoffRouter(model_factory=lambda: model)

    intent = await router.detect(_request("给我接个人吧"))

    assert intent is not None
    assert intent.reason_code == HandoffReason.USER_REQUESTED
    assert model.calls, "应调用轻量模型做识别"


async def test_router_ignores_normal_question() -> None:
    model = FakeStructuredModel(HandoffIntent(needs_human=False))
    router = HandoffRouter(model_factory=lambda: model)

    assert await router.detect(_request("屏幕闪烁怎么办")) is None


async def test_router_falls_back_when_model_fails() -> None:
    model = FakeStructuredModel(RuntimeError("gateway down"))
    router = HandoffRouter(model_factory=lambda: model)

    assert await router.detect(_request("我要转人工")) is None


async def test_router_passes_recent_history_for_context() -> None:
    model = FakeStructuredModel(HandoffIntent(needs_human=True))
    router = HandoffRouter(model_factory=lambda: model)

    await router.detect(
        _request(
            "那转人工吧",
            history=[
                {
                    "message_id": "h1",
                    "role": "customer",
                    "type": "text",
                    "content": {"text": "屏幕闪烁，修了两次还是不行"},
                },
                {
                    "message_id": "h2",
                    "role": "ai",
                    "type": "text",
                    "content": {"text": "建议再观察一下"},
                },
            ],
        )
    )

    user_prompt = str(model.calls[0][1].content)
    assert "修了两次还是不行" in user_prompt
    assert "那转人工吧" in user_prompt


def test_handoff_output_maps_reason_and_summary() -> None:
    output = AgentRunCoordinator._handoff_output(
        HandoffIntent(
            needs_human=True,
            reason_code=HandoffReason.COMPLAINT,
            summary="用户投诉多次维修未解决，要求升级处理。",
        )
    )

    assert output.reply_type == ReplyType.REQUEST_HANDOFF
    assert output.handoff_request is not None
    assert output.handoff_request.reason_code == HandoffReason.COMPLAINT
    assert output.handoff_request.summary == "用户投诉多次维修未解决，要求升级处理。"


def test_handoff_output_uses_default_summary() -> None:
    output = AgentRunCoordinator._handoff_output(
        HandoffIntent(needs_human=True, summary="")
    )

    assert output.handoff_request is not None
    assert output.handoff_request.summary == "用户明确要求转人工客服。"


def test_tool_limit_still_falls_back_to_decline() -> None:
    from edu_ai.agent.executor import AgentExecutor

    assert AgentExecutor._tool_limit_output().reply_type == ReplyType.DECLINE
