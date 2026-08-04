"""Pydantic contracts for the isolated context-tree v2 entity digest slice."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


MAX_ENTITY_UNITS = 12
MAX_ENTITY_SOURCE_CHARS = 8_000
MAX_PROJECT_OVERVIEW_CHARS = 2_000
MAX_DIGEST_SUMMARY_CHARS = 4_000


class CandidateGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class CandidateKind(str, Enum):
    ENTITY = "entity"
    TERM = "term"


class EntityDigestDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    detail: str = ""
    candidate_id: str | None = None


class DigestCandidate(BaseModel):
    """Compact candidate view accepted from v2 or v10-compatible callers."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    candidate_id: str = Field(min_length=1, max_length=240)
    compact_name: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("compact_name", "canonical_name", "name"),
    )
    local_description: str = Field(default="", max_length=2_000)
    aliases: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    local_unit_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=1_000)
    event_group_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    grade: CandidateGrade
    kind: CandidateKind = CandidateKind.ENTITY
    grade_source: Literal["automatic", "manual"] = "automatic"
    manual_grade_override: CandidateGrade | None = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        data.setdefault("compact_name", data.get("canonical_name", data.get("name")))
        if not data.get("local_description"):
            descriptions = data.get("local_descriptions", ()) or ()
            data["local_description"] = "; ".join(str(item) for item in descriptions)
        data.setdefault("kind", data.get("candidate_kind", "entity"))
        return data


class DigestLocalUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    unit_id: str = Field(
        min_length=1,
        max_length=240,
        validation_alias=AliasChoices("unit_id", "local_unit_id"),
    )
    source_text: str = Field(
        default="",
        max_length=1_000_000,
        validation_alias=AliasChoices("source_text", "text", "original_text"),
    )
    event_group_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    batch_index: int | None = Field(default=None, ge=0)
    unit_order: int | None = Field(default=None, ge=0)
    fragment_summary: str = Field(default="", max_length=2_000)
    local_descriptions: tuple[str, ...] = Field(default_factory=tuple, max_length=100)


class SemanticMergeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True)

    target_candidate_id: str = Field(
        min_length=1,
        max_length=240,
        validation_alias=AliasChoices("target_candidate_id", "canonical_candidate_id"),
    )
    member_candidate_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("member_candidate_ids", "member_ids"),
    )
    reason: str | None = Field(default=None, max_length=1_000)


class EntityDigestResponse(BaseModel):
    """Strict model-facing JSON response; IDs are validated after parsing."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=MAX_DIGEST_SUMMARY_CHARS)
    evidence_unit_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=MAX_ENTITY_UNITS)
    semantic_merge: SemanticMergeProposal | None = None


class SampledLocalUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    source_text: str
    event_group_ids: tuple[str, ...] = ()
    batch_index: int | None = None
    selection_reasons: tuple[str, ...] = ()
    original_char_count: int = Field(ge=0)
    included_char_count: int = Field(ge=0)
    truncated: bool = False


class SamplingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sampler_version: str = "context-tree-v2-entity-sampling-v1"
    candidate_id: str
    eligible_unit_count: int = Field(ge=0)
    selected_unit_count: int = Field(ge=0, le=MAX_ENTITY_UNITS)
    original_char_count: int = Field(ge=0)
    included_char_count: int = Field(ge=0, le=MAX_ENTITY_SOURCE_CHARS)
    unit_budget: int = MAX_ENTITY_UNITS
    source_char_budget: int = MAX_ENTITY_SOURCE_CHARS
    first_occurrence_unit_id: str | None = None
    last_occurrence_unit_id: str | None = None
    high_information_density_unit_id: str | None = None
    covered_event_group_ids: tuple[str, ...] = ()
    omitted_event_group_ids: tuple[str, ...] = ()
    selection_reasons: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    truncated_unit_ids: tuple[str, ...] = ()
    digest_segment_id: str | None = None
    batch_indexes: tuple[int, ...] = ()
    consumes_all_evidence: bool = False


class SamplingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    units: tuple[SampledLocalUnit, ...]
    metadata: SamplingMetadata
    diagnostics: tuple[EntityDigestDiagnostic, ...] = ()


class EntityEvidenceRecord(BaseModel):
    """Immutable #2 evidence with an explicit sample-inclusion flag."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    source_text: str = ""
    local_description: str = ""
    local_descriptions: tuple[str, ...] = ()
    event_group_ids: tuple[str, ...] = ()
    included_in_digest: bool = False
    digest_segment_id: str | None = None
    digest_segment_ids: tuple[str, ...] = ()


