"""客户会话与消息接口。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from edu_cs.api.deps import PrincipalDep, SessionDep, require_roles
from edu_cs.repositories.turns import TurnRepository
from edu_cs.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationDetailResponse,
    ConversationResponse,
    MessageListResponse,
)
from edu_cs.services.conversations import ConversationService
from edu_cs.services.messages import MessageService

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("/current", response_model=ConversationResponse)
async def current_conversation(
    principal: PrincipalDep,
    session: SessionDep,
    channel: Annotated[str, Query(min_length=1, max_length=24)] = "app",
) -> ConversationResponse:
    require_roles(principal, "customer")
    conversation = await ConversationService(session).ensure_open(principal, channel)
    await session.commit()
    is_processing = await TurnRepository(session).is_processing(conversation.id)
    return ConversationResponse(
        id=conversation.id,
        mode=conversation.mode,
        is_processing=is_processing,
        channel=conversation.channel,
        started_at=conversation.started_at,
        last_active_at=conversation.last_active_at,
    )


@router.post("/{conversation_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    conversation_id: UUID,
    payload: ChatMessageRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> ChatMessageResponse:
    require_roles(principal, "customer")
    result = await MessageService(session).accept_customer_message(
        principal, conversation_id, payload
    )
    return ChatMessageResponse(**result)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def conversation_detail(
    conversation_id: UUID,
    principal: PrincipalDep,
    session: SessionDep,
) -> ConversationDetailResponse:
    result = await ConversationService(session).detail(principal, conversation_id)
    return ConversationDetailResponse(**result)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: UUID,
    principal: PrincipalDep,
    session: SessionDep,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessageListResponse:
    result = await MessageService(session).list_messages(
        principal,
        conversation_id,
        after_sequence=after_sequence,
        limit=limit,
    )
    return MessageListResponse(**result)
