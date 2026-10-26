"""工具统一返回结构与业务数据模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolFailureType(StrEnum):
    BUSINESS = "BUSINESS"
    SERVICE_CALL = "SERVICE_CALL"
    CONTRACT = "CONTRACT"


class ToolFailureCode(StrEnum):
    TOOL_CALL_FAILED = "TOOL_CALL_FAILED"
    INVALID_TOOL_RESULT = "INVALID_TOOL_RESULT"


class ToolResult[ResultData](BaseModel):
    success: bool
    code: str
    message: str
    data: ResultData | None = None
    failure_type: ToolFailureType | None = None


class ToolBusinessError(RuntimeError):
    """客服系统明确返回的业务失败，可作为回复依据。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class OrderItemData(BaseModel):
    product_name: str
    product_model: str
    quantity: int
    amount: Decimal


class OrderData(BaseModel):
    order_no: str
    status: str
    status_label: str | None = None
    total_amount: Decimal
    created_at: datetime
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    items: list[OrderItemData] = Field(default_factory=list)


class OrderListData(BaseModel):
    items: list[OrderData]


class LogisticsEventData(BaseModel):
    status: str
    description: str
    occurred_at: datetime


class LogisticsData(BaseModel):
    order_no: str
    status: str
    status_label: str | None = None
    carrier: str | None = None
    tracking_no: str | None = None
    latest_event: str | None = None
    events: list[LogisticsEventData] = Field(default_factory=list)


class OrderDetailData(OrderData):
    recipient_masked: str | None = None
    address_masked: str | None = None
    logistics: list[LogisticsEventData] = Field(default_factory=list)


class DeviceData(BaseModel):
    sn: str
    model: str
    activation_at: datetime | None = None
    firmware_version: str | None = None
    status: str
    warranty_type: str | None = None
    warranty_start_at: datetime | None = None
    warranty_end_at: datetime | None = None
    warranty_status: str = "unknown"
    warranty_status_label: str | None = None


class DeviceListData(BaseModel):
    items: list[DeviceData]


class RepairData(BaseModel):
    repair_no: str
    device_sn: str
    fault_type: str
    description: str
    status: str
    status_label: str | None = None
    mode: str
    warranty_status: str | None = None
    warranty_status_label: str | None = None
    quote_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class RepairListData(BaseModel):
    items: list[RepairData]


class RepairEventData(BaseModel):
    from_status: str | None = None
    to_status: str
    note: str | None = None
    created_at: datetime


class RepairDetailData(RepairData):
    events: list[RepairEventData] = Field(default_factory=list)


class KnowledgeHit(BaseModel):
    chunk_id: str
    score: float
    text: str
    article_id: str
    source_title: str | None = None
    doc_type: str | None = None
    version: int | None = None


class ActionPreparedData(BaseModel):
    action_id: str
    action_type: str
    status: str = "prepared"
    detail: dict[str, Any] = Field(default_factory=dict)
