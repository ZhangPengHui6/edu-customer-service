"""客户消息接收与历史查询。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import Conversation, Message
from edu_cs.repositories.conversations import ConversationRepository
from edu_cs.repositories.messages import MessageRepository
from edu_cs.repositories.turns import TurnRepository
from edu_cs.schemas.chat import ChatMessageRequest
from edu_cs.security import Principal
from edu_cs.services.realtime import RealtimeOutboxService, message_payload
from edu_cs.services.turns import TurnService


class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversation_repository = ConversationRepository(session)
        self.message_repository = MessageRepository(session)
        self.turn_repository = TurnRepository(session)
        self.outbox = RealtimeOutboxService(session)
        self.turn_service = TurnService(session)

    async def accept_customer_message(
        self,
        principal: Principal,
        conversation_id: UUID,
        payload: ChatMessageRequest,
    ) -> dict:
        duplicate = await self.message_repository.find_by_message_id(payload.message_id)
        if duplicate is not None:
            message, conversation = duplicate
            if conversation.id != conversation_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="message_id 已属于其他会话",
                )
            is_processing = await self.turn_repository.is_processing(conversation.id)
            return self._response(conversation, message, is_processing=is_processing)

        conversation = await self.conversation_repository.get_for_update(conversation_id)
        if (
            conversation is None
            or conversation.tenant_id != principal.tenant_id
            or conversation.user_id != principal.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        if conversation.mode == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="会话已关闭，请重新发起会话",
            )

        message = Message(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            message_id=payload.message_id,
            role="customer",
            message_type=payload.type,
            content=payload.content,
        )
        self.message_repository.add(message)
        await self.session.flush()

        if conversation.mode == "AI":
            await self.turn_service.add_message_to_turn(conversation, message)
        else:
            # QUEUED / HUMAN / REPAIR：AI 不再自动回复，消息直接推给客服端。
            conversation.last_active_at = datetime.now(UTC)
            self.outbox.add_message_created(
                conversation, message, notify_user=False, notify_staff=True
            )

        await self.session.commit()
        await self.session.refresh(message)
        await self.session.refresh(conversation)
        is_processing = await self.turn_repository.is_processing(conversation.id)
        return self._response(conversation, message, is_processing=is_processing)

    async def save_staff_message(
        self,
        conversation: Conversation,
        *,
        client_message_id: UUID,
        text: str,
        operator_id: UUID,
    ) -> Message:
        duplicate = await self.message_repository.find_by_message_id(client_message_id)
        if duplicate is not None:
            message, existing_conversation = duplicate
            if existing_conversation.id != conversation.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="message_id 已属于其他会话",
                )
            return message

        message = Message(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            message_id=client_message_id,
            role="agent",
            message_type="text",
            content={"text": text},
        )
        self.message_repository.add(message)
        conversation.last_active_at = datetime.now(UTC)
        await self.session.flush()
        self.outbox.add_message_created(
            conversation, message, notify_user=True, notify_staff=False
        )
        return message

    async def list_messages(
        self,
        principal: Principal,
        conversation_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 50,
    ) -> dict:
        conversation = await self.conversation_repository.get(conversation_id)
        allowed = conversation is not None and (
            conversation.user_id == principal.user_id
            or (
                conversation.tenant_id == principal.tenant_id
                and principal.role in ("agent", "admin")
            )
            or principal.is_hq_admin
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )

        messages = await self.message_repository.list_after(
            conversation.id, after_sequence, min(limit, 200)
        )
        return {
            "messages": [message_payload(message) for message in messages],
            "next_after_sequence": messages[-1].id if messages else None,
        }

    @staticmethod
    def _response(
        conversation: Conversation, message: Message, *, is_processing: bool
    ) -> dict:
        return {
            "conversation_id": conversation.id,
            "mode": conversation.mode,
            "is_processing": is_processing,
            "message": message_payload(message),
            "input_revision": message.input_revision,
        }
