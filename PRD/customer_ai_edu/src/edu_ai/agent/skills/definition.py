"""技能定义。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SkillCode(StrEnum):
    ORDER_SERVICE = "order-service"
    LOGISTICS_SERVICE = "logistics-service"
    DEVICE_SERVICE = "device-service"
    REPAIR_SERVICE = "repair-service"
    POLICY_SERVICE = "policy-service"
    COMPLAINT_SERVICE = "complaint-service"


class SkillDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: SkillCode
    description: str = Field(min_length=1)
    guidance: tuple[str, ...] = Field(min_length=1)
    tools: tuple[str, ...] = Field(min_length=1)
