"""技能目录：按售后场景收窄模型可见工具。"""

from __future__ import annotations

from edu_ai.agent.skills.definition import SkillCode, SkillDefinition


class SkillCatalog:
    def __init__(self, definitions: tuple[SkillDefinition, ...]):
        self.definitions = {definition.code: definition for definition in definitions}

    def get_skill(self, skill_code: SkillCode) -> SkillDefinition:
        return self.definitions[skill_code]

    def render_index(self) -> str:
        return "\n".join(
            f"- {skill.code}: {skill.description}"
            for skill in self.definitions.values()
        )


SKILL_CATALOG = SkillCatalog(
    (
        SkillDefinition(
            code=SkillCode.ORDER_SERVICE,
            description="订单列表、订单状态、金额、取消未发货订单",
            guidance=(
                "用户没有提供订单号时先调用 list_orders，再根据用户描述定位订单。",
                "订单状态、金额和商品信息只能来自 get_order 的成功结果。",
                "只有待付款或已付款且未发货的订单可以取消；准备取消前必须让用户明确确认。",
                "取消工具只准备动作，确认执行由客服系统完成，不得提前声称订单已取消。",
            ),
            tools=("list_orders", "get_order", "prepare_cancel_order"),
        ),
        SkillDefinition(
            code=SkillCode.LOGISTICS_SERVICE,
            description="订单发货状态、承运公司、运单号和物流轨迹",
            guidance=(
                "用户没有提供订单号时先调用 list_orders。",
                "订单基础信息使用 get_order，物流轨迹使用 get_logistics。",
                "承运公司、运单号、物流节点只能来自 get_logistics 的成功结果。",
                "不得承诺具体送达时间或赔偿金额；物流停滞超过 48 小时可建议转人工。",
            ),
            tools=("list_orders", "get_order", "get_logistics"),
        ),
        SkillDefinition(
            code=SkillCode.DEVICE_SERVICE,
            description="设备 SN、型号、激活时间、固件版本和保修状态查询",
            guidance=(
                "用户没有提供 SN 时先调用 list_devices。",
                "设备型号、保修起止时间和保修状态只能来自 get_device 的成功结果。",
                "保修状态以工具返回的 warranty_status 为准，不得口头承诺保修。",
            ),
            tools=("list_devices", "get_device"),
        ),
        SkillDefinition(
            code=SkillCode.REPAIR_SERVICE,
            description="故障自检、维修工单查询与新建报修工单",
            guidance=(
                "先查询设备确认 SN 归属和保修状态；用户未提供 SN 时使用 list_devices。",
                "报修前给出可执行的自检步骤；自检无效或用户明确要求报修时准备维修工单。",
                "新建工单前必须收集设备 SN、故障现象和维修方式；缺少信息时使用 CLARIFY。",
                "prepare_repair_ticket 只准备动作，不得提前声称工单已创建；最终结果以客服系统确认为准。",
            ),
            tools=(
                "list_devices",
                "get_device",
                "list_repairs",
                "get_repair",
                "prepare_repair_ticket",
            ),
        ),
        SkillDefinition(
            code=SkillCode.POLICY_SERVICE,
            description="保修政策、维修流程、物流口径、隐私与取消规则等知识说明",
            guidance=(
                "用户询问政策、流程或帮助说明时必须先调用 search_knowledge。",
                "政策结论只能来自知识检索结果，并标明是通用规则。",
                "知识内容不能用于判断用户实际订单、设备或工单状态。",
                "没有检索到内容时明确说明，不得编造规则。",
            ),
            tools=("search_knowledge",),
        ),
        SkillDefinition(
            code=SkillCode.COMPLAINT_SERVICE,
            description="投诉、重复维修、退款争议、监管投诉等需要人工介入的场景",
            guidance=(
                "先共情并复述问题，再给出可执行的下一步。",
                "用户明确要求人工，或提到投诉、曝光、12315、反复维修未解决时使用 REQUEST_HANDOFF。",
                "投诉场景不要为了收集信息反复调用查询工具；一次查询足够，随后直接转人工。",
                "投诉默认 P1，涉及媒体或监管升级为 P0；不得承诺赔偿金额。",
                "可以查询订单获取上下文，但不得在未确认时声称已退款或已处理。",
            ),
            tools=("list_orders", "get_order"),
        ),
    )
)
