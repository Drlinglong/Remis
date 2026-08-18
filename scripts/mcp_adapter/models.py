"""Typed MCP result envelopes shared by every Remis tool."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class AdapterError(BaseModel):
    """Stable, sanitized error returned when an Agent API operation fails."""

    code: str
    message: str
    retryable: bool = False
    http_status: int | None = None
    action: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AdapterResult(BaseModel, Generic[DataT]):
    """Structured result envelope exposed through MCP structuredContent."""

    ok: bool
    operation: str
    data: DataT | None = None
    preflight: dict[str, Any] | None = None
    error: AdapterError | None = None


class AgentPayload(BaseModel):
    """Typed known fields while preserving forward-compatible Agent API additions."""

    model_config = ConfigDict(extra="allow")


class PreflightData(AgentPayload):
    status: str
    release_check: dict[str, Any]
    provider_setup: dict[str, Any]
    required_before_every_workflow: bool
    allowed_actions: list[str]


class CapabilitiesData(AgentPayload):
    api_version: str | None = None
    remis_version: str | None = None
    service: str
    transport: dict[str, Any] = Field(default_factory=dict)
    games: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    providers: list[dict[str, Any]] = Field(default_factory=list)
    actions: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    links: dict[str, str] = Field(default_factory=dict)


class ProjectSummaryData(AgentPayload):
    project_id: str
    name: str | None = None
    game_id: str | None = None
    source_language: str | None = None
    status: str | None = None
    file_count: int = 0
    file_status_counts: dict[str, int] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)


class TranslationPlanData(AgentPayload):
    plan_id: str
    status: Literal["awaiting_approval", "ready"]
    project_id: str | None = None
    dry_run: bool = False
    requires_approval: bool = True
    risk: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    context_readiness: dict[str, Any] = Field(default_factory=dict)
    expires_at: str


class JobData(AgentPayload):
    job_id: str
    project_id: str | None = None
    status: Literal[
        "queued",
        "running",
        "awaiting_approval",
        "completed",
        "partial_failed",
        "failed",
        "cancelled",
        "interrupted",
        "unknown",
    ]
    kind: str = "translation"
    progress: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    workflow_context: dict[str, Any] = Field(default_factory=dict)
    recovery: dict[str, Any] = Field(default_factory=dict)
    links: dict[str, str] = Field(default_factory=dict)


class TranslationPlanInput(BaseModel):
    """The existing Agent API translation-plan contract."""

    project_id: str = Field(min_length=1)
    target_lang_codes: list[str] = Field(default_factory=lambda: ["zh-CN"])
    api_provider: str = "lm_studio"
    model: str = "local-model"
    batch_size_limit: int | None = Field(default=None, ge=1)
    concurrency_limit: int | None = Field(default=1, ge=1)
    rpm_limit: int | None = Field(default=40, ge=1)
    use_resume: bool = True
    use_main_glossary: bool = True
    translation_context_mode: Literal["none", "glossaries", "archive"] = "archive"
    embedded_workshop_enabled: bool = True
    dry_run: bool = False
