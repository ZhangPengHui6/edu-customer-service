"""幂等写入 Phase 0 测试数据。

用法：
    python scripts/seed.py

库里已有租户数据时直接跳过，不在中途做部分写入；全部数据在同一事务内提交。
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import func, insert, select

from edu_cs.db import SessionFactory, engine
from edu_cs.models import (
    Agent,
    AgentSkill,
    AuditLog,
    CannedReply,
    Conversation,
    CsatSurvey,
    Device,
    DeviceBinding,
    Handoff,
    HandoffEvent,
    LogisticsEvent,
    Message,
    Order,
    OrderItem,
    RepairEvent,
    RepairTicket,
    ServiceCenter,
    SkillGroup,
    Tenant,
    User,
    Warranty,
)

NS = uuid5(NAMESPACE_URL, "https://edu-cs.local/seed")


def pk(name: str) -> UUID:
    return uuid5(NS, name)


def dt(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[arg-type]


async def seed() -> None:
    async with SessionFactory() as session:
        existing = await session.scalar(select(func.count()).select_from(Tenant))
        if existing:
            print(f"已存在 {existing} 个租户，跳过 seed。")
            return

        # --- 租户 ---------------------------------------------------------
        tenant_hq = pk("tenant:hq")
        tenant_north = pk("tenant:dlr_north")
        tenant_south = pk("tenant:dlr_south")

        await session.execute(
            insert(Tenant),
            [
                {
                    "id": tenant_hq,
                    "code": "hq",
                    "type": "HQ",
                    "name": "学习机总部",
                    "parent_id": None,
                    "status": "active",
                },
                {
                    "id": tenant_north,
                    "code": "dlr_north",
                    "type": "DEALER",
                    "name": "华北经销商",
                    "parent_id": tenant_hq,
                    "status": "active",
                },
                {
                    "id": tenant_south,
                    "code": "dlr_south",
                    "type": "DEALER",
                    "name": "华南经销商",
                    "parent_id": tenant_hq,
                    "status": "active",
                },
            ],
        )

        # --- 用户 ---------------------------------------------------------
        user_parent_001 = pk("user:parent_001")
        user_parent_002 = pk("user:parent_002")
        user_parent_003 = pk("user:parent_003")
        user_student_001 = pk("user:student_001")
        user_agent_001 = pk("user:agent_001")
        user_agent_002 = pk("user:agent_002")
        user_admin_001 = pk("user:admin_001")

        await session.execute(
            insert(User),
            [
                {
                    "id": user_parent_001,
                    "tenant_id": tenant_north,
                    "external_id": "parent_001",
                    "role": "customer",
                    "name": "张伟",
                    "phone_masked": "138****0001",
                    "guardian_user_id": None,
                    "status": "active",
                },
                {
                    "id": user_parent_002,
                    "tenant_id": tenant_north,
                    "external_id": "parent_002",
                    "role": "customer",
                    "name": "李娜",
                    "phone_masked": "139****0002",
                    "guardian_user_id": None,
                    "status": "active",
                },
                {
                    "id": user_parent_003,
                    "tenant_id": tenant_south,
                    "external_id": "parent_003",
                    "role": "customer",
                    "name": "王强",
                    "phone_masked": "137****0003",
                    "guardian_user_id": None,
                    "status": "active",
                },
                {
                    "id": user_student_001,
                    "tenant_id": tenant_north,
                    "external_id": "student_001",
                    "role": "customer",
                    "name": "张小明",
                    "phone_masked": None,
                    "guardian_user_id": user_parent_001,
                    "status": "active",
                },
                {
                    "id": user_agent_001,
                    "tenant_id": tenant_north,
                    "external_id": "agent_001",
                    "role": "agent",
                    "name": "陈晓",
                    "phone_masked": None,
                    "guardian_user_id": None,
                    "status": "active",
                },
                {
                    "id": user_agent_002,
                    "tenant_id": tenant_south,
                    "external_id": "agent_002",
                    "role": "agent",
                    "name": "刘悦",
                    "phone_masked": None,
                    "guardian_user_id": None,
                    "status": "active",
                },
                {
                    "id": user_admin_001,
                    "tenant_id": tenant_hq,
                    "external_id": "admin_001",
                    "role": "admin",
                    "name": "总部管理员",
                    "phone_masked": None,
                    "guardian_user_id": None,
                    "status": "active",
                },
            ],
        )

        # --- 技能组 / 坐席 ------------------------------------------------
        sg_north_after = pk("skill_group:north_after_sales")
        sg_north_complaint = pk("skill_group:north_complaint")
        sg_south_after = pk("skill_group:south_after_sales")

        await session.execute(
            insert(SkillGroup),
            [
                {
                    "id": sg_north_after,
                    "tenant_id": tenant_north,
                    "code": "after_sales",
                    "name": "华北售后支持",
                    "routing_strategy": "round_robin",
                    "sla_config": {"first_response_seconds": 120},
                    "status": "active",
                },
                {
                    "id": sg_north_complaint,
                    "tenant_id": tenant_north,
                    "code": "complaint",
                    "name": "华北投诉处理",
                    "routing_strategy": "least_active",
                    "sla_config": {"first_response_seconds": 60, "priority": "P1"},
                    "status": "active",
                },
                {
                    "id": sg_south_after,
                    "tenant_id": tenant_south,
                    "code": "after_sales",
                    "name": "华南售后支持",
                    "routing_strategy": "round_robin",
                    "sla_config": {"first_response_seconds": 120},
                    "status": "active",
                },
            ],
        )

        agent_001 = pk("agent:agent_001")
        agent_002 = pk("agent:agent_002")

        await session.execute(
            insert(Agent),
            [
                {
                    "id": agent_001,
                    "tenant_id": tenant_north,
                    "user_id": user_agent_001,
                    "name": "陈晓",
                    "status": "online",
                    "max_concurrent": 5,
                },
                {
                    "id": agent_002,
                    "tenant_id": tenant_south,
                    "user_id": user_agent_002,
                    "name": "刘悦",
                    "status": "online",
                    "max_concurrent": 5,
                },
            ],
        )

        await session.execute(
            insert(AgentSkill),
            [
                {"agent_id": agent_001, "skill_group_id": sg_north_after, "level": 2},
                {"agent_id": agent_001, "skill_group_id": sg_north_complaint, "level": 1},
                {"agent_id": agent_002, "skill_group_id": sg_south_after, "level": 2},
            ],
        )

        # --- 设备 / 保修 / 绑定 -------------------------------------------
        dev_1 = pk("device:SNX5000001")
        dev_2 = pk("device:SNX5000002")
        dev_3 = pk("device:SNX6000001")
        dev_4 = pk("device:SNS3000001")
        dev_5 = pk("device:SNS3000002")

        await session.execute(
            insert(Device),
            [
                {
                    "id": dev_1,
                    "tenant_id": tenant_north,
                    "sn": "SNX5000001",
                    "model": "X5",
                    "activation_at": dt(2025, 3, 15),
                    "firmware_version": "2.3.1",
                    "status": "active",
                    "owner_user_id": user_parent_001,
                },
                {
                    "id": dev_2,
                    "tenant_id": tenant_north,
                    "sn": "SNX5000002",
                    "model": "X5",
                    "activation_at": dt(2025, 5, 20),
                    "firmware_version": "2.2.7",
                    "status": "active",
                    "owner_user_id": user_parent_002,
                },
                {
                    "id": dev_3,
                    "tenant_id": tenant_north,
                    "sn": "SNX6000001",
                    "model": "X6",
                    "activation_at": dt(2025, 9, 1),
                    "firmware_version": "3.0.0",
                    "status": "active",
                    "owner_user_id": user_parent_001,
                },
                {
                    "id": dev_4,
                    "tenant_id": tenant_south,
                    "sn": "SNS3000001",
                    "model": "S3",
                    "activation_at": dt(2026, 1, 10),
                    "firmware_version": "1.8.4",
                    "status": "active",
                    "owner_user_id": user_parent_003,
                },
                {
                    "id": dev_5,
                    "tenant_id": tenant_south,
                    "sn": "SNS3000002",
                    "model": "S3",
                    "activation_at": dt(2024, 6, 1),
                    "firmware_version": "1.5.2",
                    "status": "active",
                    "owner_user_id": user_parent_003,
                },
            ],
        )

        await session.execute(
            insert(Warranty),
            [
                {
                    "id": pk("warranty:SNX5000001"),
                    "tenant_id": tenant_north,
                    "device_id": dev_1,
                    "type": "standard",
                    "start_at": dt(2025, 3, 15),
                    "end_at": dt(2027, 3, 14),
                    "status": "active",
                    "source": "order:ORDER_20251001",
                },
                {
                    "id": pk("warranty:SNX5000002"),
                    "tenant_id": tenant_north,
                    "device_id": dev_2,
                    "type": "standard",
                    "start_at": dt(2025, 5, 20),
                    "end_at": dt(2026, 5, 19),
                    "status": "expired",
                    "source": "order:ORDER_20251002",
                },
                {
                    "id": pk("warranty:SNX6000001"),
                    "tenant_id": tenant_north,
                    "device_id": dev_3,
                    "type": "extended",
                    "start_at": dt(2025, 9, 1),
                    "end_at": dt(2027, 8, 31),
                    "status": "active",
                    "source": "order:ORDER_20251003",
                },
                {
                    "id": pk("warranty:SNS3000001"),
                    "tenant_id": tenant_south,
                    "device_id": dev_4,
                    "type": "standard",
                    "start_at": dt(2026, 1, 10),
                    "end_at": dt(2028, 1, 9),
                    "status": "active",
                    "source": "order:ORDER_20251004",
                },
                {
                    "id": pk("warranty:SNS3000002"),
                    "tenant_id": tenant_south,
                    "device_id": dev_5,
                    "type": "standard",
                    "start_at": dt(2024, 6, 1),
                    "end_at": dt(2026, 5, 31),
                    "status": "expired",
                    "source": "order:ORDER_20251004",
                },
            ],
        )

        await session.execute(
            insert(DeviceBinding),
            [
                {
                    "id": pk("binding:SNX5000001:parent_001"),
                    "tenant_id": tenant_north,
                    "device_id": dev_1,
                    "user_id": user_parent_001,
                    "role": "guardian",
                    "status": "active",
                    "bound_at": dt(2025, 3, 15),
                    "unbound_at": None,
                },
                {
                    "id": pk("binding:SNX5000002:parent_002"),
                    "tenant_id": tenant_north,
                    "device_id": dev_2,
                    "user_id": user_parent_002,
                    "role": "guardian",
                    "status": "active",
                    "bound_at": dt(2025, 5, 20),
                    "unbound_at": None,
                },
                {
                    "id": pk("binding:SNX6000001:parent_001"),
                    "tenant_id": tenant_north,
                    "device_id": dev_3,
                    "user_id": user_parent_001,
                    "role": "guardian",
                    "status": "active",
                    "bound_at": dt(2025, 9, 1),
                    "unbound_at": None,
                },
                {
                    "id": pk("binding:SNX6000001:student_001"),
                    "tenant_id": tenant_north,
                    "device_id": dev_3,
                    "user_id": user_student_001,
                    "role": "student",
                    "status": "active",
                    "bound_at": dt(2025, 9, 1),
                    "unbound_at": None,
                },
                {
                    "id": pk("binding:SNS3000001:parent_003"),
                    "tenant_id": tenant_south,
                    "device_id": dev_4,
                    "user_id": user_parent_003,
                    "role": "guardian",
                    "status": "active",
                    "bound_at": dt(2026, 1, 10),
                    "unbound_at": None,
                },
                {
                    "id": pk("binding:SNS3000002:parent_003"),
                    "tenant_id": tenant_south,
                    "device_id": dev_5,
                    "user_id": user_parent_003,
                    "role": "guardian",
                    "status": "active",
                    "bound_at": dt(2024, 6, 1),
                    "unbound_at": None,
                },
            ],
        )

        # --- 服务中心 -----------------------------------------------------
        sc_north = pk("service_center:north")
        sc_south = pk("service_center:south")
        sc_hq = pk("service_center:hq")

        await session.execute(
            insert(ServiceCenter),
            [
                {
                    "id": sc_north,
                    "tenant_id": tenant_north,
                    "name": "北京朝阳服务中心",
                    "city": "北京",
                    "district": "朝阳区",
                    "address": "北京市朝阳区建国路 88 号",
                    "phone": "010-88880001",
                    "service_types": ["in_store", "mail_in"],
                    "status": "active",
                },
                {
                    "id": sc_south,
                    "tenant_id": tenant_south,
                    "name": "广州天河服务中心",
                    "city": "广州",
                    "district": "天河区",
                    "address": "广州市天河区体育西路 66 号",
                    "phone": "020-88880002",
                    "service_types": ["in_store", "mail_in"],
                    "status": "active",
                },
                {
                    "id": sc_hq,
                    "tenant_id": tenant_hq,
                    "name": "上海总部直营服务中心",
                    "city": "上海",
                    "district": "浦东新区",
                    "address": "上海市浦东新区张江路 100 号",
                    "phone": "021-88880003",
                    "service_types": ["in_store", "mail_in", "on_site"],
                    "status": "active",
                },
            ],
        )

        # --- 订单 / 物流 ---------------------------------------------------
        order_1 = pk("order:ORDER_20251001")
        order_2 = pk("order:ORDER_20251002")
        order_3 = pk("order:ORDER_20251003")
        order_4 = pk("order:ORDER_20251004")
        order_5 = pk("order:ORDER_20251005")

        await session.execute(
            insert(Order),
            [
                {
                    "id": order_1,
                    "tenant_id": tenant_north,
                    "user_id": user_parent_001,
                    "order_no": "ORDER_20251001",
                    "status": "delivered",
                    "total_amount": Decimal("3299.00"),
                    "recipient_masked": "张*",
                    "address_masked": "北京市朝阳区****",
                    "created_at": dt(2025, 10, 1, 9, 0),
                    "updated_at": dt(2025, 10, 5, 18, 0),
                    "shipped_at": dt(2025, 10, 2, 10, 0),
                    "delivered_at": dt(2025, 10, 5, 15, 0),
                    "cancelled_at": None,
                },
                {
                    "id": order_2,
                    "tenant_id": tenant_north,
                    "user_id": user_parent_002,
                    "order_no": "ORDER_20251002",
                    "status": "shipped",
                    "total_amount": Decimal("3398.00"),
                    "recipient_masked": "李*",
                    "address_masked": "北京市海淀区****",
                    "created_at": dt(2026, 10, 23, 14, 0),
                    "updated_at": dt(2026, 10, 25, 9, 0),
                    "shipped_at": dt(2026, 10, 24, 11, 0),
                    "delivered_at": None,
                    "cancelled_at": None,
                },
                {
                    "id": order_3,
                    "tenant_id": tenant_north,
                    "user_id": user_parent_001,
                    "order_no": "ORDER_20251003",
                    "status": "paid",
                    "total_amount": Decimal("4999.00"),
                    "recipient_masked": "张*",
                    "address_masked": "北京市朝阳区****",
                    "created_at": dt(2026, 10, 25, 16, 0),
                    "updated_at": dt(2026, 10, 25, 16, 5),
                    "shipped_at": None,
                    "delivered_at": None,
                    "cancelled_at": None,
                },
                {
                    "id": order_4,
                    "tenant_id": tenant_south,
                    "user_id": user_parent_003,
                    "order_no": "ORDER_20251004",
                    "status": "delivered",
                    "total_amount": Decimal("1999.00"),
                    "recipient_masked": "王*",
                    "address_masked": "广州市天河区****",
                    "created_at": dt(2025, 12, 15, 10, 0),
                    "updated_at": dt(2025, 12, 20, 16, 0),
                    "shipped_at": dt(2025, 12, 16, 9, 0),
                    "delivered_at": dt(2025, 12, 20, 14, 0),
                    "cancelled_at": None,
                },
                {
                    "id": order_5,
                    "tenant_id": tenant_south,
                    "user_id": user_parent_003,
                    "order_no": "ORDER_20251005",
                    "status": "pending",
                    "total_amount": Decimal("199.00"),
                    "recipient_masked": "王*",
                    "address_masked": "广州市天河区****",
                    "created_at": dt(2026, 10, 26, 8, 0),
                    "updated_at": dt(2026, 10, 26, 8, 0),
                    "shipped_at": None,
                    "delivered_at": None,
                    "cancelled_at": None,
                },
            ],
        )

        await session.execute(
            insert(OrderItem),
            [
                {
                    "id": pk("order_item:ORDER_20251001:1"),
                    "order_id": order_1,
                    "product_name": "学习机 X5",
                    "product_model": "X5",
                    "quantity": 1,
                    "amount": Decimal("3299.00"),
                },
                {
                    "id": pk("order_item:ORDER_20251002:1"),
                    "order_id": order_2,
                    "product_name": "学习机 X5",
                    "product_model": "X5",
                    "quantity": 1,
                    "amount": Decimal("3299.00"),
                },
                {
                    "id": pk("order_item:ORDER_20251002:2"),
                    "order_id": order_2,
                    "product_name": "X5 专用保护壳",
                    "product_model": "X5-CASE",
                    "quantity": 1,
                    "amount": Decimal("99.00"),
                },
                {
                    "id": pk("order_item:ORDER_20251003:1"),
                    "order_id": order_3,
                    "product_name": "学习机 X6",
                    "product_model": "X6",
                    "quantity": 1,
                    "amount": Decimal("4999.00"),
                },
                {
                    "id": pk("order_item:ORDER_20251004:1"),
                    "order_id": order_4,
                    "product_name": "学习机 S3",
                    "product_model": "S3",
                    "quantity": 1,
                    "amount": Decimal("1999.00"),
                },
                {
                    "id": pk("order_item:ORDER_20251005:1"),
                    "order_id": order_5,
                    "product_name": "S3 配件套装",
                    "product_model": "S3-KIT",
                    "quantity": 1,
                    "amount": Decimal("199.00"),
                },
            ],
        )

        await session.execute(
            insert(LogisticsEvent),
            [
                {
                    "order_id": order_1,
                    "carrier": "顺丰速运",
                    "tracking_no": "SF1000000001",
                    "status": "picked_up",
                    "description": "快件已由顺丰揽收",
                    "occurred_at": dt(2025, 10, 2, 10, 0),
                },
                {
                    "order_id": order_1,
                    "carrier": "顺丰速运",
                    "tracking_no": "SF1000000001",
                    "status": "delivered",
                    "description": "快件已签收",
                    "occurred_at": dt(2025, 10, 5, 15, 0),
                },
                {
                    "order_id": order_2,
                    "carrier": "京东物流",
                    "tracking_no": "JD2000000002",
                    "status": "picked_up",
                    "description": "快件已由京东物流揽收",
                    "occurred_at": dt(2026, 10, 24, 11, 0),
                },
                {
                    "order_id": order_2,
                    "carrier": "京东物流",
                    "tracking_no": "JD2000000002",
                    "status": "in_transit",
                    "description": "快件已到达北京分拣中心",
                    "occurred_at": dt(2026, 10, 25, 9, 0),
                },
                {
                    "order_id": order_4,
                    "carrier": "中通快递",
                    "tracking_no": "ZT3000000004",
                    "status": "delivered",
                    "description": "快件已签收",
                    "occurred_at": dt(2025, 12, 20, 14, 0),
                },
            ],
        )

        # --- 维修工单 -----------------------------------------------------
        rep_1 = pk("repair:REP_20251001")
        rep_2 = pk("repair:REP_20251002")
        rep_3 = pk("repair:REP_20251003")
        rep_4 = pk("repair:REP_20251004")
        rep_5 = pk("repair:REP_20251005")

        await session.execute(
            insert(RepairTicket),
            [
                {
                    "id": rep_1,
                    "tenant_id": tenant_north,
                    "repair_no": "REP_20251001",
                    "user_id": user_parent_001,
                    "conversation_id": None,
                    "device_id": dev_1,
                    "device_sn": "SNX5000001",
                    "fault_type": "screen_flicker",
                    "description": "屏幕偶发闪烁，重启后仍存在。",
                    "status": "completed",
                    "mode": "in_store",
                    "store_id": sc_north,
                    "warranty_status": "in_warranty",
                    "quote_amount": None,
                    "contact": "138****0001",
                    "created_at": dt(2026, 8, 1, 10, 0),
                    "updated_at": dt(2026, 8, 6, 17, 0),
                    "closed_at": dt(2026, 8, 6, 17, 0),
                },
                {
                    "id": rep_2,
                    "tenant_id": tenant_north,
                    "repair_no": "REP_20251002",
                    "user_id": user_parent_002,
                    "conversation_id": None,
                    "device_id": dev_2,
                    "device_sn": "SNX5000002",
                    "fault_type": "no_power",
                    "description": "设备无法开机，充电无反应。",
                    "status": "diagnosing",
                    "mode": "mail_in",
                    "store_id": sc_north,
                    "warranty_status": "out_of_warranty",
                    "quote_amount": None,
                    "contact": "139****0002",
                    "created_at": dt(2026, 10, 20, 9, 30),
                    "updated_at": dt(2026, 10, 22, 14, 0),
                    "closed_at": None,
                },
                {
                    "id": rep_3,
                    "tenant_id": tenant_north,
                    "repair_no": "REP_20251003",
                    "user_id": user_parent_001,
                    "conversation_id": None,
                    "device_id": dev_3,
                    "device_sn": "SNX6000001",
                    "fault_type": "touch_failure",
                    "description": "屏幕下半部分触控无响应。",
                    "status": "created",
                    "mode": "in_store",
                    "store_id": sc_north,
                    "warranty_status": "in_warranty",
                    "quote_amount": None,
                    "contact": "138****0001",
                    "created_at": dt(2026, 10, 25, 20, 0),
                    "updated_at": dt(2026, 10, 25, 20, 0),
                    "closed_at": None,
                },
                {
                    "id": rep_4,
                    "tenant_id": tenant_south,
                    "repair_no": "REP_20251004",
                    "user_id": user_parent_003,
                    "conversation_id": None,
                    "device_id": dev_4,
                    "device_sn": "SNS3000001",
                    "fault_type": "battery",
                    "description": "满电后续航不足两小时。",
                    "status": "repairing",
                    "mode": "in_store",
                    "store_id": sc_south,
                    "warranty_status": "in_warranty",
                    "quote_amount": Decimal("0.00"),
                    "contact": "137****0003",
                    "created_at": dt(2026, 9, 15, 11, 0),
                    "updated_at": dt(2026, 9, 18, 10, 0),
                    "closed_at": None,
                },
                {
                    "id": rep_5,
                    "tenant_id": tenant_south,
                    "repair_no": "REP_20251005",
                    "user_id": user_parent_003,
                    "conversation_id": None,
                    "device_id": dev_5,
                    "device_sn": "SNS3000002",
                    "fault_type": "speaker",
                    "description": "扬声器有杂音。",
                    "status": "cancelled",
                    "mode": "mail_in",
                    "store_id": sc_south,
                    "warranty_status": "out_of_warranty",
                    "quote_amount": Decimal("180.00"),
                    "contact": "137****0003",
                    "created_at": dt(2026, 7, 1, 9, 0),
                    "updated_at": dt(2026, 7, 2, 9, 0),
                    "closed_at": dt(2026, 7, 2, 9, 0),
                },
            ],
        )

        await session.execute(
            insert(RepairEvent),
            [
                {
                    "repair_id": rep_1,
                    "from_status": None,
                    "to_status": "created",
                    "operator_id": user_parent_001,
                    "note": "家长通过客服创建工单",
                    "attachments": [],
                    "created_at": dt(2026, 8, 1, 10, 0),
                },
                {
                    "repair_id": rep_1,
                    "from_status": "created",
                    "to_status": "completed",
                    "operator_id": user_agent_001,
                    "note": "更换屏幕排线，已交付",
                    "attachments": [],
                    "created_at": dt(2026, 8, 6, 17, 0),
                },
                {
                    "repair_id": rep_2,
                    "from_status": None,
                    "to_status": "created",
                    "operator_id": user_parent_002,
                    "note": "家长通过客服创建工单",
                    "attachments": [],
                    "created_at": dt(2026, 10, 20, 9, 30),
                },
                {
                    "repair_id": rep_3,
                    "from_status": None,
                    "to_status": "created",
                    "operator_id": user_parent_001,
                    "note": "家长通过客服创建工单",
                    "attachments": [],
                    "created_at": dt(2026, 10, 25, 20, 0),
                },
                {
                    "repair_id": rep_4,
                    "from_status": "created",
                    "to_status": "repairing",
                    "operator_id": user_agent_002,
                    "note": "检测为电池老化，保修内更换",
                    "attachments": [],
                    "created_at": dt(2026, 9, 18, 10, 0),
                },
            ],
        )

        # --- 会话 / 消息 / 转人工 ------------------------------------------
        conv_1 = pk("conversation:conv_20251001")
        conv_2 = pk("conversation:conv_20251002")

        await session.execute(
            insert(Conversation),
            [
                {
                    "id": conv_1,
                    "tenant_id": tenant_north,
                    "user_id": user_parent_001,
                    "channel": "app",
                    "source": "device_detail",
                    "subject_type": "parent",
                    "guardian_user_id": user_parent_001,
                    "mode": "CLOSED",
                    "priority": "P2",
                    "skill_group_id": sg_north_after,
                    "context": {"device_sn": "SNX5000001", "entry": "after_sales"},
                    "close_reason": "resolved",
                    "started_at": dt(2026, 10, 24, 9, 0),
                    "last_active_at": dt(2026, 10, 24, 9, 12),
                    "ended_at": dt(2026, 10, 24, 9, 12),
                    "input_revision": 1,
                    "answered_revision": 1,
                },
                {
                    "id": conv_2,
                    "tenant_id": tenant_north,
                    "user_id": user_parent_002,
                    "channel": "app",
                    "source": "order_detail",
                    "subject_type": "parent",
                    "guardian_user_id": user_parent_002,
                    "mode": "QUEUED",
                    "priority": "P1",
                    "skill_group_id": sg_north_complaint,
                    "context": {"order_no": "ORDER_20251002", "sentiment": "negative"},
                    "close_reason": None,
                    "started_at": dt(2026, 10, 25, 18, 0),
                    "last_active_at": dt(2026, 10, 25, 18, 5),
                    "ended_at": None,
                    "input_revision": 1,
                    "answered_revision": 0,
                },
            ],
        )

        await session.execute(
            insert(Message),
            [
                {
                    "message_id": pk("message:conv_1:1"),
                    "tenant_id": tenant_north,
                    "conversation_id": conv_1,
                    "role": "customer",
                    "message_type": "text",
                    "content": {"text": "学习机屏幕偶尔闪烁，还在保修期吗？"},
                    "input_revision": 1,
                    "agent_run_id": None,
                    "agent_outcome_seq": None,
                    "created_at": dt(2026, 10, 24, 9, 0),
                },
                {
                    "message_id": pk("message:conv_1:2"),
                    "tenant_id": tenant_north,
                    "conversation_id": conv_1,
                    "role": "ai",
                    "message_type": "text",
                    "content": {
                        "text": "已查到 SNX5000001 在保，保修至 2027-03-14。建议先升级固件并重启；若仍闪烁，可到北京朝阳服务中心检测。"
                    },
                    "input_revision": None,
                    "agent_run_id": "seed-run-conv-1",
                    "agent_outcome_seq": 1,
                    "created_at": dt(2026, 10, 24, 9, 1),
                },
                {
                    "message_id": pk("message:conv_2:1"),
                    "tenant_id": tenant_north,
                    "conversation_id": conv_2,
                    "role": "customer",
                    "message_type": "text",
                    "content": {"text": "订单说昨天发货，但物流一直没更新，太耽误孩子用了。"},
                    "input_revision": 1,
                    "agent_run_id": None,
                    "agent_outcome_seq": None,
                    "created_at": dt(2026, 10, 25, 18, 0),
                },
            ],
        )

        handoff_1 = pk("handoff:conv_2")
        await session.execute(
            insert(Handoff),
            [
                {
                    "id": handoff_1,
                    "tenant_id": tenant_north,
                    "conversation_id": conv_2,
                    "user_id": user_parent_002,
                    "summary": "家长反馈订单物流停滞，情绪负面，需人工跟进。",
                    "status": "waiting",
                    "assigned_agent_id": None,
                    "skill_group_id": sg_north_complaint,
                    "priority": "P1",
                    "sla_due_at": dt(2026, 10, 25, 18, 30),
                    "created_at": dt(2026, 10, 25, 18, 5),
                    "accepted_at": None,
                    "resolved_at": None,
                    "close_reason": None,
                },
            ],
        )

        await session.execute(
            insert(HandoffEvent),
            [
                {
                    "handoff_id": handoff_1,
                    "from_status": None,
                    "to_status": "waiting",
                    "operator_id": None,
                    "note": "AI 触发转人工",
                    "created_at": dt(2026, 10, 25, 18, 5),
                },
            ],
        )

        await session.execute(
            insert(CsatSurvey),
            [
                {
                    "id": pk("csat:conv_1"),
                    "tenant_id": tenant_north,
                    "conversation_id": conv_1,
                    "handoff_id": None,
                    "score": 5,
                    "tags": ["quick", "clear"],
                    "comment": "回答很快，保修信息准确。",
                    "created_at": dt(2026, 10, 24, 9, 15),
                },
            ],
        )

        await session.execute(
            insert(CannedReply),
            [
                {
                    "id": pk("canned:logistics_delay"),
                    "tenant_id": tenant_north,
                    "category": "logistics",
                    "title": "物流停滞安抚",
                    "content": "已为您联系承运方核查，预计 24 小时内更新物流，请您留意短信通知。",
                    "variables": [],
                    "status": "active",
                },
                {
                    "id": pk("canned:warranty_check"),
                    "tenant_id": tenant_north,
                    "category": "warranty",
                    "title": "保修查询说明",
                    "content": "已根据设备 SN 查询保修状态：{{warranty_status}}，保修截止 {{warranty_end}}。",
                    "variables": ["warranty_status", "warranty_end"],
                    "status": "active",
                },
                {
                    "id": pk("canned:repair_created"),
                    "tenant_id": tenant_south,
                    "category": "repair",
                    "title": "维修工单已创建",
                    "content": "已为您创建维修工单 {{repair_no}}，请留意服务网点联系。",
                    "variables": ["repair_no"],
                    "status": "active",
                },
            ],
        )

        await session.execute(
            insert(AuditLog),
            [
                {
                    "tenant_id": tenant_hq,
                    "actor_id": user_admin_001,
                    "action": "tenant.seed",
                    "object_type": "tenant",
                    "object_id": "hq",
                    "before": None,
                    "after": {"tenants": ["hq", "dlr_north", "dlr_south"]},
                    "ip": None,
                    "created_at": dt(2026, 10, 26, 9, 0),
                },
            ],
        )

        await session.commit()

    print("Seed 完成：3 租户 / 7 用户 / 3 技能组 / 5 设备 / 5 订单 / 5 维修单 / 2 会话。")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    # psycopg 异步模式在 Windows 上只能用 SelectorEventLoop。
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
