"""写操作工具：只准备动作，由客服系统确认后执行。"""

from __future__ import annotations

from typing import Annotated, Literal

from langchain.tools import ToolRuntime, tool

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.tools.cs_client import (
    CustomerServiceClient,
    CustomerServiceError,
    quote_resource,
)
from edu_ai.agent.tools.executor import ToolExecutor
from edu_ai.agent.tools.result import (
    ActionPreparedData,
    DeviceData,
    OrderDetailData,
    ToolBusinessError,
)
from edu_ai.services.actions import CANCEL_ACTION, REPAIR_ACTION, ActionService

tool_executor = ToolExecutor()

CANCEL_CONFIRMATION_KEYWORDS = (
    "取消订单",
    "帮我取消",
    "确认取消",
    "申请取消",
    "不要了",
    "退掉",
    "别发了",
)


def _has_cancel_confirmation(texts: tuple[str, ...]) -> bool:
    return any(
        keyword in text for text in texts for keyword in CANCEL_CONFIRMATION_KEYWORDS
    )


@tool
async def prepare_repair_ticket(
    device_sn: Annotated[str, "需要报修的学习机 SN，例如 SNX5000001"],
    fault_type: Annotated[
        str, "故障类型，例如 无法开机、屏幕闪烁、触控失灵、电池异常"
    ],
    description: Annotated[str, "用户描述的故障现象、发生时间和是否进液摔碰"],
    runtime: ToolRuntime[AgentRuntimeContext],
    mode: Annotated[
        Literal["mail_in", "in_store", "on_site"], "维修方式"
    ] = "mail_in",
    contact: Annotated[str | None, "联系人手机号，用户提供时填写"] = None,
) -> str:
    """准备一张维修工单，等待客服系统确认后生效。

    调用前必须已经和用户确认设备 SN、故障现象；缺少信息时不要调用，改用 CLARIFY。
    该工具不会立即创建工单，回复中不得声称工单已经创建成功。
    """
    if runtime.tool_call_id is None:
        raise RuntimeError("报修工具缺少调用编号")

    normalized_sn = device_sn.strip().upper()
    normalized_fault = fault_type.strip()
    normalized_description = description.strip()
    if not normalized_sn or not normalized_fault or not normalized_description:
        raise ToolBusinessError(
            "REPAIR_INFO_INCOMPLETE", "报修信息不完整，请先补齐设备 SN、故障类型和现象"
        )

    client = CustomerServiceClient(runtime.context)

    async def prepare() -> ActionPreparedData:
        try:
            device = DeviceData.model_validate(
                await client.get(
                    f"/internal/v1/tools/devices/{quote_resource(normalized_sn)}"
                )
            )
        except CustomerServiceError as exc:
            if exc.status_code == 404:
                raise ToolBusinessError(
                    "DEVICE_NOT_FOUND", "设备不存在或不属于当前用户，无法报修"
                ) from exc
            raise
        payload = {
            "device_sn": device.sn,
            "fault_type": normalized_fault,
            "description": normalized_description,
            "mode": mode,
            "contact": contact,
        }
        prepared = await ActionService.prepare(
            runtime.context,
            action_type=REPAIR_ACTION,
            resource=device.sn,
            payload=payload,
        )
        prepared.detail = {
            "device_sn": device.sn,
            "fault_type": normalized_fault,
            "mode": mode,
            "warranty_status": device.warranty_status,
        }
        return prepared

    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="prepare_repair_ticket",
        arguments={
            "device_sn": normalized_sn,
            "fault_type": normalized_fault,
            "description": normalized_description,
            "mode": mode,
            "contact": contact,
        },
        operation=prepare,
        output_schema=ActionPreparedData,
    )


@tool
async def prepare_cancel_order(
    order_no: Annotated[str, "需要取消的订单编号，例如 ORDER_20251001"],
    runtime: ToolRuntime[AgentRuntimeContext],
    reason: Annotated[str | None, "用户给出的取消原因"] = None,
) -> str:
    """准备取消未发货订单，等待客服系统确认后执行。

    只有用户明确说出取消订单、不要了、退掉等确认意图时才能调用；
    已发货或已签收的订单不能取消，应引导拒收或申请退货。
    """
    if runtime.tool_call_id is None:
        raise RuntimeError("取消订单工具缺少调用编号")

    normalized = order_no.strip().upper().replace("-", "_")
    if not _has_cancel_confirmation(runtime.context.customer_texts):
        raise ToolBusinessError(
            "CONFIRMATION_REQUIRED",
            "用户还没有明确确认取消订单，请先向用户确认后再操作",
        )

    client = CustomerServiceClient(runtime.context)

    async def prepare() -> ActionPreparedData:
        try:
            order = OrderDetailData.model_validate(
                await client.get(
                    f"/internal/v1/tools/orders/{quote_resource(normalized)}"
                )
            )
        except CustomerServiceError as exc:
            if exc.status_code == 404:
                raise ToolBusinessError(
                    "ORDER_NOT_FOUND", "订单不存在或不属于当前用户"
                ) from exc
            raise
        if order.status not in ("pending", "paid"):
            label = order.status_label or order.status
            raise ToolBusinessError(
                "ORDER_NOT_CANCELLABLE",
                f"订单 {order.order_no} 当前为{label}，不能直接取消",
            )
        prepared = await ActionService.prepare(
            runtime.context,
            action_type=CANCEL_ACTION,
            resource=order.order_no,
            payload={"order_no": order.order_no, "reason": reason},
        )
        prepared.detail = {
            "order_no": order.order_no,
            "status": order.status,
            "status_label": order.status_label,
        }
        return prepared

    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="prepare_cancel_order",
        arguments={"order_no": normalized, "reason": reason},
        operation=prepare,
        output_schema=ActionPreparedData,
    )
