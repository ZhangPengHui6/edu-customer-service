"""轮次合并、领取与状态流转。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.config import get_settings
from edu_cs.models import Conversation, ConversationTurn, Message
from edu_cs.repositories.messages import MessageRepository
from edu_cs.repositories.turns import TurnRepository


class TurnService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.repository = TurnRepository(session)
        self.message_repository = MessageRepository(session)

    async def add_message_to_turn(
        self, conversation: Conversation, message: Message
    ) -> ConversationTurn:
        """为 AI 会话登记待处理消息。

        合并窗口内复用同一个 COLLECTING 轮次；如果上一轮仍在 RUNNING，
        新建一个 COLLECTING 轮次（两个部分唯一索引允许同时存在）。
        """
        conversation.input_revision += 1
        message.input_revision = conversation.input_revision

        now = datetime.now(UTC)
        merge_delay = timedelta(milliseconds=self.settings.merge_delay_ms)
        turn = await self.repository.find_collecting_for_update(conversation.id)
        if turn is not None:
            turn.collect_until = min(now + merge_delay, turn.max_collect_until)
            await self.session.flush()
            return turn

        max_collect_until = now + timedelta(
            milliseconds=self.settings.max_merge_delay_ms
        )
        turn = ConversationTurn(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            status="COLLECTING",
            start_revision=conversation.input_revision,
            collect_until=now + merge_delay,
            max_collect_until=max_collect_until,
        )
        self.session.add(turn)
        await self.session.flush()
        return turn

    async def claim(self, worker_id: str) -> ConversationTurn | None:
        now = datetime.now(UTC)
        claimed = await self.repository.claim_ready(now)
        if claimed is None:
            return None
        turn, conversation = claimed
        turn.status = "RUNNING"
        turn.snapshot_revision = conversation.input_revision
        turn.locked_by = worker_id
        turn.locked_until = now + timedelta(seconds=self.settings.turn_lease_seconds)
        turn.attempts += 1
        turn.last_error = None
        await self.session.flush()
        return turn

    async def build_ai_request(
        self, turn: ConversationTurn, conversation: Conversation
    ) -> tuple[dict[str, Any], UUID]:
        """构建 AI 请求；调用方需保证 snapshot_revision 已设置。"""
        snapshot_revision = turn.snapshot_revision
        if snapshot_revision is None:
            raise RuntimeError("轮次缺少 snapshot_revision")

        current_messages = await self.message_repository.find_current_range(
            conversation.id, turn.start_revision, snapshot_revision
        )
        if not current_messages:
            raise RuntimeError("轮次没有可处理的客户消息")

        history = await self.message_repository.history_before(
            conversation.id,
            current_messages[0].id,
            self.settings.history_limit,
        )

        request = {
            "request_id": f"{turn.id}:attempt:{turn.attempts}",
            "tenant_id": str(conversation.tenant_id),
            "user_id": str(conversation.user_id),
            "conversation_id": str(conversation.id),
            "turn_id": str(turn.id),
            "input_revision": snapshot_revision,
            "channel": conversation.channel,
            "subject_type": conversation.subject_type,
            "context": conversation.context or {},
            "messages": [
                {
                    "message_id": str(message.message_id),
                    "role": "customer",
                    "type": message.message_type,
                    "content": message.content,
                }
                for message in current_messages
            ],
            "history": [
                {
                    "message_id": str(message.message_id),
                    "role": message.role,
                    "type": message.message_type,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
                for message in history
            ],
        }
        return request, current_messages[-1].message_id

    async def find_turn_and_conversation(
        self, turn_id: UUID
    ) -> tuple[ConversationTurn, Conversation] | None:
        return await self.repository.find_turn_with_conversation(turn_id)

    async def list_expired_with_conversation(
        self,
    ) -> list[tuple[ConversationTurn, Conversation]]:
        turns = await self.repository.list_expired_running(datetime.now(UTC))
        result: list[tuple[ConversationTurn, Conversation]] = []
        for turn in turns:
            conversation = await self.session.get(Conversation, turn.conversation_id)
            if conversation is not None:
                result.append((turn, conversation))
        return result

    @staticmethod
    def mark_superseded(turn: ConversationTurn) -> None:
        turn.status = "SUPERSEDED"
        turn.locked_by = None
        turn.locked_until = None
        turn.last_error = turn.last_error or "输入版本已过期"

    @staticmethod
    def mark_completed(turn: ConversationTurn) -> None:
        turn.status = "COMPLETED"
        turn.locked_by = None
        turn.locked_until = None

    def retry_or_fail(self, turn: ConversationTurn, error: Exception) -> bool:
        turn.last_error = str(error)[:2000]
        turn.locked_by = None
        turn.locked_until = None
        if turn.attempts < self.settings.max_attempts:
            turn.status = "COLLECTING"
            turn.collect_until = datetime.now(UTC) + timedelta(
                seconds=self.settings.retry_delay_seconds
            )
            turn.run_id = None
            return True
        turn.status = "FAILED"
        return False

    @staticmethod
    def requeue(turn: ConversationTurn, error: Exception) -> None:
        turn.status = "COLLECTING"
        turn.collect_until = datetime.now(UTC)
        turn.run_id = None
        turn.last_error = str(error)[:2000]
        turn.locked_by = None
        turn.locked_until = None
