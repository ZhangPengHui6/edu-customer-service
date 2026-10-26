"""模型适配。"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from edu_ai.agent.output import AgentOutput
from edu_ai.config import get_settings


class ModelAdapter:
    @classmethod
    def create_model(cls, *, vision: bool = False):
        settings = get_settings()
        return ChatOpenAI(
            model=settings.vision_model if vision else settings.main_model,
            base_url=settings.dashscope_base_url,
            api_key=settings.dashscope_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
            use_responses_api=False,
            extra_body={"enable_thinking": settings.llm_thinking_enabled},
        )

    @classmethod
    def create_fast_model(cls):
        """轻量模型：意图识别等短任务，不参与主对话。"""
        settings = get_settings()
        return ChatOpenAI(
            model=settings.fast_model,
            base_url=settings.dashscope_base_url,
            api_key=settings.dashscope_api_key,
            temperature=0.0,
            timeout=settings.llm_timeout_seconds,
            max_tokens=512,
            use_responses_api=False,
            extra_body={"enable_thinking": False},
        )

    @staticmethod
    def normalize_output(value: Any) -> AgentOutput:
        structured = (
            value.get("structured_response")
            if isinstance(value, dict)
            else value
        )
        if isinstance(structured, AgentOutput):
            return structured
        return AgentOutput.model_validate(structured)
