"""订单、设备、保修与维修工单的读写业务。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import RepairEvent, RepairTicket
from edu_cs.repositories.catalog import CatalogRepository
from edu_cs.schemas.catalog import CreateRepairRequest

ORDER_STATUS_LABELS = {
    "pending": "待付款",
    "paid": "已付款待发货",
    "shipped": "已发货",
    "delivered": "已签收",
    "cancelled": "已取消",
    "after_sale": "售后处理中",
}
REPAIR_STATUS_LABELS = {
    "created": "已创建",
    "received": "已收件",
    "diagnosing": "检测中",
    "quoted": "已报价",
    "repairing": "维修中",
    "completed": "已完成",
    "cancelled": "已取消",
}
WARRANTY_STATUS_LABELS = {
    "in_warranty": "保修内",
    "out_of_warranty": "保外",
    "unknown": "未知",
}


class AfterSalesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CatalogRepository(session)

    # --- 订单 ---------------------------------------------------------
    async def list_orders(self, tenant_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        orders = await self.repository.list_orders(tenant_id, user_id)
        return [self.order_payload(order) for order in orders]

    async def get_order_detail(
        self,
        tenant_id: UUID,
        user_id: UUID,
        order_no: str,
        *,
        include_logistics: bool = False,
    ) -> dict[str, Any]:
        order = await self.repository.get_order(tenant_id, user_id, order_no)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
            )
        payload = self.order_payload(order, include_items=True)
        payload["recipient_masked"] = order.recipient_masked
        payload["address_masked"] = order.address_masked
        if include_logistics:
            events = await self.repository.list_logistics(order.id)
            payload["logistics"] = [
                {
                    "status": event.status,
                    "description": event.description,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in events
            ]
        return payload

    async def get_logistics(
        self, tenant_id: UUID, user_id: UUID, order_no: str
    ) -> dict[str, Any]:
        order = await self.repository.get_order(tenant_id, user_id, order_no)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
            )
        events = await self.repository.list_logistics(order.id)
        latest = events[-1] if events else None
        return {
            "order_no": order.order_no,
            "status": order.status,
            "status_label": ORDER_STATUS_LABELS.get(order.status, order.status),
            "carrier": latest.carrier if latest else None,
            "tracking_no": latest.tracking_no if latest else None,
            "latest_event": latest.description if latest else None,
            "events": [
                {
                    "status": event.status,
                    "description": event.description,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in events
            ],
        }

    async def cancel_order(
        self,
        tenant_id: UUID,
        user_id: UUID,
        order_no: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        order = await self.repository.get_order(
            tenant_id, user_id, order_no, for_update=True
        )
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
            )
        if order.status == "cancelled":
            return {
                "order_no": order.order_no,
                "status": order.status,
                "message": f"订单 {order.order_no} 已经取消，无需重复操作。",
            }
        if order.status not in ("pending", "paid"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"订单当前状态为{ORDER_STATUS_LABELS.get(order.status, order.status)}，不能直接取消",
            )
        order.status = "cancelled"
        order.cancelled_at = datetime.now(UTC)
        await self.session.flush()
        return {
            "order_no": order.order_no,
            "status": order.status,
            "message": (
                f"已为您取消订单 {order.order_no}，退款将原路退回，"
                "通常 1 至 3 个工作日到账。"
            ),
        }

    # --- 设备 / 保修 ---------------------------------------------------
    async def list_devices(self, tenant_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        devices = await self.repository.list_devices(tenant_id, user_id)
        warranties = await self.repository.get_warranties([item.id for item in devices])
        return [
            self.device_payload(device, warranties.get(device.id))
            for device in devices
        ]

    async def get_device(
        self, tenant_id: UUID, user_id: UUID, sn: str
    ) -> dict[str, Any]:
        device = await self.repository.get_user_device(tenant_id, user_id, sn)
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在或不属于当前用户"
            )
        warranties = await self.repository.get_warranties([device.id])
        return self.device_payload(device, warranties.get(device.id))

    # --- 维修工单 ------------------------------------------------------
    async def list_repairs(self, tenant_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        repairs = await self.repository.list_repairs(tenant_id, user_id)
        return [self.repair_payload(repair) for repair in repairs]

    async def get_repair(
        self, tenant_id: UUID, user_id: UUID, repair_no: str
    ) -> dict[str, Any]:
        repair = await self.repository.get_repair(tenant_id, user_id, repair_no)
        if repair is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="维修工单不存在"
            )
        payload = self.repair_payload(repair)
        events = await self.repository.list_repair_events(repair.id)
        payload["events"] = [
            {
                "from_status": event.from_status,
                "to_status": event.to_status,
                "note": event.note,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
        return payload

    async def create_repair(
        self,
        tenant_id: UUID,
        user_id: UUID,
        payload: CreateRepairRequest,
        *,
        idempotency_key: str | None = None,
        conversation_id: UUID | None = None,
    ) -> dict[str, Any]:
        """创建维修工单。

        repair_no 由幂等键确定性生成，重复请求返回第一次的结果，
        避免 AI 决策确认重试时产生重复工单。
        """
        repair_no = self._repair_no_for(idempotency_key)
        existing = await self.repository.get_repair_by_no(tenant_id, repair_no)
        if existing is not None:
            return {
                "repair_no": existing.repair_no,
                "status": existing.status,
                "message": self._repair_created_message(existing),
            }

        device = await self.repository.get_user_device(
            tenant_id, user_id, payload.device_sn
        )
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="设备不存在或不属于当前用户，无法创建维修工单",
            )
        warranties = await self.repository.get_warranties([device.id])
        warranty = warranties.get(device.id)
        warranty_status = self._warranty_status(warranty)

        repair = RepairTicket(
            tenant_id=tenant_id,
            repair_no=repair_no,
            user_id=user_id,
            conversation_id=conversation_id,
            device_id=device.id,
            device_sn=device.sn,
            fault_type=payload.fault_type,
            description=payload.description,
            status="created",
            mode=payload.mode,
            store_id=payload.store_id,
            warranty_status=warranty_status,
            contact=payload.contact,
        )
        await self.repository.add_repair(repair)
        await self.repository.add_repair_event(
            RepairEvent(
                repair_id=repair.id,
                from_status=None,
                to_status="created",
                operator_id=user_id,
                note="智能客服创建工单",
                attachments=[],
            )
        )
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.get_repair_by_no(tenant_id, repair_no)
            if existing is None:
                raise
            return {
                "repair_no": existing.repair_no,
                "status": existing.status,
                "message": self._repair_created_message(existing),
            }
        return {
            "repair_no": repair.repair_no,
            "status": repair.status,
            "message": self._repair_created_message(repair),
        }

    # --- 序列化 --------------------------------------------------------
    @staticmethod
    def order_payload(order, *, include_items: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "order_no": order.order_no,
            "status": order.status,
            "status_label": ORDER_STATUS_LABELS.get(order.status, order.status),
            "total_amount": str(order.total_amount),
            "created_at": order.created_at.isoformat(),
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
            "delivered_at": order.delivered_at.isoformat()
            if order.delivered_at
            else None,
            "cancelled_at": order.cancelled_at.isoformat()
            if order.cancelled_at
            else None,
        }
        if include_items:
            payload["items"] = [
                {
                    "product_name": item.product_name,
                    "product_model": item.product_model,
                    "quantity": item.quantity,
                    "amount": str(item.amount),
                }
                for item in order.items
            ]
        return payload

    @staticmethod
    def device_payload(device, warranty) -> dict[str, Any]:
        warranty_status = AfterSalesService._warranty_status(warranty)
        return {
            "sn": device.sn,
            "model": device.model,
            "activation_at": device.activation_at.isoformat()
            if device.activation_at
            else None,
            "firmware_version": device.firmware_version,
            "status": device.status,
            "warranty_type": warranty.type if warranty else None,
            "warranty_start_at": warranty.start_at.isoformat() if warranty else None,
            "warranty_end_at": warranty.end_at.isoformat() if warranty else None,
            "warranty_status": warranty_status,
            "warranty_status_label": WARRANTY_STATUS_LABELS[warranty_status],
        }

    @staticmethod
    def repair_payload(repair) -> dict[str, Any]:
        return {
            "repair_no": repair.repair_no,
            "device_sn": repair.device_sn,
            "fault_type": repair.fault_type,
            "description": repair.description,
            "status": repair.status,
            "status_label": REPAIR_STATUS_LABELS.get(repair.status, repair.status),
            "mode": repair.mode,
            "warranty_status": repair.warranty_status,
            "warranty_status_label": WARRANTY_STATUS_LABELS.get(
                repair.warranty_status or "unknown", "未知"
            ),
            "quote_amount": str(repair.quote_amount)
            if repair.quote_amount is not None
            else None,
            "created_at": repair.created_at.isoformat(),
            "updated_at": repair.updated_at.isoformat(),
            "closed_at": repair.closed_at.isoformat() if repair.closed_at else None,
        }

    @staticmethod
    def _warranty_status(warranty) -> str:
        if warranty is None:
            return "unknown"
        if warranty.status == "active" and warranty.end_at > datetime.now(UTC):
            return "in_warranty"
        return "out_of_warranty"

    @staticmethod
    def _repair_no_for(idempotency_key: str | None) -> str:
        if idempotency_key:
            token = "".join(ch for ch in idempotency_key.upper() if ch.isalnum())[:16]
            return f"REP_{token}"
        return f"REP_{uuid4().hex[:16].upper()}"

    @staticmethod
    def _repair_created_message(repair: RepairTicket) -> str:
        label = REPAIR_STATUS_LABELS.get(repair.status, repair.status)
        return (
            f"已为您创建维修工单 {repair.repair_no}（{label}），"
            "售后专员会尽快联系您确认收件方式。"
        )
