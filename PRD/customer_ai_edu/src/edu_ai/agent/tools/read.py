"""只读业务工具。"""

from __future__ import annotations

from typing import Annotated

from langchain.tools import ToolRuntime, tool

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.tools.cs_client import (
    CustomerServiceClient,
    CustomerServiceError,
    quote_resource,
)
from edu_ai.agent.tools.executor import ToolExecutor
from edu_ai.agent.tools.result import (
    DeviceData,
    DeviceListData,
    KnowledgeHit,
    LogisticsData,
    OrderDetailData,
    OrderListData,
    RepairDetailData,
    RepairListData,
    ToolBusinessError,
)
from edu_ai.services.knowledge import knowledge_service

tool_executor = ToolExecutor()


def _guard_not_found(code: str, message: str, operation):
    """把资源不存在转成业务失败，让模型用固定口径回复而不是报服务故障。"""

    async def guarded():
        try:
            return await operation()
        except CustomerServiceError as exc:
            if exc.status_code == 404:
                raise ToolBusinessError(code, message) from exc
            raise

    return guarded


def _normalize_order_no(order_no: str) -> str:
    return order_no.strip().upper().replace("-", "_")


def _normalize_sn(sn: str) -> str:
    return sn.strip().upper()


@tool
async def list_orders(runtime: ToolRuntime[AgentRuntimeContext]) -> str:
    """查询当前用户的订单列表。用户没有提供订单号时调用。只读，不执行取消。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("订单列表工具缺少调用编号")
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="list_orders",
        arguments={},
        operation=lambda: client.get("/internal/v1/tools/orders"),
        output_schema=OrderListData,
    )


@tool
async def get_order(
    order_no: Annotated[str, "订单编号，例如 ORDER_20251001"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """查询当前用户的一条订单详情，包含状态、金额、商品和物流节点。只读。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("订单详情工具缺少调用编号")
    normalized = _normalize_order_no(order_no)
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="get_order",
        arguments={"order_no": normalized},
        operation=_guard_not_found(
            "ORDER_NOT_FOUND",
            f"没有找到订单 {normalized}，请核对订单号，或确认是否属于当前账号",
            lambda: client.get(
                f"/internal/v1/tools/orders/{quote_resource(normalized)}"
            ),
        ),
        output_schema=OrderDetailData,
    )


@tool
async def get_logistics(
    order_no: Annotated[str, "订单编号，例如 ORDER_20251001"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """查询一个订单的承运公司、运单号、最新状态和物流轨迹。只读。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("物流查询工具缺少调用编号")
    normalized = _normalize_order_no(order_no)
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="get_logistics",
        arguments={"order_no": normalized},
        operation=_guard_not_found(
            "ORDER_NOT_FOUND",
            f"没有找到订单 {normalized} 的物流信息，请核对订单号，或确认是否属于当前账号",
            lambda: client.get(
                f"/internal/v1/tools/orders/{quote_resource(normalized)}/logistics"
            ),
        ),
        output_schema=LogisticsData,
    )


@tool
async def list_devices(runtime: ToolRuntime[AgentRuntimeContext]) -> str:
    """查询当前用户绑定或名下的学习机设备列表。用户没有提供 SN 时调用。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("设备列表工具缺少调用编号")
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="list_devices",
        arguments={},
        operation=lambda: client.get("/internal/v1/tools/devices"),
        output_schema=DeviceListData,
    )


@tool
async def get_device(
    sn: Annotated[str, "设备 SN，例如 SNX5000001"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """查询一台学习机的型号、激活时间、固件版本和保修状态。只读。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("设备详情工具缺少调用编号")
    normalized = _normalize_sn(sn)
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="get_device",
        arguments={"sn": normalized},
        operation=_guard_not_found(
            "DEVICE_NOT_FOUND",
            f"没有找到设备 {normalized}，请核对设备背面的 SN，或确认是否已绑定当前账号",
            lambda: client.get(
                f"/internal/v1/tools/devices/{quote_resource(normalized)}"
            ),
        ),
        output_schema=DeviceData,
    )


@tool
async def list_repairs(runtime: ToolRuntime[AgentRuntimeContext]) -> str:
    """查询当前用户的维修工单列表。用户没有提供维修单号时调用。只读。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("维修列表工具缺少调用编号")
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="list_repairs",
        arguments={},
        operation=lambda: client.get("/internal/v1/tools/repairs"),
        output_schema=RepairListData,
    )


@tool
async def get_repair(
    repair_no: Annotated[str, "维修工单编号，例如 REP_20251001"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """查询当前用户的一条维修工单状态和进度。只读。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("维修详情工具缺少调用编号")
    normalized = repair_no.strip().upper().replace("-", "_")
    client = CustomerServiceClient(runtime.context)
    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="get_repair",
        arguments={"repair_no": normalized},
        operation=_guard_not_found(
            "REPAIR_NOT_FOUND",
            f"没有找到维修工单 {normalized}，请核对维修单号，或确认是否属于当前账号",
            lambda: client.get(
                f"/internal/v1/tools/repairs/{quote_resource(normalized)}"
            ),
        ),
        output_schema=RepairDetailData,
    )


@tool
async def search_knowledge(
    query: Annotated[str, "需要查询的保修政策、维修流程、物流口径或隐私规则"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """检索当前租户和总部发布的售后知识。政策结论必须以此工具结果为依据。"""
    if runtime.tool_call_id is None:
        raise RuntimeError("知识检索工具缺少调用编号")
    normalized = query.strip()

    async def search() -> list[KnowledgeHit]:
        hits = await knowledge_service.search(
            normalized, runtime.context.tenant_id
        )
        if not hits:
            return []
        return hits

    return await tool_executor.execute(
        runtime_context=runtime.context,
        tool_call_id=runtime.tool_call_id,
        tool_name="search_knowledge",
        arguments={"query": normalized},
        operation=search,
        output_schema=list[KnowledgeHit],
    )
