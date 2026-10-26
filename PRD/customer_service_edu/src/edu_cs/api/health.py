"""健康检查：/health 只探活，/ready 依赖数据库与 Redis。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.config import get_settings
from edu_cs.db import get_session
from edu_cs.redis_client import get_redis

router = APIRouter(tags=["system"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health", summary="存活探针")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready", summary="就绪探针")
async def ready(session: SessionDep) -> JSONResponse:
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - 就绪探针只暴露异常类型
        checks["database"] = f"error:{type(exc).__name__}"

    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error:{type(exc).__name__}"

    ready_now = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if ready_now else 503,
        content={"status": "ready" if ready_now else "degraded", "checks": checks},
    )
