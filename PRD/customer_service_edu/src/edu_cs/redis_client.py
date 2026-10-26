"""Redis 客户端（同步用于健康检查，异步用于投递与订阅）。"""

from functools import lru_cache

import redis
import redis.asyncio as redis_async

from edu_cs.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def get_async_redis() -> redis_async.Redis:
    return redis_async.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
        health_check_interval=30,
    )
