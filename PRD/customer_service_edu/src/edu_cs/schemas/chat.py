"""会话与消息接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

MessageType = Literal["text", "image", "object"]
ConversationMode = Literal["AI", "QUEUED", "HUMAN", "REPAIR", "CLOSED"]


class ChatMessageRequest(BaseModel):
    """客户发送的一条消息。

    message_id 由客户端生成，是接口幂等键；重试时必须复用同一个值。
    """

    message_id: UUID
    type: MessageType = "text"
    content: dict[str, Any]

    @model_validator(mode="after")
    def validate_content(self) -> ChatMessageRequest:
        if self.type == "text":
            text = self.content.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("文本消息必须提供非空的 content.text")
            if len(text) > 4000:
                raise ValueError("单条文本消息不能超过 4000 字")
        elif self.type == "image":
            url = self.content.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("图片消息必须提供 http(s) 的 content.url")
        else:
            if not isinstance(self.content.get("object_type"), str):
                raise ValueError("对象消息必须提供 content.object_type")
        return self


class MessagePayload(BaseModel):
    sequence: int
    message_id: UUID
    conversation_id: UUID
    role: Literal["customer", "ai", "agent", "system"]
    type: MessageType
    content: dict[str, Any]
    created_at: datetime


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    mode: ConversationMode
    is_processing: bool
    message: MessagePayload
    input_revision: int | None = None


class ConversationResponse(BaseModel):
    id: UUID
    mode: ConversationMode
    is_processing: bool
    channel: str
    started_at: datetime
    last_active_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessagePayload]


class MessageListResponse(BaseModel):
    messages: list[MessagePayload]
    next_after_sequence: int | None = None
