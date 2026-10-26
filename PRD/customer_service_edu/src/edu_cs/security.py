"""JWT 签发与解析。

Phase 1 没有接入真实登录：``/api/v1/auth/demo-token`` 用种子用户换取令牌。
令牌里的 tenant 是租户隔离的唯一可信来源，业务接口不再接受客户端传入的 tenant。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt
from pydantic import BaseModel, ValidationError

from edu_cs.config import get_settings


class TokenError(ValueError):
    """令牌缺失、过期或内容不完整。"""


class Principal(BaseModel):
    """一次请求的可信身份。"""

    user_id: UUID
    tenant_id: UUID
    tenant_code: str
    tenant_type: Literal["HQ", "DEALER"]
    role: Literal["customer", "agent", "admin"]
    name: str

    @property
    def is_hq_admin(self) -> bool:
        return self.tenant_type == "HQ" and self.role == "admin"


def create_access_token(principal: Principal, ttl_seconds: int | None = None) -> str:
    """按配置签发访问令牌。"""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds or settings.jwt_ttl_seconds)
    payload = {
        "sub": str(principal.user_id),
        "tenant_id": str(principal.tenant_id),
        "tenant_code": principal.tenant_code,
        "tenant_type": principal.tenant_type,
        "role": principal.role,
        "name": principal.name,
        "iss": "edu-customer-service",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Principal:
    """解析并校验令牌；任何异常都统一成 TokenError。"""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="edu-customer-service",
        )
    except jwt.PyJWTError as exc:
        raise TokenError("无效令牌或者令牌已过期") from exc

    try:
        return Principal(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            tenant_code=str(payload["tenant_code"]),
            tenant_type=payload["tenant_type"],
            role=payload["role"],
            name=str(payload["name"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise TokenError("令牌缺少必要的身份信息") from exc
