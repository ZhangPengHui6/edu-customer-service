"""工具目录。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from langchain_core.tools import BaseTool

from edu_ai.agent.tools.read import (
    get_device,
    get_logistics,
    get_order,
    get_repair,
    list_devices,
    list_orders,
    list_repairs,
    search_knowledge,
)
from edu_ai.agent.tools.skill import load_skill
from edu_ai.agent.tools.write import prepare_cancel_order, prepare_repair_ticket


class ToolCategory(StrEnum):
    BUSINESS = "BUSINESS"
    KNOWLEDGE = "KNOWLEDGE"
    GUIDANCE = "GUIDANCE"


@dataclass(frozen=True)
class ToolDefinition:
    tool: BaseTool
    category: ToolCategory


class ToolCatalog:
    def __init__(self, definitions: tuple[ToolDefinition, ...]):
        self.definitions = {definition.tool.name: definition for definition in definitions}

    def get_agent_tools(self) -> list[BaseTool]:
        return [definition.tool for definition in self.definitions.values()]

    def get_tool_category(self, tool_name: str) -> ToolCategory:
        return self.definitions[tool_name].category


TOOL_CATALOG = ToolCatalog(
    (
        ToolDefinition(list_orders, ToolCategory.BUSINESS),
        ToolDefinition(get_order, ToolCategory.BUSINESS),
        ToolDefinition(get_logistics, ToolCategory.BUSINESS),
        ToolDefinition(list_devices, ToolCategory.BUSINESS),
        ToolDefinition(get_device, ToolCategory.BUSINESS),
        ToolDefinition(list_repairs, ToolCategory.BUSINESS),
        ToolDefinition(get_repair, ToolCategory.BUSINESS),
        ToolDefinition(prepare_repair_ticket, ToolCategory.BUSINESS),
        ToolDefinition(prepare_cancel_order, ToolCategory.BUSINESS),
        ToolDefinition(search_knowledge, ToolCategory.KNOWLEDGE),
        ToolDefinition(load_skill, ToolCategory.GUIDANCE),
    )
)
