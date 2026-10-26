"""服务入口。"""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from edu_ai.api import health, internal
from edu_ai.config import get_settings
from edu_ai.db import SessionFactory, engine
from edu_ai.models import AgentRun

settings = get_settings()
logger = logging.getLogger(__name__)


async def _fail_orphan_runs() -> None:
    """上次进程退出时仍在 RUNNING 的运行已无法完成，启动时统一收尾。"""
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        result = await session.execute(
            update(AgentRun)
            .where(AgentRun.status == "RUNNING")
            .values(
                status="FAILED",
                error="服务重启导致运行中断",
                completed_at=now,
                updated_at=now,
                output={
                    "code": "RUN_CANCELLED_BY_RESTART",
                    "message": "服务重启导致运行中断，请重试",
                },
            )
        )
        await session.commit()
    if result.rowcount:
        logger.warning("marked %s orphaned agent runs as failed", result.rowcount)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _fail_orphan_runs()
    except Exception:  # noqa: BLE001 - 数据库不可用时仍应启动，交给健康检查暴露
        logger.exception("failed to clean up orphaned agent runs")
    yield
    await engine.dispose()


app = FastAPI(
    title="Edu AI Service",
    version=settings.app_version,
    lifespan=lifespan,
)

# AI 服务只被客服服务内网调用，默认不放行浏览器跨域。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(internal.router)


@app.get("/", include_in_schema=False)
async def index() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
