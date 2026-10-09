"""Agent batch inputs expose locale identity separately from engine loading."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BatchPlanRequest(StrictInput):
    api_provider: Literal["openrouter", "openai"] = "openrouter"
    execution_mode: Literal["batch", "immediate"] = "batch"
    project_id: str = Field(min_length=1, max_length=200)
    file_ids: list[str] = Field(min_length=1, max_length=2000)
    target_locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    game_language_slot: str | None = Field(default=None, max_length=100)
    model: str = Field(min_length=3, max_length=200)
    provider_only: list[str] = Field(default_factory=list, max_length=5)
    translation_context_mode: Literal["none", "term_release"]
    allow_provisional_terms: bool = False
    source_column: Literal["Text", "Translation"] = "Text"
    term_release_id: str | None = None
    style_guide: str = Field(default="", max_length=20000)
    reasoning: dict[str, str | bool] = Field(default_factory=dict)
    group_size: int = Field(default=30, ge=1, le=100)
    max_group_chars: int = Field(default=12000, ge=1000, le=60000)


class BatchStartRequest(StrictInput):
    plan_id: str
    idempotency_key: str = Field(min_length=1, max_length=200)
    approved: bool = False


class TranslationTrialPlanRequest(BatchPlanRequest):
    api_provider: Literal["openai"] = "openai"
    execution_mode: Literal["immediate"] = "immediate"


class BatchApplyPlanRequest(StrictInput):
    file_ids: list[str] | None = Field(default=None, min_length=1, max_length=2000)


class BatchApplyRequest(StrictInput):
    apply_plan_id: str
    approved: bool = False


class BatchRetryRequest(StrictInput):
    custom_ids: list[str] = Field(min_length=1, max_length=10000)


class BatchReconcileRequest(StrictInput):
    remote_id: str = Field(min_length=1, max_length=200)
    approved: bool = False


class TermDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_id: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=2000)
    translation: str = Field(min_length=1, max_length=2000)
    sense: str = Field(min_length=1, max_length=10000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    context_keys: list[str] = Field(default_factory=list, max_length=1000)
    evidence_refs: list[str | dict] = Field(default_factory=list, max_length=100)
    reviewer: str = Field(default="", max_length=300)
    review_dimensions: list[str] = Field(default_factory=list, max_length=50)
    unverified_dimensions: list[str] = Field(default_factory=list, max_length=50)


class TermReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: str = Field(min_length=1, max_length=100)
    scope_id: str | None = Field(default=None, min_length=1, max_length=200)
    locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    version: str = Field(min_length=1, max_length=100)
    maturity: Literal["provisional", "approved"] = "provisional"
    terms: list[TermDefinition] = Field(min_length=1, max_length=50000)
    approved: bool = False
