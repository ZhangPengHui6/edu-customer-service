"""Agent 输出的服务端校验。"""

from __future__ import annotations

from pydantic import Field

from edu_ai.agent.errors import AgentOutputValidationError, CorrectableErrorCode
from edu_ai.agent.output import AgentOutput, ReplyType
from edu_ai.agent.tools.catalog import TOOL_CATALOG, ToolCategory
from edu_ai.agent.tools.result import ToolFailureType
from edu_ai.agent.tools.snapshot import ToolCallReader, ToolCallSnapshot
from edu_ai.agent.validators.facts import FactChecker


class AnswerValidationError(AgentOutputValidationError):
    pass


class ValidatedAgentOutput(AgentOutput):
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )


class AnswerValidator:
    business_failure_message = (
        "暂时无法取得可靠的订单、设备、物流或维修信息，"
        "因此现在不能确认结果，请稍后重试。"
    )

    def __init__(self) -> None:
        self.fact_checker = FactChecker()

    def validate(
        self, output: AgentOutput, tool_calls: tuple[ToolCallSnapshot, ...]
    ) -> AgentOutput:
        business_calls = self._get_business_calls(tool_calls)
        successful_calls = tuple(
            call for call in business_calls if call.success is True
        )
        if business_calls and not successful_calls:
            return self._build_failure_reply(output, business_calls)
        self._validate_facts(output.reply_content, successful_calls)
        return output

    @staticmethod
    def _get_business_calls(
        tool_calls: tuple[ToolCallSnapshot, ...],
    ) -> tuple[ToolCallSnapshot, ...]:
        return tuple(
            call
            for call in tool_calls
            if TOOL_CATALOG.get_tool_category(call.tool_name)
            in (ToolCategory.BUSINESS, ToolCategory.KNOWLEDGE)
        )

    def _build_failure_reply(
        self,
        output: AgentOutput,
        business_calls: tuple[ToolCallSnapshot, ...],
    ) -> AgentOutput:
        business_failures = tuple(
            call
            for call in business_calls
            if call.failure_type == ToolFailureType.BUSINESS
        )
        if len(business_failures) == len(business_calls):
            latest = business_failures[-1]
            message = (latest.result or {}).get("message") or self.business_failure_message
            return output.model_copy(
                update={
                    "reply_type": ReplyType.ANSWER,
                    "reply_content": message,
                    "handoff_request": None,
                }
            )
        return output.model_copy(
            update={
                "reply_type": ReplyType.DECLINE,
                "reply_content": self.business_failure_message,
                "handoff_request": None,
            }
        )

    def _validate_facts(
        self,
        reply_content: str,
        successful_calls: tuple[ToolCallSnapshot, ...],
    ) -> None:
        unsupported = self.fact_checker.get_unsupported_facts(
            reply_content, successful_calls
        )
        if unsupported:
            values = "、".join(fact.value for fact in unsupported)
            raise AnswerValidationError(
                CorrectableErrorCode.UNSUPPORTED_FACT,
                f"回复中的业务事实缺少工具支持：{values}",
            )


class AgentOutputValidator:
    def __init__(self, tool_call_reader: ToolCallReader):
        self.tool_call_reader = tool_call_reader
        self.answer_validator = AnswerValidator()

    async def validate(
        self, agent_output: AgentOutput, run_pk
    ) -> ValidatedAgentOutput:
        tool_calls = await self.tool_call_reader.read_by_run_pk(run_pk)
        checked = self.answer_validator.validate(agent_output, tool_calls)
        return ValidatedAgentOutput.model_validate(checked.model_dump())
