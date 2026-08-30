"""Bounded, read-only response contracts for the Agent Mod Context API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentContextReleaseMetadata(BaseModel):
    """Safe metadata for one published context release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    project_id: str
    source_snapshot_hash: str
    analysis_scope: dict[str, Any] = Field(default_factory=dict)
    schema_version: str
    prompt_version: str
    provider_id: str
    model_id: str
    created_at: str
    parent_release_id: str | None = None
    upstream_version: str | None = None
    description_language: str | None = None
    source_refs: list[str] = Field(default_factory=list, max_length=200)


class AgentContextLatestReleaseResponse(AgentContextReleaseMetadata):
    """Latest-release response with Agent navigation affordances."""

    allowed_actions: list[str] = Field(default_factory=list, max_length=10)
    links: dict[str, str] = Field(default_factory=dict, max_length=10)


class AgentContextEffectiveResponse(BaseModel):
    """Generated synthesis merged with the published human overrides."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    release: AgentContextReleaseMetadata
    generated_synthesis: dict[str, dict[str, Any]] = Field(default_factory=dict)
    human_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    effective_context: dict[str, dict[str, Any]] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list, max_length=10)
    links: dict[str, str] = Field(default_factory=dict, max_length=10)


class AgentContextAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_id: str
    aggregate_type: str
    aggregate_key: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentContextContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_id: str
    source_item_id: str
    contribution_type: str
    subject_key: str
    provenance: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentContextSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    synthesis_id: str
    context_key: str
    content: dict[str, Any] = Field(default_factory=dict)


class AgentContextSourceEvidence(BaseModel):
    """A bounded source excerpt; internal metadata and full paths are omitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_item_id: str
    source_type: str
    source_ref: str
    content_excerpt: str = Field(max_length=2000)
    content_hash: str
    created_at: str


class AgentContextTraceabilityItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate: AgentContextAggregate
    contributions: list[AgentContextContribution] = Field(default_factory=list, max_length=50)
    syntheses: list[AgentContextSynthesis] = Field(default_factory=list, max_length=20)
    source_evidence: list[AgentContextSourceEvidence] = Field(
        default_factory=list, max_length=50
    )
    delivery_membership_count: int = Field(default=0, ge=0)
    delivery_role_counts: dict[str, int] = Field(default_factory=dict, max_length=3)


class AgentContextSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_key: str | None = None
    context_key: str | None = None


class AgentContextTraceabilityResponse(BaseModel):
    """Traceability for one selected aggregate or context key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    release: AgentContextReleaseMetadata
    selection: AgentContextSelection
    traceability: list[AgentContextTraceabilityItem] = Field(
        default_factory=list, max_length=20
    )
    truncated: bool = False
    allowed_actions: list[str] = Field(default_factory=list, max_length=10)
    links: dict[str, str] = Field(default_factory=dict, max_length=10)
