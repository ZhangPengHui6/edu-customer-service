"""演示登录：用种子用户换取 JWT。真实登录接入后由统一认证替换。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from edu_cs.api.deps import SessionDep
from edu_cs.config import get_settings
from edu_cs.models import Tenant, User
from edu_cs.schemas.auth import DemoTokenRequest, DemoTokenResponse
from edu_cs.security import Principal, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/demo-token", response_model=DemoTokenResponse)
async def issue_demo_token(
    payload: DemoTokenRequest, session: SessionDep
) -> DemoTokenResponse:
    settings = get_settings()
    if not settings.demo_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="演示登录已关闭"
        )

    row = (
        await session.execute(
            select(User, Tenant)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(
                Tenant.code == payload.tenant_code,
                User.external_id == payload.external_id,
                User.status == "active",
                Tenant.status == "active",
            )
        )
    ).tuples().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="租户或用户不存在",
        )
    user, tenant = row
    principal = Principal(
        user_id=user.id,
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        tenant_type=tenant.type,
        role=user.role,
        name=user.name,
    )
    token = create_access_token(principal)
    return DemoTokenResponse(
        access_token=token,
        expires_in=settings.jwt_ttl_seconds,
        user_id=user.id,
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        tenant_type=tenant.type,
        role=user.role,
        name=user.name,
    )
