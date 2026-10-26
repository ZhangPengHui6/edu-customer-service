"""客服端接口：工单队列、接入、回复与结束。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from edu_cs.api.deps import SessionDep, get_staff_identity
from edu_cs.models import User
from edu_cs.repositories.catalog import CatalogRepository
from edu_cs.repositories.conversations import ConversationRepository
from edu_cs.schemas.catalog import DeviceOut, OrderOut, RepairOut
from edu_cs.schemas.staff import (
    HandoffActionResponse,
    HandoffEventItem,
    HandoffEventListResponse,
    HandoffListResponse,
    HandoffSummary,
    ResolveHandoffRequest,
    StaffCustomerOut,
    StaffCustomerStats,
    StaffHandoffContextResponse,
    StaffMessageRequest,
    StaffMessageResponse,
)
from edu_cs.security import Principal
from edu_cs.services import audit
from edu_cs.services.after_sales import AfterSalesService
from edu_cs.services.handoffs import HandoffService
from edu_cs.services.messages import MessageService

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])

StaffContext = Annotated[tuple[Principal, UUID], Depends(get_staff_identity)]


async def _audit_if_cross(
    session,
    principal: Principal,
    tenant_id: UUID,
    action: str,
    object_type: str,
    object_id: str,
) -> None:
    if tenant_id != principal.tenant_id:
        await audit.record(
            session,
            tenant_id=tenant_id,
            actor_id=principal.user_id,
            action="staff.cross_tenant_access",
            object_type=object_type,
            object_id=object_id,
            after={"action": action},
        )


@router.get("/handoffs", response_model=HandoffListResponse)
async def list_handoffs(
    context: StaffContext,
    session: SessionDep,
    status_filter: Annotated[str, Query(alias="status")] = "waiting,active",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HandoffListResponse:
    principal, tenant_id = context
    statuses = tuple(
        item.strip() for item in status_filter.split(",") if item.strip()
    )
    allowed = {"waiting", "active", "resolved", "closed", "cancelled"}
    if not statuses or any(item not in allowed for item in statuses):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="status 参数不合法"
        )
    await _audit_if_cross(session, principal, tenant_id, "handoff.list", "tenant", str(tenant_id))
    items = await HandoffService(session).list_for_staff(
        tenant_id, statuses=statuses, limit=limit
    )
    await session.commit()
    return HandoffListResponse(items=[HandoffSummary(**item) for item in items])


@router.post(
    "/handoffs/{handoff_id}/accept", response_model=HandoffActionResponse
)
async def accept_handoff(
    handoff_id: UUID, context: StaffContext, session: SessionDep
) -> HandoffActionResponse:
    principal, tenant_id = context
    await _audit_if_cross(session, principal, tenant_id, "handoff.accept", "handoff", str(handoff_id))
    result = await HandoffService(session).accept(principal, tenant_id, handoff_id)
    return HandoffActionResponse(**result)


@router.get(
    "/handoffs/{handoff_id}/context",
    response_model=StaffHandoffContextResponse,
)
async def handoff_context(
    handoff_id: UUID, context: StaffContext, session: SessionDep
) -> StaffHandoffContextResponse:
    principal, tenant_id = context
    await _audit_if_cross(
        session, principal, tenant_id, "handoff.context", "handoff", str(handoff_id)
    )
    handoff = await HandoffService(session).get_or_none(tenant_id, handoff_id)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在"
        )
    user = await session.get(User, handoff.user_id)
    if user is None or user.tenant_id != handoff.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在"
        )

    sales = AfterSalesService(session)
    orders = await sales.list_orders(handoff.tenant_id, handoff.user_id)
    devices = await sales.list_devices(handoff.tenant_id, handoff.user_id)
    repairs = await sales.list_repairs(handoff.tenant_id, handoff.user_id)
    result = StaffHandoffContextResponse(
        customer=StaffCustomerOut(
            id=user.id, name=user.name, phone_masked=user.phone_masked
        ),
        stats=StaffCustomerStats(
            orders=len(orders), devices=len(devices), repairs=len(repairs)
        ),
        orders=[OrderOut(**item) for item in orders[:10]],
        devices=[DeviceOut(**item) for item in devices[:10]],
        repairs=[RepairOut(**item) for item in repairs[:10]],
    )
    await session.commit()
    return result


@router.post(
    "/handoffs/{handoff_id}/resolve", response_model=HandoffActionResponse
)
async def resolve_handoff(
    handoff_id: UUID,
    payload: ResolveHandoffRequest,
    context: StaffContext,
    session: SessionDep,
) -> HandoffActionResponse:
    principal, tenant_id = context
    await _audit_if_cross(session, principal, tenant_id, "handoff.resolve", "handoff", str(handoff_id))
    result = await HandoffService(session).resolve(
        principal,
        tenant_id,
        handoff_id,
        close_reason=payload.close_reason,
        note=payload.note,
    )
    return HandoffActionResponse(**result)


@router.get(
    "/handoffs/{handoff_id}/events", response_model=HandoffEventListResponse
)
async def handoff_events(
    handoff_id: UUID, context: StaffContext, session: SessionDep
) -> HandoffEventListResponse:
    principal, tenant_id = context
    await _audit_if_cross(session, principal, tenant_id, "handoff.events", "handoff", str(handoff_id))
    items = await HandoffService(session).events(tenant_id, handoff_id)
    await session.commit()
    return HandoffEventListResponse(
        items=[HandoffEventItem(**item) for item in items]
    )


@router.post(
    "/handoffs/{handoff_id}/messages", response_model=StaffMessageResponse
)
async def send_staff_message(
    handoff_id: UUID,
    payload: StaffMessageRequest,
    context: StaffContext,
    session: SessionDep,
) -> StaffMessageResponse:
    principal, tenant_id = context
    handoff = await CatalogRepository(session).get_handoff(tenant_id, handoff_id)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在"
        )
    if handoff.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请先接入工单再回复",
        )
    if principal.role == "agent":
        agent = await CatalogRepository(session).get_agent_by_user(
            tenant_id, principal.user_id
        )
        if agent is None or handoff.assigned_agent_id != agent.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="工单已分配给其他客服",
            )

    conversation = await ConversationRepository(session).get_for_update(
        handoff.conversation_id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
        )
    message = await MessageService(session).save_staff_message(
        conversation,
        client_message_id=payload.client_message_id,
        text=payload.text,
        operator_id=principal.user_id,
    )
    await session.commit()
    await session.refresh(message)
    await _audit_if_cross(session, principal, tenant_id, "handoff.message", "handoff", str(handoff_id))
    await session.commit()
    return StaffMessageResponse(
        conversation_id=conversation.id,
        message_id=message.message_id,
        sequence=message.id,
        created_at=message.created_at,
    )
