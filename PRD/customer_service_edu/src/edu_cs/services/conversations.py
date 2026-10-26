"""会话生命周期与访问控制。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.config import get_settings
from edu_cs.models import Conversation
from edu_cs.repositories.conversations import ConversationRepository
from edu_cs.repositories.messages import MessageRepository
from edu_cs.repositories.turns import TurnRepository
from edu_cs.security import Principal
from edu_cs.services.realtime import RealtimeOutboxService


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.repository = ConversationRepository(session)
        self.turn_repository = TurnRepository(session)
        self.message_repository = MessageRepository(session)
        self.outbox = RealtimeOutboxService(session)

    async def ensure_open(self, principal: Principal, channel: str = "app") -> Conversation:
        """返回当前打开会话；空闲超时的会话先关闭再新建。"""
        await self._close_idle(principal, channel)

        conversation = await self.repository.find_open(
            principal.tenant_id, principal.user_id, channel
        )
        if conversation is not None:
            return conversation

        conversation = Conversation(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            channel=channel,
            mode="AI",
            subject_type="parent",
            input_revision=0,
            answered_revision=0,
        )
        try:
            return await self.repository.add(conversation)
        except IntegrityError:
            # 并发首条消息时另一个请求已经创建，回滚后复用。
            await self.session.rollback()
            existing = await self.repository.find_open(
                principal.tenant_id, principal.user_id, channel
            )
            if existing is None:
                raise
            return existing

    async def _close_idle(self, principal: Principal, channel: str) -> None:
        conversation = await self.repository.find_open(
            principal.tenant_id, principal.user_id, channel
        )
        if conversation is None:
            return
        if await self.turn_repository.is_processing(conversation.id):
            return
        idle_deadline = datetime.now(UTC) - timedelta(
            minutes=self.settings.conversation_idle_minutes
        )
        if conversation.last_active_at > idle_deadline:
            return
        self.repository.close(conversation, "idle_timeout")
        self.outbox.add_mode_changed(conversation)
        await self.session.flush()

    async def get_for_customer(
        self,
        principal: Principal,
        conversation_id: UUID,
        *,
        for_update: bool = False,
    ) -> Conversation:
        conversation = (
            await self.repository.get_for_update(conversation_id)
            if for_update
            else await self.repository.get(conversation_id)
        )
        if (
            conversation is None
            or conversation.tenant_id != principal.tenant_id
            or conversation.user_id != principal.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        return conversation

    async def get_for_staff(
        self,
        principal: Principal,
        tenant_id: UUID,
        conversation_id: UUID,
        *,
        for_update: bool = False,
    ) -> Conversation:
        conversation = (
            await self.repository.get_for_update(conversation_id)
            if for_update
            else await self.repository.get(conversation_id)
        )
        if conversation is None or conversation.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        return conversation

    async def get_for_access(
        self, principal: Principal, conversation_id: UUID
    ) -> Conversation:
        """客户或同租户客服均可读取（客户只能读自己的）。"""
        conversation = await self.repository.get(conversation_id)
        allowed = conversation is not None and (
            conversation.user_id == principal.user_id
            or conversation.tenant_id == principal.tenant_id
            and principal.role in ("agent", "admin")
            or principal.is_hq_admin
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        return conversation

    async def detail(self, principal: Principal, conversation_id: UUID) -> dict:
        conversation = await self.get_for_access(principal, conversation_id)
        messages = await self.message_repository.latest_for_conversation(
            conversation.id, limit=50
        )
        is_processing = await self.turn_repository.is_processing(conversation.id)
        return {
            "id": conversation.id,
            "mode": conversation.mode,
            "is_processing": is_processing,
            "channel": conversation.channel,
            "started_at": conversation.started_at,
            "last_active_at": conversation.last_active_at,
            "messages": [
                {
                    "sequence": message.id,
                    "message_id": message.message_id,
                    "conversation_id": message.conversation_id,
                    "role": message.role,
                    "type": message.message_type,
                    "content": message.content,
                    "created_at": message.created_at,
                }
                for message in messages
            ],
        }
