"""Pydantic schemas for Remis Help Copilot."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CopilotChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(..., min_length=1)


class CopilotChatRequest(BaseModel):
    messages: list[CopilotChatMessage] = Field(..., min_length=1)
    # Omitted values use the server-owned shared Copilot settings.
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    locale: str = Field(default="zh")
    # Optional override; omitted requests use the shared 200k input budget.
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
    budget_tokens: int = 200000
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
    phase: int = 2
    default_provider: str = "lm_studio"
    default_model: Optional[str] = None
    reasoning_enabled: bool = False
    reasoning_preset: str = "medium"
    context_budget_tokens: int = 200000
    context_policy: str = (
        "Use a default 200000-token input budget; drop oldest history first and "
        "protect the latest user message. If no verified provider/model limit is "
        "available, surface a recoverable context-length error instead of guessing."
    )
    notes: str = (
        "Help Copilot uses the shared server-owned Copilot settings. "
        "Chats persist in the browser (localStorage). "
        "Provider, model, and verified reasoning strength are configured in Settings."
    )


class CopilotWorkflowPlanRequest(BaseModel):
    folder_path: str = Field(..., min_length=1)
    project_name: str = Field(..., min_length=1, max_length=160)
    game_id: str = Field(..., min_length=1)
    source_language: str = Field(default="en", min_length=1)
    import_mode: Literal["copy", "reference"] = "copy"
    target_language: str = Field(default="zh-CN", min_length=1)
    api_provider: str = Field(default="lm_studio", min_length=1)
    model: str = Field(default="google/gemma-4-31b-qat", min_length=1)
    batch_size_limit: Optional[int] = Field(default=10, ge=1, le=1000)
    concurrency_limit: Optional[int] = Field(default=1, ge=1, le=100)
    rpm_limit: Optional[int] = Field(default=40, ge=1, le=100000)
    use_resume: bool = True
    use_main_glossary: bool = True
    embedded_workshop_enabled: bool = True


class CopilotWorkflowApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., min_length=1)


class CopilotTranslationPlanRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    target_lang_codes: list[str] = Field(default_factory=lambda: ["zh-CN"], min_length=1)
    api_provider: str = Field(default="lm_studio", min_length=1)
    model: str = Field(..., min_length=1)
    batch_size_limit: Optional[int] = Field(default=10, ge=1, le=1000)
    concurrency_limit: Optional[int] = Field(default=1, ge=1, le=100)
    rpm_limit: Optional[int] = Field(default=40, ge=1, le=100000)
    use_resume: bool = True
    use_main_glossary: bool = True
    embedded_workshop_enabled: bool = True


class CopilotAgentRecommendationRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    target_lang_codes: list[str] = Field(default_factory=lambda: ["zh-CN"], min_length=1)
    preferred_provider: str = Field(default="lm_studio", min_length=1)
    planner_provider: Optional[str] = Field(default=None, min_length=1)
    planner_model: Optional[str] = None


class CopilotSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_enabled: bool = False
    reasoning_preset: Literal["minimal", "low", "medium", "high", "xhigh", "max"] = "medium"
