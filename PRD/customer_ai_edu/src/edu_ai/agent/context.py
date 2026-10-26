"""把客服请求编译成 LangChain 消息。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from edu_ai.config import get_settings
from edu_ai.schemas.run import AgentRunRequest, CurrentMessage, HistoryMessage


class ContextCompiler:
    def __init__(self) -> None:
        self.settings = get_settings()

    def compile_messages(self, request: AgentRunRequest) -> list[BaseMessage]:
        history = self._bounded_history(request.history)
        messages: list[BaseMessage] = []
        for message in history:
            text = self._format_message(message)
            if message.role == "customer":
                messages.append(HumanMessage(content=text))
            elif message.role == "system":
                messages.append(SystemMessage(content=text))
            else:
                messages.append(AIMessage(content=text))

        messages.append(self._build_current_message(request.messages))
        return messages

    def _bounded_history(
        self, history: list[HistoryMessage]
    ) -> list[HistoryMessage]:
        candidates = history[-self.settings.history_message_limit :]
        used = 0
        kept: list[HistoryMessage] = []
        for message in reversed(candidates):
            length = len(self._format_message(message))
            if length + used > self.settings.history_character_budget:
                break
            kept.append(message)
            used += length
        kept.reverse()
        start = next(
            (index for index, message in enumerate(kept) if message.role == "customer"),
            len(kept),
        )
        return kept[start:]

    @staticmethod
    def _format_message(message: CurrentMessage) -> str:
        if message.type == "text":
            return str(message.content.get("text", ""))
        if message.type == "image":
            return f"【用户发送了一张图片】{message.content.get('url', '')}"
        return "【用户发送了一个对象】\n" + json.dumps(
            message.content, ensure_ascii=False
        )

    def _build_current_message(
        self, current_messages: list[CurrentMessage]
    ) -> HumanMessage:
        texts = [self._format_message(message) for message in current_messages]
        if len(texts) == 1:
            combined = texts[0]
        else:
            items = "\n".join(
                f"{index}. {text}" for index, text in enumerate(texts, 1)
            )
            combined = (
                "用户连续输入了多条消息，请作为一个整体理解，并以最新内容为准：\n"
                f"{items}"
            )

        image_urls = self._image_urls(current_messages)
        if not image_urls:
            return HumanMessage(content=combined)

        content: list[dict[str, Any]] = [{"type": "text", "text": combined}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        return HumanMessage(content=content)

    @staticmethod
    def _image_urls(messages: list[CurrentMessage]) -> list[str]:
        urls: list[str] = []
        for message in messages:
            if message.type != "image":
                continue
            url = message.content.get("url")
            if (
                isinstance(url, str)
                and url.startswith(("http://", "https://"))
                and url not in urls
            ):
                urls.append(url)
        return urls

    @staticmethod
    def has_images(request: AgentRunRequest) -> bool:
        return bool(ContextCompiler._image_urls(request.messages))
