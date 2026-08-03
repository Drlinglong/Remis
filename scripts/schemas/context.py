"""Typed domain contracts for traceable Mod Context releases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Provenance = Literal["text_inferred", "script_derived", "user_confirmed"]
ContributionType = Literal["mention", "fact", "event", "relationship"]
AggregateType = Literal["entity", "event", "project"]
DeliveryRole = Literal["primary_member", "supporting_context", "theme_related"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_credentials(value: Any) -> Any:
    forbidden = {
        "api_key",
        "api_token",
        "authorization",
        "password",
        "secret",
        "token",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if (
                normalized in forbidden
                or normalized.endswith("_token")
                or normalized.endswith("_secret")
                or normalized in {"private_key", "credential"}
            ):
                raise ValueError("context analysis configuration cannot contain credentials")
            _reject_credentials(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_credentials(nested)
    return value


class ContextSourceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_item_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    content: str
    content_hash: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class ContextContribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    contribution_id: str = Field(min_length=1)
    source_item_id: str = Field(min_length=1)
    contribution_type: ContributionType
    subject_key: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    created_at: str = Field(default_factory=_now)


class ContextAggregate(BaseModel):
    model_config = ConfigDict(frozen=True)

    aggregate_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    aggregate_type: AggregateType
    aggregate_key: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    contribution_ids: list[str] = Field(min_length=1)
    created_at: str = Field(default_factory=_now)


class ContextDeliveryMembership(BaseModel):
    """One immutable event-summary delivery edge captured in a release."""

    model_config = ConfigDict(frozen=True)

    aggregate_id: str = Field(min_length=1)
    source_item_id: str = Field(min_length=1)
    role: DeliveryRole
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance = "text_inferred"
    reasoning: str | None = Field(default=None, max_length=500)


class GeneratedSynthesis(BaseModel):
    model_config = ConfigDict(frozen=True)

    synthesis_id: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    context_key: str = Field(min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)


class ContextSynthesisItem(BaseModel):
    """Validated model output for one aggregate summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_alias: str = Field(pattern=r"^a\d+$")
    summary: str = Field(min_length=1, max_length=1200)
    evidence_aliases: list[str] = Field(min_length=1, max_length=20)


class ContextSynthesisResponse(BaseModel):
    """The single structured response used by the context synthesizer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    syntheses: list[ContextSynthesisItem] = Field(min_length=1, max_length=250)


class HumanOverride(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_key: str = Field(min_length=1)
    value: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class ContextReleaseMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_snapshot_hash: str = Field(min_length=1)
    analysis_scope: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    analysis_config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)
    parent_release_id: str | None = None
    upstream_version: str | None = None

    _validate_analysis_config = field_validator("analysis_config")(_reject_credentials)


class ContextReleaseFile(BaseModel):
    """One source file captured by an immutable Context Release manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str = Field(min_length=1)
    source_sha256: str = Field(min_length=1)
    size: int = Field(ge=0)


class ContextReleaseSourceItem(BaseModel):
    """One logical source item and its content revision in a release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_item_id: str = Field(min_length=1)
    source_revision_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    item_key: str | None = None
    duplicate_key_ordinal: int = Field(default=0, ge=0)
    source_order: int | None = Field(default=None, ge=0)
    source_ref: str = Field(min_length=1)
    content: str
    content_hash: str = Field(min_length=1)


class ContextReleaseLocalUnit(BaseModel):
    """A persisted local-unit grouping with ordered source-item members."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    local_unit_id: str = Field(min_length=1)
    unit_key: str = Field(min_length=1)
    unit_order: int = Field(ge=0)
    source_item_ids: list[str] = Field(default_factory=list)


class ContextReleaseManifest(BaseModel):
    """Self-contained source and unit snapshot owned by one release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    files: list[ContextReleaseFile] = Field(default_factory=list)
    source_items: list[ContextReleaseSourceItem] = Field(default_factory=list)
    local_units: list[ContextReleaseLocalUnit] = Field(default_factory=list)


class ContextDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: str
    project_id: str
    base_release_id: str | None = None
    status: Literal["draft", "published"]
    created_at: str
    updated_at: str
    overrides: list[HumanOverride] = Field(default_factory=list)


class ContextRelease(BaseModel):
    model_config = ConfigDict(frozen=True)

    release_id: str
    project_id: str
    metadata: ContextReleaseMetadata


class EffectiveContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    release: ContextRelease
    generated_synthesis: dict[str, dict[str, Any]]
    human_overrides: dict[str, dict[str, Any]]
    effective_context: dict[str, dict[str, Any]]
