"""Outbox → Redis Pub/Sub 投递 worker。"""

from __future__ import annotations

import asyncio
import json
import logging

from edu_cs.config import get_settings
from edu_cs.db import SessionFactory
from edu_cs.redis_client import get_async_redis
from edu_cs.repositories.outbox import OutboxRepository
from edu_cs.services.realtime import build_event

logger = logging.getLogger(__name__)


class OutboxPublisher:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run_forever(self) -> None:
        logger.info("outbox publisher started")
        while True:
            try:
                published = await self.publish_once()
                if not published:
                    await asyncio.sleep(self.settings.outbox_poll_seconds)
            except asyncio.CancelledError:
                logger.info("outbox publisher stopped")
                raise
            except Exception:
                logger.exception("outbox publisher loop failed")
                await asyncio.sleep(1)

    async def publish_once(self) -> int:
        async with SessionFactory() as session:
            repository = OutboxRepository(session)
            events = await repository.claim_batch()
            if not events:
                return 0

            redis = get_async_redis()
            for event in events:
                payload = build_event(
                    event.sequence,
                    event.event_type,
                    event.data,
                    event.conversation_id,
                    event.created_at,
                )
                try:
                    await redis.publish(
                        event.channel,
                        json.dumps(payload, ensure_ascii=False, default=str),
                    )
                    repository.mark_published(event)
                except Exception as exc:  # noqa: BLE001 - 单条失败不影响整批
                    logger.warning(
                        "publish outbox %s failed: %s", event.sequence, exc
                    )
                    repository.mark_failed(event, exc)
                    if event.attempts >= self.settings.outbox_max_attempts:
                        repository.dead_letter(event)

            await session.commit()
            return len(events)
