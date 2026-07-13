"""Pydantic schemas for Remis Help Copilot."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CopilotChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(..., min_length=1)


class CopilotChatRequest(BaseModel):
    messages: list[CopilotChatMessage] = Field(..., min_length=1)
    # Test default: local LM Studio. UI provider/model picker comes later.
    provider: str = Field(default="lm_studio")
    model: Optional[str] = Field(default=None)
    locale: str = Field(default="zh")
    # Optional override; default targets ~32k local models with output headroom.
    context_budget_tokens: Optional[int] = Field(default=None, ge=2000, le=200000)
    # Sanitized UI snapshot supplied by Remis, never arbitrary application state.
    page_context: Optional[dict[str, Any]] = Field(default=None)


class SuggestedAction(BaseModel):
    action: str
    label: str
    args: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    risk: str = "safe_ui_navigation"


class CopilotSource(BaseModel):
    title: str
    path: str


class CopilotContextInfo(BaseModel):
    estimated_input_tokens: int = 0
    budget_tokens: int = 24000
    dropped_message_count: int = 0
    truncated_system: bool = False
    strategy: str = "keep_recent"
    warnings: list[str] = Field(default_factory=list)
    history_message_count: int = 0
    routing_mode: str = "not_run"
    routing_ms: int = 0
    answer_ms: int = 0
    selected_skill_ids: list[str] = Field(default_factory=list)
    loaded_source_count: int = 0


class CopilotChatResponse(BaseModel):
    reply: str
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    sources: list[CopilotSource] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    provider: str = "lm_studio"
    model: Optional[str] = None
    parse_mode: Literal["structured", "fallback_text"] = "structured"
    grounding: Literal["strong", "weak", "none", "policy"] = "weak"
    grounding_score: int = 0
    context: Optional[CopilotContextInfo] = None


class CopilotActionDescriptor(BaseModel):
    action: str
    label: str
    description: str
    risk: str
    requires_confirmation: bool = False
    phase: int = 1


class CopilotStatusResponse(BaseModel):
    enabled: bool = True
    phase: int = 1
    default_provider: str = "lm_studio"
    context_budget_tokens: int = 24000
    context_policy: str = (
        "For ~32k local models: estimate tokens, drop oldest history first, "
        "optionally trim system docs; do not throw solely because the chat is long."
    )
    notes: str = (
        "Help Copilot: LM Studio by default for local testing. "
        "Chats persist in the browser (localStorage). "
        "Provider/model picker will be added on the helper page later."
    )
