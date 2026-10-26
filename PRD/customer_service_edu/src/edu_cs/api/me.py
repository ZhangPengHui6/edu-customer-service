"""客户自助查询订单、设备与维修工单。"""

from __future__ import annotations

from fastapi import APIRouter

from edu_cs.api.deps import PrincipalDep, SessionDep
from edu_cs.schemas.catalog import (
    DeviceListResponse,
    DeviceOut,
    OrderDetailResponse,
    OrderListResponse,
    OrderOut,
    RepairDetailResponse,
    RepairListResponse,
    RepairOut,
)
from edu_cs.services.after_sales import AfterSalesService

router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    principal: PrincipalDep, session: SessionDep
) -> OrderListResponse:
    items = await AfterSalesService(session).list_orders(
        principal.tenant_id, principal.user_id
    )
    return OrderListResponse(items=[OrderOut(**item) for item in items])


@router.get("/orders/{order_no}", response_model=OrderDetailResponse)
async def order_detail(
    order_no: str, principal: PrincipalDep, session: SessionDep
) -> OrderDetailResponse:
    result = await AfterSalesService(session).get_order_detail(
        principal.tenant_id, principal.user_id, order_no, include_logistics=True
    )
    return OrderDetailResponse(**result)


@router.get("/orders/{order_no}/logistics")
async def order_logistics(
    order_no: str, principal: PrincipalDep, session: SessionDep
) -> dict:
    return await AfterSalesService(session).get_logistics(
        principal.tenant_id, principal.user_id, order_no
    )


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    principal: PrincipalDep, session: SessionDep
) -> DeviceListResponse:
    items = await AfterSalesService(session).list_devices(
        principal.tenant_id, principal.user_id
    )
    return DeviceListResponse(items=[DeviceOut(**item) for item in items])


@router.get("/devices/{sn}", response_model=DeviceOut)
async def device_detail(
    sn: str, principal: PrincipalDep, session: SessionDep
) -> DeviceOut:
    result = await AfterSalesService(session).get_device(
        principal.tenant_id, principal.user_id, sn
    )
    return DeviceOut(**result)


@router.get("/repairs", response_model=RepairListResponse)
async def list_repairs(
    principal: PrincipalDep, session: SessionDep
) -> RepairListResponse:
    items = await AfterSalesService(session).list_repairs(
        principal.tenant_id, principal.user_id
    )
    return RepairListResponse(items=[RepairOut(**item) for item in items])


@router.get("/repairs/{repair_no}", response_model=RepairDetailResponse)
async def repair_detail(
    repair_no: str, principal: PrincipalDep, session: SessionDep
) -> RepairDetailResponse:
    result = await AfterSalesService(session).get_repair(
        principal.tenant_id, principal.user_id, repair_no
    )
    return RepairDetailResponse(**result)
