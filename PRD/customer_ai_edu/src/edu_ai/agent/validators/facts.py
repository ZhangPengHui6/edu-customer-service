"""业务事实抽取与校验。"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from edu_ai.agent.tools.snapshot import ToolCallSnapshot


class FactCategory(StrEnum):
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STATUS = "STATUS"


STATUS_CODE_MAP = {
    "待付款": "pending",
    "已付款": "paid",
    "已发货": "shipped",
    "已签收": "delivered",
    "已取消": "cancelled",
    "售后处理中": "after_sale",
    "已创建": "created",
    "已收件": "received",
    "检测中": "diagnosing",
    "已报价": "quoted",
    "维修中": "repairing",
    "已完成": "completed",
    "保修内": "in_warranty",
    "保外": "out_of_warranty",
    "运输中": "in_transit",
}


@dataclass(frozen=True)
class BusinessFact:
    category: FactCategory
    value: str


class FactExtractor:
    resource_id_pattern = re.compile(
        r"\b(?:ORDER|REP)[_-][A-Z0-9_-]+\b|\bSN[A-Z0-9]{6,}\b",
        re.IGNORECASE,
    )
    labeled_number_pattern = re.compile(
        r"(?:金额|总价|价格|数量|报价)"
        r"(?:为|是|有|剩余|还剩|：|:)?\s*"
        r"[¥￥]?\s*(\d+(?:\.\d+)?)"
    )
    unit_number_pattern = re.compile(
        r"(?:[¥￥]\s*(\d+(?:\.\d+)?)|"
        r"(\d+(?:\.\d+)?)\s*(?:元|件|个|台|套))"
    )
    status_labels = tuple(STATUS_CODE_MAP)

    @classmethod
    def extract(cls, reply_content: str) -> tuple[BusinessFact, ...]:
        facts: dict[BusinessFact, None] = {}
        for resource_id in cls.resource_id_pattern.findall(reply_content):
            normalized = resource_id.upper().replace("-", "_")
            facts[BusinessFact(FactCategory.IDENTIFIER, normalized)] = None
        for number in cls.labeled_number_pattern.findall(reply_content):
            facts[BusinessFact(FactCategory.NUMBER, number)] = None
        for first_number, second_number in cls.unit_number_pattern.findall(reply_content):
            facts[BusinessFact(FactCategory.NUMBER, first_number or second_number)] = None
        for status_label in cls.status_labels:
            if status_label in reply_content:
                facts[BusinessFact(FactCategory.STATUS, status_label)] = None
        return tuple(facts)


class FactChecker:
    number_pattern = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

    def get_unsupported_facts(
        self,
        reply_content: str,
        successful_tool_calls: tuple[ToolCallSnapshot, ...],
    ) -> tuple[BusinessFact, ...]:
        facts = FactExtractor.extract(reply_content)
        if not facts:
            return ()

        source_decimals: set[Decimal] = set()
        normalized_sources: set[str] = set()
        for tool_call in successful_tool_calls:
            for source in (tool_call.arguments, (tool_call.result or {}).get("data")):
                for scalar in self._iter_scalars(source):
                    normalized_sources.add(self._normalize_text(scalar))
                    decimal_value = self._to_decimal(scalar)
                    if decimal_value is not None:
                        source_decimals.add(decimal_value)

        return tuple(
            fact
            for fact in facts
            if not self._is_supported(fact, source_decimals, normalized_sources)
        )

    @classmethod
    def _is_supported(
        cls,
        fact: BusinessFact,
        source_decimals: set[Decimal],
        normalized_sources: set[str],
    ) -> bool:
        if fact.category == FactCategory.NUMBER:
            return Decimal(fact.value) in source_decimals
        normalized_value = cls._normalize_text(fact.value)
        if fact.category == FactCategory.STATUS:
            return (
                normalized_value in normalized_sources
                or STATUS_CODE_MAP[fact.value] in normalized_sources
            )
        return normalized_value in normalized_sources

    @classmethod
    def _to_decimal(cls, value: object) -> Decimal | None:
        text = str(value).strip()
        if cls.number_pattern.fullmatch(text) is None:
            return None
        return Decimal(text)

    @staticmethod
    def _normalize_text(value: object) -> str:
        return (
            unicodedata.normalize("NFKC", str(value))
            .strip()
            .casefold()
            .replace("-", "_")
        )

    @classmethod
    def _iter_scalars(cls, value: object) -> Iterable[object]:
        if isinstance(value, dict):
            for nested in value.values():
                yield from cls._iter_scalars(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from cls._iter_scalars(nested)
        elif value is not None:
            yield value
