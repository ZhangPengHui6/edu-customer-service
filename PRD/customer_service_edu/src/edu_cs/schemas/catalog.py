"""订单、设备、维修等业务数据的接口模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OrderStatus = Literal["pending", "paid", "shipped", "delivered", "cancelled", "after_sale"]
RepairStatus = Literal[
    "created", "received", "diagnosing", "quoted", "repairing", "completed", "cancelled"
]
RepairMode = Literal["mail_in", "in_store", "on_site"]
WarrantyStatus = Literal["in_warranty", "out_of_warranty", "unknown"]


class OrderItemOut(BaseModel):
    product_name: str
    product_model: str
    quantity: int
    amount: Decimal


class LogisticsEventOut(BaseModel):
    status: str
    description: str
    occurred_at: datetime


class OrderOut(BaseModel):
    order_no: str
    status: OrderStatus
    status_label: str | None = None
    total_amount: Decimal
    created_at: datetime
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    items: list[OrderItemOut]


class OrderListResponse(BaseModel):
    items: list[OrderOut]


class OrderDetailResponse(OrderOut):
    recipient_masked: str | None
    address_masked: str | None
    logistics: list[LogisticsEventOut] = Field(default_factory=list)


class DeviceOut(BaseModel):
    sn: str
    model: str
    activation_at: datetime | None
    firmware_version: str | None
    status: str
    warranty_type: str | None = None
    warranty_start_at: datetime | None = None
    warranty_end_at: datetime | None = None
    warranty_status: WarrantyStatus = "unknown"
    warranty_status_label: str | None = None


class DeviceListResponse(BaseModel):
    items: list[DeviceOut]


class RepairOut(BaseModel):
    repair_no: str
    device_sn: str
    fault_type: str
    description: str
    status: RepairStatus
    status_label: str | None = None
    mode: RepairMode
    warranty_status: WarrantyStatus | None
    warranty_status_label: str | None = None
    quote_amount: Decimal | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class RepairListResponse(BaseModel):
    items: list[RepairOut]


class RepairDetailResponse(RepairOut):
    events: list[dict] = Field(default_factory=list)


class CreateRepairRequest(BaseModel):
    device_sn: str = Field(min_length=6, max_length=64)
    fault_type: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    mode: RepairMode = "mail_in"
    contact: str | None = Field(default=None, max_length=64)
    store_id: UUID | None = None
    conversation_id: UUID | None = None


class RepairActionResult(BaseModel):
    repair_no: str
    status: RepairStatus
    message: str


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class CancelOrderResult(BaseModel):
    order_no: str
    status: OrderStatus
    message: str
