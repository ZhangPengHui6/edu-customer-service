"""Agent 执行器：上下文编译、模型调用、输出校验与有限纠错。"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import SystemMessage
from pydantic import ValidationError

from edu_ai.agent.context import ContextCompiler
from edu_ai.agent.errors import (
    AgentExecutionError,
    AgentOutputValidationError,
    CorrectableErrorCode,
    TerminalErrorCode,
)
from edu_ai.agent.factory import create_support_agent
from edu_ai.agent.llm import ModelAdapter
from edu_ai.agent.output import AgentOutput, ReplyType
from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.agent.validators.output import AgentOutputValidator, ValidatedAgentOutput
from edu_ai.config import get_settings
from edu_ai.schemas.run import AgentRunRequest

logger = logging.getLogger(__name__)


class AgentExecutor:
    def __init__(self, output_validator: AgentOutputValidator):
        self.settings = get_settings()
        self.context_compiler = ContextCompiler()
        self.output_validator = output_validator

    async def execute(
        self,
        request: AgentRunRequest,
        runtime_context: AgentRuntimeContext,
    ) -> ValidatedAgentOutput:
        messages = self.context_compiler.compile_messages(request)
        usage_callback = UsageMetadataCallbackHandler()
        validated = await self._execute_with_correction(
            messages,
            runtime_context,
            usage_callback,
            vision=ContextCompiler.has_images(request),
        )
        return validated.model_copy(
            update={"token_usage": self._summarize_usage(usage_callback)}
        )

    async def _execute_with_correction(
        self,
        messages,
        runtime_context: AgentRuntimeContext,
        usage_callback: UsageMetadataCallbackHandler,
        *,
        vision: bool,
    ) -> ValidatedAgentOutput:
        current_messages = messages
        attempt = 0
        while True:
            try:
                raw_output = await self._invoke_agent(
                    current_messages, runtime_context, usage_callback, vision=vision
                )
                normalized = self._normalize(raw_output)
                return await self._validate(normalized, runtime_context)
            except ToolCallLimitExceededError as exc:
                logger.warning(
                    "tool call limit exceeded run=%s count=%s limit=%s tool=%s",
                    runtime_context.run_id,
                    exc.run_count,
                    exc.run_limit,
                    exc.tool_name,
                )
                return self._tool_limit_output()
            except AgentOutputValidationError as exc:
                is_last = attempt >= self.settings.max_correction_attempts - 1
                if is_last or not isinstance(exc.code, CorrectableErrorCode):
                    raise AgentExecutionError(exc.code, str(exc)) from exc
                current_messages = [
                    *raw_output["messages"],
                    self._correction_feedback(exc),
                ]
                attempt += 1

    async def _invoke_agent(
        self,
        messages,
        runtime_context: AgentRuntimeContext,
        usage_callback: UsageMetadataCallbackHandler,
        *,
        vision: bool,
    ) -> Any:
        agent = create_support_agent(vision=vision)
        try:
            return await agent.ainvoke(
                {"messages": messages},
                context=runtime_context,
                config={"callbacks": [usage_callback]},
            )
        except ToolCallLimitExceededError:
            raise
        except Exception as exc:
            logger.exception(
                "agent model invocation failed run=%s: %s",
                runtime_context.run_id,
                exc,
            )
            raise AgentExecutionError(
                TerminalErrorCode.MODEL_CALL_FAILED, "模型调用失败"
            ) from exc

    @staticmethod
    def _normalize(raw_output: Any) -> AgentOutput:
        try:
            return ModelAdapter.normalize_output(raw_output)
        except ValidationError as exc:
            raise AgentOutputValidationError(
                CorrectableErrorCode.MODEL_OUTPUT_INVALID,
                "模型返回的结构化结果不符合约定",
            ) from exc

    async def _validate(
        self, output: AgentOutput, runtime_context: AgentRuntimeContext
    ) -> ValidatedAgentOutput:
        try:
            return await self.output_validator.validate(
                output, runtime_context.run_pk
            )
        except AgentOutputValidationError:
            raise
        except Exception as exc:
            raise AgentExecutionError(
                TerminalErrorCode.OUTPUT_VALIDATION_FAILED, "Agent 输出校验失败"
            ) from exc

    @staticmethod
    def _tool_limit_output() -> ValidatedAgentOutput:
        return ValidatedAgentOutput(
            reply_type=ReplyType.DECLINE,
            reply_content=(
                "这次查询需要的信息较多，为避免反复查询打扰您，"
                "建议转人工客服继续处理。您也可以稍后重新描述问题再试一次。"
            ),
        )

    @staticmethod
    def _correction_feedback(error: AgentOutputValidationError) -> SystemMessage:
        return SystemMessage(
            content=(
                "上一次最终回复未通过服务端校验："
                f"{error}。请只根据成功的工具结果重新生成回复；"
                "无法确认的业务事实不要回答，也不要声称已经执行写操作。"
            )
        )

    @staticmethod
    def _summarize_usage(
        usage_callback: UsageMetadataCallbackHandler,
    ) -> dict[str, int]:
        items = list(usage_callback.usage_metadata.values())
        return {
            "input_tokens": sum(item.get("input_tokens", 0) for item in items),
            "output_tokens": sum(item.get("output_tokens", 0) for item in items),
        }
