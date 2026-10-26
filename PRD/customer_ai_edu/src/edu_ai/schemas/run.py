"""内部 Agent 运行接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MessageType = Literal["text", "image", "object"]


class CurrentMessage(BaseModel):
    message_id: str
    role: Literal["customer", "ai", "agent", "system"] = "customer"
    type: MessageType = "text"
    content: dict[str, Any]


class HistoryMessage(CurrentMessage):
    created_at: datetime | None = None


class AgentRunRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    tenant_id: UUID
    user_id: UUID
    conversation_id: UUID
    turn_id: UUID
    input_revision: int = Field(ge=1)
    channel: str = "app"
    subject_type: str = "parent"
    context: dict[str, Any] = Field(default_factory=dict)
    messages: list[CurrentMessage] = Field(min_length=1)
    history: list[HistoryMessage] = Field(default_factory=list)


class ConfirmRunRequest(BaseModel):
    input_revision: int | None = Field(default=None, ge=1)


class RunSummary(BaseModel):
    run_id: str
    request_id: str
    tenant_id: UUID
    conversation_id: UUID
    turn_id: UUID
    status: str
    intent: str | None = None
    skill_code: str | None = None
    input_revision: int
    output: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
