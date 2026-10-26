"""WebSocket 实时推送：订阅 Redis Pub/Sub 并转发给客户端。"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from edu_cs.redis_client import get_async_redis
from edu_cs.security import Principal, TokenError, decode_access_token
from edu_cs.services.realtime import staff_channel, user_channel

router = APIRouter(tags=["realtime"])

HEARTBEAT_SECONDS = 25.0


def _channels(principal: Principal) -> list[str]:
    channels = [user_channel(principal.user_id)]
    if principal.role in ("agent", "admin"):
        channels.append(staff_channel(principal.tenant_id))
    return channels


async def _pump_events(websocket: WebSocket, pubsub) -> None:
    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        await websocket.send_text(message["data"])


async def _pump_heartbeat(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await websocket.send_json({"event_type": "ping"})


async def _guard_disconnect(websocket: WebSocket) -> None:
    while True:
        await websocket.receive_text()


@router.websocket("/api/v1/realtime")
async def realtime(websocket: WebSocket, token: str | None = None) -> None:
    await websocket.accept()
    if not token:
        await websocket.close(code=4401, reason="缺少访问令牌")
        return
    try:
        principal = decode_access_token(token)
    except TokenError:
        await websocket.close(code=4401, reason="访问令牌无效")
        return

    redis = get_async_redis()
    pubsub = redis.pubsub()
    channels = _channels(principal)
    try:
        await pubsub.subscribe(*channels)
    except Exception:  # noqa: BLE001 - 订阅失败统一关闭连接
        await pubsub.aclose()
        await websocket.close(code=1011, reason="实时通道暂不可用")
        return

    await websocket.send_json(
        {
            "event_type": "ready",
            "user_id": str(principal.user_id),
            "channels": channels,
        }
    )

    tasks = [
        asyncio.create_task(_pump_events(websocket, pubsub)),
        asyncio.create_task(_pump_heartbeat(websocket)),
        asyncio.create_task(_guard_disconnect(websocket)),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(
                exc, (WebSocketDisconnect, asyncio.CancelledError)
            ):
                raise exc
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(*channels)
        with contextlib.suppress(Exception):
            await pubsub.aclose()
        with contextlib.suppress(Exception):
            await websocket.close()
