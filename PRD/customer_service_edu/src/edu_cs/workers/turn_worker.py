"""AI 轮次消费者。

流程：领取轮次 → 调 AI 服务 → 若 AI 准备了写操作，先校验会话快照再确认
→ 在同一个数据库事务里保存回复、工单、会话状态与 Outbox 事件。
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.clients.ai import AIServiceClient, AIServiceError
from edu_cs.config import get_settings
from edu_cs.db import SessionFactory
from edu_cs.models import Conversation, ConversationTurn, Message
from edu_cs.services.ai_events import (
    find_run_id,
    has_prepared_decision,
    parse_outcome,
)
from edu_cs.services.handoffs import HandoffService
from edu_cs.services.realtime import RealtimeOutboxService
from edu_cs.services.turns import TurnService

logger = logging.getLogger(__name__)


class TurnWorker:
    def __init__(self, client: AIServiceClient | None = None):
        self.settings = get_settings()
        self.worker_id = (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:6]}"
        )
        self.client = client or AIServiceClient()

    async def run_forever(self) -> None:
        logger.info("turn worker started: %s", self.worker_id)
        while True:
            try:
                processed = await self.poll_once()
                if not processed:
                    await asyncio.sleep(self.settings.worker_poll_ms / 1000)
            except asyncio.CancelledError:
                logger.info("turn worker stopped: %s", self.worker_id)
                raise
            except Exception:
                logger.exception("turn worker loop failed")
                await asyncio.sleep(1)

    async def poll_once(self) -> bool:
        await self._recover_expired()
        claimed = await self._claim()
        if claimed is None:
            return False
        turn_id, request = claimed
        await self._process(turn_id, request)
        return True

    async def _claim(self) -> tuple[UUID, dict[str, Any]] | None:
        async with SessionFactory() as session:
            service = TurnService(session)
            turn = await service.claim(self.worker_id)
            if turn is None:
                return None
            conversation = await session.get(Conversation, turn.conversation_id)
            if conversation is None:
                return None
            try:
                request, _ = await service.build_ai_request(turn, conversation)
            except Exception as exc:  # noqa: BLE001 - 请求构建失败要回退轮次
                logger.warning("turn %s has no request data: %s", turn.id, exc)
                service.requeue(turn, exc)
                await session.commit()
                return None
            turn_id = turn.id
            await session.commit()
            return turn_id, request

    async def _process(
        self, turn_id: UUID, request: dict[str, Any]
    ) -> None:
        run_id: str | None = None
        outcome: dict[str, Any] | None = None
        error: Exception | None = None
        prepared = False
        action_executed = False

        try:
            event = await self.client.start_run(request)
            run_id = find_run_id(event)
            prepared = has_prepared_decision(event)
            if prepared:
                if not await self._validate_before_commit(turn_id, run_id):
                    await self._safe_cancel(run_id)
                    return
                event = await self.client.confirm_run(
                    run_id, int(request["input_revision"])
                )
                run_id = find_run_id(event)
                action_executed = True
            outcome = parse_outcome(event)
        except Exception as exc:
            error = exc
            logger.exception("turn %s AI pipeline failed", turn_id)
            if prepared and run_id is not None and not action_executed:
                await self._safe_cancel(run_id)

        await self._finalize(
            turn_id,
            run_id=run_id,
            outcome=outcome,
            error=error,
            action_executed=action_executed,
        )

    async def _validate_before_commit(self, turn_id: UUID, run_id: str) -> bool:
        async with SessionFactory() as session:
            service = TurnService(session)
            row = await service.find_turn_and_conversation(turn_id)
            if row is None:
                return False
            turn, conversation = row
            turn.run_id = run_id
            if (
                turn.status != "RUNNING"
                or conversation.mode != "AI"
                or conversation.input_revision != turn.snapshot_revision
            ):
                service.mark_superseded(turn)
                await session.commit()
                return False
            await session.commit()
            return True

    async def _finalize(
        self,
        turn_id: UUID,
        *,
        run_id: str | None,
        outcome: dict[str, Any] | None,
        error: Exception | None,
        action_executed: bool,
    ) -> None:
        async with SessionFactory() as session:
            service = TurnService(session)
            row = await service.find_turn_and_conversation(turn_id)
            if row is None:
                logger.warning("turn %s disappeared before finalize", turn_id)
                return
            turn, conversation = row
            if run_id is not None:
                turn.run_id = run_id

            if turn.status != "RUNNING":
                # 租约回收或其他 worker 已经处理，避免重复写消息。
                await session.commit()
                return

            stale = conversation.input_revision != turn.snapshot_revision
            if stale and not action_executed:
                service.mark_superseded(turn)
                await session.commit()
                return

            if error is not None:
                if service.retry_or_fail(turn, error):
                    await session.commit()
                    return
                message = await self._save_message(
                    session,
                    conversation,
                    turn,
                    role="ai",
                    content={"text": "AI 处理失败，请稍后重试。"},
                    run_id=None,
                )
                RealtimeOutboxService(session).add_message_created(
                    conversation, message, notify_user=True, notify_staff=False
                )
                conversation.answered_revision = max(
                    conversation.answered_revision,
                    turn.snapshot_revision or 0,
                )
                await session.commit()
                return

            if outcome is None:
                error = AIServiceError("AI 未返回结果")
                if service.retry_or_fail(turn, error):
                    await session.commit()
                    return
                message = await self._save_message(
                    session,
                    conversation,
                    turn,
                    role="ai",
                    content={"text": "AI 处理失败，请稍后重试。"},
                    run_id=None,
                )
                RealtimeOutboxService(session).add_message_created(
                    conversation, message, notify_user=True, notify_staff=False
                )
                conversation.answered_revision = max(
                    conversation.answered_revision,
                    turn.snapshot_revision or 0,
                )
                await session.commit()
                return

            service.mark_completed(turn)
            now = datetime.now(UTC)
            conversation.last_active_at = now

            if outcome["outcome_type"] == "handoff":
                handoff = await HandoffService(session).get_or_create_open(
                    conversation,
                    summary=str(outcome["summary"]),
                    priority=str(outcome.get("priority") or "P2"),
                )
                conversation.mode = "QUEUED"
                message = await self._save_message(
                    session,
                    conversation,
                    turn,
                    role="ai",
                    content=outcome["content"],
                    run_id=run_id,
                    message_id=outcome.get("message_id"),
                )
                outbox = RealtimeOutboxService(session)
                outbox.add_message_created(
                    conversation, message, notify_user=True, notify_staff=False
                )
                outbox.add_handoff_changed(conversation, handoff)
                outbox.add_mode_changed(conversation)
            else:
                message = await self._save_message(
                    session,
                    conversation,
                    turn,
                    role="ai",
                    content=outcome["content"],
                    run_id=run_id,
                    message_id=outcome.get("message_id"),
                )
                RealtimeOutboxService(session).add_message_created(
                    conversation, message, notify_user=True, notify_staff=False
                )

            conversation.answered_revision = max(
                conversation.answered_revision,
                turn.snapshot_revision or 0,
            )
            await session.commit()

    @staticmethod
    async def _save_message(
        session: AsyncSession,
        conversation: Conversation,
        turn: ConversationTurn,
        *,
        role: str,
        content: dict[str, Any],
        run_id: str | None,
        message_id: str | None = None,
    ) -> Message:
        try:
            outgoing_id = UUID(message_id) if message_id else uuid4()
        except (TypeError, ValueError):
            outgoing_id = uuid4()
        message = Message(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            message_id=outgoing_id,
            role=role,
            message_type="text",
            content=content,
            agent_run_id=run_id,
            agent_outcome_seq=1 if run_id else None,
        )
        session.add(message)
        # flush 后才有 sequence/created_at，Outbox 事件依赖这两个字段。
        await session.flush()
        await session.refresh(message)
        return message

    async def _safe_cancel(self, run_id: str) -> None:
        try:
            await self.client.cancel_run(run_id)
        except Exception:
            logger.warning("cancel run %s failed", run_id, exc_info=True)

    async def _recover_expired(self) -> None:
        async with SessionFactory() as session:
            service = TurnService(session)
            expired = await service.list_expired_with_conversation()
            if not expired:
                return
            for turn, _ in expired:
                row = await service.find_turn_and_conversation(turn.id)
                if row is None:
                    continue
                locked_turn, conversation = row
                if locked_turn.status != "RUNNING":
                    continue
                if conversation.input_revision != locked_turn.snapshot_revision:
                    service.mark_superseded(locked_turn)
                else:
                    service.requeue(
                        locked_turn, RuntimeError("worker 租约超时")
                    )
            await session.commit()
