"""上下文编译测试。"""

from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage

from edu_ai.agent.context import ContextCompiler
from edu_ai.config import Settings
from edu_ai.schemas.run import AgentRunRequest, CurrentMessage, HistoryMessage


def _request(
    messages: list[CurrentMessage],
    history: list[HistoryMessage] | None = None,
) -> AgentRunRequest:
    return AgentRunRequest(
        request_id="req-1",
        tenant_id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        turn_id=uuid4(),
        input_revision=1,
        messages=messages,
        history=history or [],
    )


def _text_message(text: str, *, role: str = "customer") -> CurrentMessage:
    return CurrentMessage(message_id="m", role=role, type="text", content={"text": text})


def test_single_text_message() -> None:
    request = _request([_text_message("订单到哪了")])
    messages = ContextCompiler().compile_messages(request)
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "订单到哪了"


def test_multiple_current_messages_are_grouped() -> None:
    request = _request([_text_message("订单到哪了"), _text_message("订单号 ORDER_20251001")])
    messages = ContextCompiler().compile_messages(request)
    assert isinstance(messages[0], HumanMessage)
    content = messages[0].content
    assert isinstance(content, str)
    assert "用户连续输入了多条消息" in content
    assert "1. 订单到哪了" in content
    assert "2. 订单号 ORDER_20251001" in content


def test_image_message_becomes_multimodal() -> None:
    request = _request(
        [
            CurrentMessage(
                message_id="m1",
                role="customer",
                type="image",
                content={"url": "https://cdn.example.com/a.jpg"},
            ),
            _text_message("屏幕变成这样了"),
        ]
    )
    content = ContextCompiler().compile_messages(request)[0].content
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example.com/a.jpg"},
    }
    assert ContextCompiler.has_images(request)


def test_history_is_trimmed_to_customer_start() -> None:
    compiler = ContextCompiler()
    compiler.settings = Settings(history_message_limit=20, history_character_budget=6000)
    request = _request(
        [_text_message("现在的问题")],
        history=[
            HistoryMessage(
                message_id="h1", role="ai", type="text", content={"text": "早上好"}
            ),
            HistoryMessage(
                message_id="h2", role="customer", type="text", content={"text": "你好"}
            ),
            HistoryMessage(
                message_id="h3", role="ai", type="text", content={"text": "请问有什么可以帮您"}
            ),
        ],
    )
    messages = compiler.compile_messages(request)
    assert [type(message) for message in messages] == [HumanMessage, AIMessage, HumanMessage]
    assert messages[0].content == "你好"
    assert messages[1].content == "请问有什么可以帮您"


def test_history_budget_limits_messages() -> None:
    compiler = ContextCompiler()
    compiler.settings = Settings(history_message_limit=20, history_character_budget=8)
    request = _request(
        [_text_message("当前")],
        history=[
            HistoryMessage(
                message_id="h1",
                role="customer",
                type="text",
                content={"text": "一二三四五六"},
            ),
            HistoryMessage(
                message_id="h2", role="ai", type="text", content={"text": "七八九十"}
            ),
        ],
    )
    messages = compiler.compile_messages(request)
    # 超预算的最旧消息被丢弃，剩下的 AI 消息缺少对应客户消息，也一并丢弃。
    assert len(messages) == 1
    assert messages[0].content == "当前"
