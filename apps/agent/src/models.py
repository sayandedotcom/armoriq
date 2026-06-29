from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class RuleType(str, Enum):
    BLOCK_TOOL = "block_tool"
    REQUIRE_APPROVAL = "require_approval"
    INPUT_VALIDATION = "input_validation"
    TOKEN_BUDGET = "token_budget"
    PROMPT_INJECTION_GUARD = "prompt_injection_guard"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class Rule(BaseModel):
    id: str | None = None
    name: str
    rule_type: RuleType
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    server_name: str
    arguments: dict[str, Any]
    conversation_id: str
    user_id: str | None = None


class PolicyResult(BaseModel):
    decision: Decision
    reason: str | None = None
    rule_id: str | None = None
    tool_call: ToolCall | None = None


class ApprovalRequest(BaseModel):
    id: str | None = None
    tool_call: ToolCall
    status: str = "pending"
    timeout_seconds: int = 300
    created_at: datetime | None = None
    expires_at: datetime | None = None


class LogEntry(BaseModel):
    id: str | None = None
    conversation_id: str
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    decision: Decision | None = None
    rule_id: str | None = None
    rule_name: str | None = None
    reason: str | None = None
    token_used: int = 0
    timestamp: datetime | None = None


class ConversationMessage(BaseModel):
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None