class EntityEvidenceBundle(BaseModel):
    """Complete local evidence retained alongside any bounded digest call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    full_evidence: tuple[EntityEvidenceRecord, ...] = ()
    mechanical_local_description: str = ""


class ProjectOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    source: Literal["human", "generated"]
    char_count: int = Field(ge=0, le=MAX_PROJECT_OVERVIEW_CHARS)
    truncated: bool = False
    parts: tuple[str, ...] = ()


class EntityDigest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    summary: str
    digest_status: Literal["complete", "incomplete"] = "complete"
    llm_digest: str = ""
    final_digest: str = ""
    partial_digests: tuple["PartialEntityDigest", ...] = ()
    digest_segment_id: str | None = None
    mechanical_local_description: str = ""
    full_evidence: tuple[EntityEvidenceRecord, ...] = ()
    evidence_unit_ids: tuple[str, ...] = ()
    semantic_merge: SemanticMergeProposal | None = None
    sampling: SamplingMetadata

    @model_validator(mode="before")
    @classmethod
    def _keep_llm_alias(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        data.setdefault("llm_digest", data.get("summary", ""))
        data.setdefault("final_digest", data.get("summary", ""))
        return data


class SemanticMergeRecompute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_candidate_id: str
    member_candidate_ids: tuple[str, ...]
    source_candidate_id: str
    merged_local_unit_ids: tuple[str, ...]
    merged_event_group_ids: tuple[str, ...]
    local_unit_coverage: int = Field(ge=0)
    recomputed_grade: CandidateGrade


class PartialEntityDigest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    digest_segment_id: str
    candidate_id: str
    summary: str
    evidence_unit_ids: tuple[str, ...] = ()
    batch_indexes: tuple[int, ...] = ()


class EntityDigestCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    status: Literal["succeeded", "invalid_response", "handler_error", "skipped"]
    phase: Literal["single", "partial", "final", "skipped"] = "single"
    digest_segment_id: str | None = None
    temperature: float = 0.0
    messages: tuple[dict[str, str], ...] = ()
    sampling: SamplingMetadata | None = None
    response_payload: dict[str, Any] | None = None
    digest: EntityDigest | None = None
    diagnostics: tuple[EntityDigestDiagnostic, ...] = ()


class EntityDigestRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_overview: ProjectOverview
    evidence_bundles: tuple[EntityEvidenceBundle, ...] = ()
    digests: tuple[EntityDigest, ...] = ()
    semantic_merges: tuple[SemanticMergeRecompute, ...] = ()
    call_records: tuple[EntityDigestCallRecord, ...] = ()
    diagnostics: tuple[EntityDigestDiagnostic, ...] = ()


TreeCandidate = DigestCandidate
EntityCandidate = DigestCandidate
LocalUnit = DigestLocalUnit
SemanticMergeResult = SemanticMergeRecompute

EntityDigest.model_rebuild()


__all__ = [
    "CandidateGrade",
    "CandidateKind",
    "DigestCandidate",
    "DigestLocalUnit",
    "EntityCandidate",
    "EntityDigest",
    "EntityDigestCallRecord",
    "EntityDigestDiagnostic",
    "EntityEvidenceBundle",
    "EntityEvidenceRecord",
    "EntityDigestResponse",
    "EntityDigestRunResult",
    "PartialEntityDigest",
    "LocalUnit",
    "MAX_DIGEST_SUMMARY_CHARS",
    "MAX_ENTITY_SOURCE_CHARS",
    "MAX_ENTITY_UNITS",
    "MAX_PROJECT_OVERVIEW_CHARS",
    "ProjectOverview",
    "SampledLocalUnit",
    "SamplingMetadata",
    "SamplingResult",
    "SemanticMergeProposal",
    "SemanticMergeRecompute",
    "SemanticMergeResult",
    "TreeCandidate",
]
