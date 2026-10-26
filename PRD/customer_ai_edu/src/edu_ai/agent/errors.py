"""Agent 运行状态与错误定义。"""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    DECISION_PREPARED = "DECISION_PREPARED"
    COMPLETED = "COMPLETED"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class CorrectableErrorCode(StrEnum):
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    UNSUPPORTED_FACT = "UNSUPPORTED_FACT"


class TerminalErrorCode(StrEnum):
    MODEL_CALL_FAILED = "MODEL_CALL_FAILED"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    ACTION_EXECUTION_FAILED = "ACTION_EXECUTION_FAILED"


type AgentErrorCode = CorrectableErrorCode | TerminalErrorCode


class AgentOutputValidationError(ValueError):
    def __init__(self, code: CorrectableErrorCode, message: str):
        super().__init__(message)
        self.code = code


class AgentExecutionError(RuntimeError):
    def __init__(self, code: AgentErrorCode, message: str):
        super().__init__(message)
        self.code = code


class RunNotFoundError(LookupError):
    pass


class RunConflictError(RuntimeError):
    pass


class ActionExecutionError(RuntimeError):
    """写操作暂时无法确认，允许客服侧稍后重试。"""

