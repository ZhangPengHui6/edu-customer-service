"""转人工工单。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.config import get_settings
from edu_cs.models import Conversation, Handoff, HandoffEvent, User
from edu_cs.repositories.catalog import CatalogRepository
from edu_cs.repositories.conversations import ConversationRepository
from edu_cs.security import Principal
from edu_cs.services.realtime import RealtimeOutboxService


class HandoffService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.repository = CatalogRepository(session)
        self.conversation_repository = ConversationRepository(session)
        self.outbox = RealtimeOutboxService(session)

    async def get_or_create_open(
        self,
        conversation: Conversation,
        *,
        summary: str,
        priority: str = "P2",
    ) -> Handoff:
        existing = await self.repository.find_open_handoff(
            conversation.tenant_id, conversation.user_id
        )
        if existing is not None:
            return existing

        handoff = Handoff(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            summary=summary[:2000],
            status="waiting",
            priority=priority if priority in ("P0", "P1", "P2") else "P2",
            skill_group_id=conversation.skill_group_id,
            sla_due_at=datetime.now(UTC)
            + timedelta(seconds=self.settings.handoff_sla_seconds),
        )
        self.repository.add_handoff(handoff)
        await self.session.flush()
        self.repository.add_handoff_event(
            HandoffEvent(
                handoff_id=handoff.id,
                from_status=None,
                to_status="waiting",
                operator_id=None,
                note="AI 请求转人工",
            )
        )
        return handoff

    async def list_for_staff(
        self,
        tenant_id: UUID,
        *,
        statuses: tuple[str, ...] = ("waiting", "active"),
        limit: int = 50,
    ) -> list[dict]:
        handoffs = await self.repository.list_handoffs(
            tenant_id, statuses=statuses, limit=limit
        )
        user_ids = {handoff.user_id for handoff in handoffs}
        users: dict[UUID, User] = {}
        if user_ids:
            rows = await self.session.scalars(
                select(User).where(
                    User.tenant_id == tenant_id, User.id.in_(user_ids)
                )
            )
            users = {user.id: user for user in rows.all()}
        return [
            self.payload(handoff, user=users.get(handoff.user_id))
            for handoff in handoffs
        ]

    async def accept(
        self, principal: Principal, tenant_id: UUID, handoff_id: UUID
    ) -> dict:
        handoff = await self.repository.get_handoff(
            tenant_id, handoff_id, for_update=True
        )
        if handoff is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在"
            )
        conversation = await self.conversation_repository.get_for_update(
            handoff.conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        if handoff.status == "active" and handoff.assigned_agent_id is not None:
            return self._result(handoff, conversation)
        if handoff.status != "waiting":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"工单当前状态为 {handoff.status}，不能接入",
            )

        agent = await self.repository.get_agent_by_user(tenant_id, principal.user_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号未绑定坐席，无法接入会话",
            )

        previous = handoff.status
        handoff.status = "active"
        handoff.assigned_agent_id = agent.id
        handoff.accepted_at = datetime.now(UTC)
        agent.status = "busy"
        conversation.mode = "HUMAN"
        self.repository.add_handoff_event(
            HandoffEvent(
                handoff_id=handoff.id,
                from_status=previous,
                to_status="active",
                operator_id=principal.user_id,
                note="坐席接入",
            )
        )
        self.outbox.add_handoff_changed(conversation, handoff)
        self.outbox.add_mode_changed(conversation)
        await self.session.commit()
        return self._result(handoff, conversation)

    async def resolve(
        self,
        principal: Principal,
        tenant_id: UUID,
        handoff_id: UUID,
        *,
        close_reason: str,
        note: str | None,
    ) -> dict:
        handoff = await self.repository.get_handoff(
            tenant_id, handoff_id, for_update=True
        )
        if handoff is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在"
            )
        conversation = await self.conversation_repository.get_for_update(
            handoff.conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        if handoff.status not in ("waiting", "active"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"工单当前状态为 {handoff.status}，不能结束",
            )

        previous = handoff.status
        now = datetime.now(UTC)
        handoff.status = "resolved"
        handoff.resolved_at = now
        handoff.close_reason = close_reason[:32]
        conversation.mode = "CLOSED"
        conversation.close_reason = close_reason[:32]
        conversation.ended_at = now
        self.repository.add_handoff_event(
            HandoffEvent(
                handoff_id=handoff.id,
                from_status=previous,
                to_status="resolved",
                operator_id=principal.user_id,
                note=note,
            )
        )
        if handoff.assigned_agent_id is not None:
            agent = await self.repository.get_agent_by_user(
                tenant_id, principal.user_id
            )
            if agent is not None:
                agent.status = "online"
        self.outbox.add_handoff_changed(conversation, handoff)
        self.outbox.add_mode_changed(conversation)
        await self.session.commit()
        return self._result(handoff, conversation)

    async def events(self, tenant_id: UUID, handoff_id: UUID) -> list[dict]:
        handoff = await self.repository.get_handoff(tenant_id, handoff_id)
        if handoff is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在"
            )
        events = await self.repository.list_handoff_events(handoff.id)
        return [
            {
                "id": event.id,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "operator_id": event.operator_id,
                "note": event.note,
                "created_at": event.created_at,
            }
            for event in events
        ]

    async def get_or_none(self, tenant_id: UUID, handoff_id: UUID) -> Handoff | None:
        return await self.repository.get_handoff(tenant_id, handoff_id)

    @staticmethod
    def payload(handoff: Handoff, *, user: User | None = None) -> dict:
        return {
            "id": handoff.id,
            "conversation_id": handoff.conversation_id,
            "user_id": handoff.user_id,
            "summary": handoff.summary,
            "status": handoff.status,
            "priority": handoff.priority,
            "assigned_agent_id": handoff.assigned_agent_id,
            "created_at": handoff.created_at,
            "accepted_at": handoff.accepted_at,
            "resolved_at": handoff.resolved_at,
            "sla_due_at": handoff.sla_due_at,
            "customer_name": user.name if user else None,
            "customer_phone_masked": user.phone_masked if user else None,
        }

    @classmethod
    def _result(cls, handoff: Handoff, conversation: Conversation) -> dict:
        return {
            "handoff": cls.payload(handoff),
            "conversation_mode": conversation.mode,
        }
