"""服务入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edu_cs.api import (
    admin,
    auth,
    conversations,
    health,
    internal,
    me,
    realtime,
    staff,
)
from edu_cs.config import get_settings
from edu_cs.db import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Edu Customer Service",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(me.router)
app.include_router(staff.router)
app.include_router(internal.router)
app.include_router(admin.router)
app.include_router(realtime.router)


@app.get("/", include_in_schema=False)
async def index() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
