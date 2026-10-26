"""FastAPI 通用依赖：数据库会话、用户身份、租户范围、内部服务调用。"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.config import get_settings
from edu_cs.db import get_session
from edu_cs.models import Tenant, User
from edu_cs.security import Principal, TokenError, decode_access_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


class InternalIdentity(BaseModel):
    """AI 服务以内部身份访问客服接口时的上下文。"""

    tenant_id: UUID
    tenant_code: str
    tenant_type: Literal["HQ", "DEALER"]
    user_id: UUID


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_roles(principal: Principal, *roles: Literal["customer", "agent", "admin"]) -> None:
    if principal.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号没有该操作权限",
        )


def resolve_staff_tenant(
    principal: Principal,
    requested_tenant_id: UUID | None,
) -> tuple[UUID, bool]:
    """返回客服端要操作的租户及是否为跨租户操作。

    - 经销商只能操作自己的租户；
    - 总部管理员可以指定任意租户；
    - 总部普通客服仍限制在总部租户，避免越权。
    """
    if requested_tenant_id is None or requested_tenant_id == principal.tenant_id:
        return principal.tenant_id, False
    if principal.is_hq_admin:
        return requested_tenant_id, True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权访问其他租户的数据",
    )


async def get_internal_identity(
    session: SessionDep,
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
    tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-Id")] = None,
    user_id: Annotated[UUID | None, Header(alias="X-User-Id")] = None,
) -> InternalIdentity:
    """校验内部服务令牌，并确认用户确实属于指定租户。"""
    if token != get_settings().internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的内部服务令牌",
        )
    if tenant_id is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="内部调用必须提供 X-Tenant-Id 与 X-User-Id",
        )

    row = (
        await session.execute(
            select(User, Tenant)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.status == "active",
                Tenant.status == "active",
            )
        )
    ).tuples().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定的租户或用户不存在",
        )
    user, tenant = row
    return InternalIdentity(
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        tenant_type=tenant.type,
        user_id=user.id,
    )


InternalIdentityDep = Annotated[InternalIdentity, Depends(get_internal_identity)]


async def get_staff_identity(
    session: SessionDep,
    principal: PrincipalDep,
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-Id")] = None,
) -> tuple[Principal, UUID]:
    """客服端接口的租户解析（不写审计，端点按需审计）。"""
    require_roles(principal, "agent", "admin")
    tenant_id, _ = resolve_staff_tenant(principal, x_tenant_id)
    return principal, tenant_id
