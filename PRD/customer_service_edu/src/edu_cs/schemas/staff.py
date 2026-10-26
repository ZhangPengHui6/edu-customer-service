"""人工工单接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from edu_cs.schemas.catalog import DeviceOut, OrderOut, RepairOut

HandoffStatus = Literal["waiting", "active", "resolved", "closed", "cancelled"]
Priority = Literal["P0", "P1", "P2"]


class HandoffSummary(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    summary: str
    status: HandoffStatus
    priority: Priority
    assigned_agent_id: UUID | None
    created_at: datetime
    accepted_at: datetime | None
    resolved_at: datetime | None
    sla_due_at: datetime | None = None
    customer_name: str | None = None
    customer_phone_masked: str | None = None


class StaffCustomerOut(BaseModel):
    id: UUID
    name: str
    phone_masked: str | None


class StaffCustomerStats(BaseModel):
    orders: int
    devices: int
    repairs: int


class StaffHandoffContextResponse(BaseModel):
    customer: StaffCustomerOut
    stats: StaffCustomerStats
    orders: list[OrderOut]
    devices: list[DeviceOut]
    repairs: list[RepairOut]


class HandoffListResponse(BaseModel):
    items: list[HandoffSummary]


class HandoffEventItem(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    operator_id: UUID | None
    note: str | None
    created_at: datetime


class HandoffEventListResponse(BaseModel):
    items: list[HandoffEventItem]


class StaffMessageRequest(BaseModel):
    client_message_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class StaffMessageResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    sequence: int
    created_at: datetime


class ResolveHandoffRequest(BaseModel):
    close_reason: str = Field(default="resolved", max_length=32)
    note: str | None = Field(default=None, max_length=1000)


class HandoffActionResponse(BaseModel):
    handoff: HandoffSummary
    conversation_mode: str


class StaffAuditContext(BaseModel):
    tenant_id: UUID
    cross_tenant: bool
    detail: dict[str, Any] = Field(default_factory=dict)
