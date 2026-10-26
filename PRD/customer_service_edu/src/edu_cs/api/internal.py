"""内部工具接口：仅供 AI 服务以受信身份读取/执行售后业务。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from edu_cs.api.deps import InternalIdentityDep, SessionDep
from edu_cs.schemas.catalog import (
    CancelOrderRequest,
    CancelOrderResult,
    CreateRepairRequest,
    DeviceListResponse,
    DeviceOut,
    OrderDetailResponse,
    OrderListResponse,
    OrderOut,
    RepairActionResult,
    RepairDetailResponse,
    RepairListResponse,
    RepairOut,
)
from edu_cs.services.after_sales import AfterSalesService

router = APIRouter(prefix="/internal/v1/tools", tags=["internal"])

IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    identity: InternalIdentityDep, session: SessionDep
) -> OrderListResponse:
    items = await AfterSalesService(session).list_orders(
        identity.tenant_id, identity.user_id
    )
    return OrderListResponse(items=[OrderOut(**item) for item in items])


@router.get("/orders/{order_no}", response_model=OrderDetailResponse)
async def get_order(
    order_no: str, identity: InternalIdentityDep, session: SessionDep
) -> OrderDetailResponse:
    result = await AfterSalesService(session).get_order_detail(
        identity.tenant_id,
        identity.user_id,
        order_no,
        include_logistics=True,
    )
    return OrderDetailResponse(**result)


@router.get("/orders/{order_no}/logistics")
async def get_logistics(
    order_no: str, identity: InternalIdentityDep, session: SessionDep
) -> dict:
    return await AfterSalesService(session).get_logistics(
        identity.tenant_id, identity.user_id, order_no
    )


@router.post("/orders/{order_no}/cancel", response_model=CancelOrderResult)
async def cancel_order(
    order_no: str,
    payload: CancelOrderRequest,
    identity: InternalIdentityDep,
    session: SessionDep,
) -> CancelOrderResult:
    result = await AfterSalesService(session).cancel_order(
        identity.tenant_id,
        identity.user_id,
        order_no,
        reason=payload.reason,
    )
    await session.commit()
    return CancelOrderResult(**result)


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    identity: InternalIdentityDep, session: SessionDep
) -> DeviceListResponse:
    items = await AfterSalesService(session).list_devices(
        identity.tenant_id, identity.user_id
    )
    return DeviceListResponse(items=[DeviceOut(**item) for item in items])


@router.get("/devices/{sn}", response_model=DeviceOut)
async def get_device(
    sn: str, identity: InternalIdentityDep, session: SessionDep
) -> DeviceOut:
    result = await AfterSalesService(session).get_device(
        identity.tenant_id, identity.user_id, sn
    )
    return DeviceOut(**result)


@router.get("/repairs", response_model=RepairListResponse)
async def list_repairs(
    identity: InternalIdentityDep, session: SessionDep
) -> RepairListResponse:
    items = await AfterSalesService(session).list_repairs(
        identity.tenant_id, identity.user_id
    )
    return RepairListResponse(items=[RepairOut(**item) for item in items])


@router.get("/repairs/{repair_no}", response_model=RepairDetailResponse)
async def get_repair(
    repair_no: str, identity: InternalIdentityDep, session: SessionDep
) -> RepairDetailResponse:
    result = await AfterSalesService(session).get_repair(
        identity.tenant_id, identity.user_id, repair_no
    )
    return RepairDetailResponse(**result)


@router.post("/repairs", response_model=RepairActionResult)
async def create_repair(
    payload: CreateRepairRequest,
    identity: InternalIdentityDep,
    session: SessionDep,
    idempotency_key: IdempotencyKey = None,
) -> RepairActionResult:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创建维修工单必须提供 Idempotency-Key",
        )
    result = await AfterSalesService(session).create_repair(
        identity.tenant_id,
        identity.user_id,
        payload,
        idempotency_key=idempotency_key,
        conversation_id=payload.conversation_id,
    )
    await session.commit()
    return RepairActionResult(**result)
