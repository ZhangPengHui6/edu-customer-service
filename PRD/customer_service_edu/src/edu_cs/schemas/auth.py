"""认证相关请求/响应模型。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DemoTokenRequest(BaseModel):
    tenant_code: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=64)


class DemoTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user_id: UUID
    tenant_id: UUID
    tenant_code: str
    tenant_type: Literal["HQ", "DEALER"]
    role: Literal["customer", "agent", "admin"]
    name: str
