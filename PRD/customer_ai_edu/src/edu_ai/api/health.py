"""健康检查：/health 只探活，/ready 检查数据库与 Milvus。"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edu_ai.config import get_settings
from edu_ai.db import get_session

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
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - 就绪探针只暴露异常类型
        checks["database"] = f"error:{type(exc).__name__}"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(settings.milvus_health_url)
        checks["milvus"] = "ok" if response.status_code == 200 else f"http:{response.status_code}"
    except Exception as exc:  # noqa: BLE001
        checks["milvus"] = f"error:{type(exc).__name__}"

    ready_now = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if ready_now else 503,
        content={"status": "ready" if ready_now else "degraded", "checks": checks},
    )
