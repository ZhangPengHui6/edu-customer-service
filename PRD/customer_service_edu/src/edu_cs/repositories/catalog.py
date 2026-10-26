"""订单、设备、维修、工单等业务数据仓储。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from edu_cs.models import (
    Agent,
    Device,
    DeviceBinding,
    Handoff,
    HandoffEvent,
    LogisticsEvent,
    Order,
    RepairEvent,
    RepairTicket,
    Warranty,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- 订单 ---------------------------------------------------------
    async def list_orders(
        self, tenant_id: UUID, user_id: UUID, limit: int = 20
    ) -> list[Order]:
        orders = await self.session.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.tenant_id == tenant_id, Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(orders.all())

    async def get_order(
        self,
        tenant_id: UUID,
        user_id: UUID,
        order_no: str,
        *,
        for_update: bool = False,
    ) -> Order | None:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(
                Order.tenant_id == tenant_id,
                Order.user_id == user_id,
                Order.order_no == order_no.upper(),
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def list_logistics(self, order_id: UUID) -> list[LogisticsEvent]:
        events = await self.session.scalars(
            select(LogisticsEvent)
            .where(LogisticsEvent.order_id == order_id)
            .order_by(LogisticsEvent.occurred_at, LogisticsEvent.id)
        )
        return list(events.all())

    # --- 设备 / 保修 ---------------------------------------------------
    async def list_devices(self, tenant_id: UUID, user_id: UUID) -> list[Device]:
        devices = await self.session.scalars(
            select(Device)
            .where(
                Device.tenant_id == tenant_id,
                or_(
                    Device.owner_user_id == user_id,
                    exists().where(
                        DeviceBinding.device_id == Device.id,
                        DeviceBinding.user_id == user_id,
                        DeviceBinding.status == "active",
                    ),
                ),
            )
            .order_by(Device.created_at)
        )
        return list(devices.all())

    async def get_device(self, tenant_id: UUID, sn: str) -> Device | None:
        return await self.session.scalar(
            select(Device).where(Device.tenant_id == tenant_id, Device.sn == sn.upper())
        )

    async def get_user_device(
        self, tenant_id: UUID, user_id: UUID, sn: str
    ) -> Device | None:
        return await self.session.scalar(
            select(Device).where(
                Device.tenant_id == tenant_id,
                Device.sn == sn.upper(),
                or_(
                    Device.owner_user_id == user_id,
                    exists().where(
                        DeviceBinding.device_id == Device.id,
                        DeviceBinding.user_id == user_id,
                        DeviceBinding.status == "active",
                    ),
                ),
            )
        )

    async def get_warranties(self, device_ids: list[UUID]) -> dict[UUID, Warranty]:
        if not device_ids:
            return {}
        warranties = await self.session.scalars(
            select(Warranty).where(Warranty.device_id.in_(device_ids))
        )
        return {item.device_id: item for item in warranties.all()}

    # --- 维修工单 ------------------------------------------------------
    async def list_repairs(
        self, tenant_id: UUID, user_id: UUID, limit: int = 20
    ) -> list[RepairTicket]:
        repairs = await self.session.scalars(
            select(RepairTicket)
            .where(RepairTicket.tenant_id == tenant_id, RepairTicket.user_id == user_id)
            .order_by(RepairTicket.created_at.desc())
            .limit(limit)
        )
        return list(repairs.all())

    async def get_repair(
        self,
        tenant_id: UUID,
        user_id: UUID,
        repair_no: str,
        *,
        for_update: bool = False,
    ) -> RepairTicket | None:
        stmt = select(RepairTicket).where(
            RepairTicket.tenant_id == tenant_id,
            RepairTicket.user_id == user_id,
            RepairTicket.repair_no == repair_no.upper(),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def get_repair_by_no(
        self, tenant_id: UUID, repair_no: str
    ) -> RepairTicket | None:
        return await self.session.scalar(
            select(RepairTicket).where(
                RepairTicket.tenant_id == tenant_id,
                RepairTicket.repair_no == repair_no,
            )
        )

    async def list_repair_events(self, repair_id: UUID) -> list[RepairEvent]:
        events = await self.session.scalars(
            select(RepairEvent)
            .where(RepairEvent.repair_id == repair_id)
            .order_by(RepairEvent.id)
        )
        return list(events.all())

    async def add_repair(self, repair: RepairTicket) -> RepairTicket:
        self.session.add(repair)
        await self.session.flush()
        return repair

    async def add_repair_event(self, event: RepairEvent) -> None:
        self.session.add(event)

    # --- 人工工单 ------------------------------------------------------
    async def find_open_handoff(
        self, tenant_id: UUID, user_id: UUID
    ) -> Handoff | None:
        return await self.session.scalar(
            select(Handoff).where(
                Handoff.tenant_id == tenant_id,
                Handoff.user_id == user_id,
                Handoff.status.in_(("waiting", "active")),
            )
        )

    async def get_handoff(
        self, tenant_id: UUID, handoff_id: UUID, *, for_update: bool = False
    ) -> Handoff | None:
        stmt = select(Handoff).where(
            Handoff.tenant_id == tenant_id, Handoff.id == handoff_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def list_handoffs(
        self,
        tenant_id: UUID,
        *,
        statuses: tuple[str, ...] = ("waiting", "active"),
        limit: int = 50,
    ) -> list[Handoff]:
        handoffs = await self.session.scalars(
            select(Handoff)
            .where(Handoff.tenant_id == tenant_id, Handoff.status.in_(statuses))
            .order_by(Handoff.priority, Handoff.created_at)
            .limit(limit)
        )
        return list(handoffs.all())

    def add_handoff(self, handoff: Handoff) -> Handoff:
        self.session.add(handoff)
        return handoff

    def add_handoff_event(self, event: HandoffEvent) -> None:
        self.session.add(event)

    async def list_handoff_events(self, handoff_id: UUID) -> list[HandoffEvent]:
        events = await self.session.scalars(
            select(HandoffEvent)
            .where(HandoffEvent.handoff_id == handoff_id)
            .order_by(HandoffEvent.id)
        )
        return list(events.all())

    async def get_agent_by_user(
        self, tenant_id: UUID, user_id: UUID
    ) -> Agent | None:
        return await self.session.scalar(
            select(Agent).where(
                Agent.tenant_id == tenant_id, Agent.user_id == user_id
            )
        )
