"""Immutable source-grounded node contracts for Context Archive tree v2."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_IDENTIFIER_LENGTH = 200
MAX_SOURCE_REF_LENGTH = 500
MAX_ITEM_KEY_LENGTH = 300
MAX_LABEL_LENGTH = 240
MAX_SUMMARY_LENGTH = 1200
MAX_BOUNDARY_LENGTH = 800
MAX_EVIDENCE_EXCERPT_LENGTH = 2000
MAX_REASON_LENGTH = 500
MAX_FRAGMENT_COUNT = 500
MAX_UNIT_COUNT = 500
MAX_GROUP_COUNT = 200
MAX_STORY_COUNT = 100
MAX_EDGE_COUNT = 1_000
MAX_EVIDENCE_COUNT = 50
MAX_EDGE_UNIT_COUNT = 20

Identifier = Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]
EvidenceText = Annotated[str, Field(min_length=1, max_length=MAX_EVIDENCE_EXCERPT_LENGTH)]
ShortText = Annotated[str, Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)]
LabelText = Annotated[str, Field(min_length=1, max_length=MAX_LABEL_LENGTH)]

UnitRouteKind = Literal["reference_asset", "narrative", "no_context"]
UnresolvedReferenceKind = Literal[
    "fragment", "fragment_edge", "group", "story", "unit_route", "source_evidence"
]


class _ExternalContract(BaseModel):
    """Shared strictness for all public tree contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class SourceEvidenceReference(_ExternalContract):
    """Immutable pointer to source material supporting a fragment card."""

    source_item_id: Identifier
    source_ref: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_REF_LENGTH,
        validation_alias=AliasChoices("source_ref", "relative_path"),
    )
    local_unit_id: Identifier | None = None
    item_key: str | None = Field(default=None, min_length=1, max_length=MAX_ITEM_KEY_LENGTH)
    source_order: int | None = Field(default=None, ge=0, le=1_000_000)
    excerpt: str | None = Field(
        default=None,
        validation_alias=AliasChoices("excerpt", "snippet", "content_excerpt"),
    )
    content_hash: str | None = Field(default=None, min_length=1, max_length=128)
    provenance: str | None = Field(default=None, min_length=1, max_length=100)
    batch_source: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_SOURCE_REF_LENGTH,
        validation_alias=AliasChoices("batch_source", "source_batch", "batch_name"),
    )
    batch_id: Identifier | None = None
    batch_index: int | None = Field(default=None, ge=0, le=1_000_000)
    # The source snapshot remains the authority.  This optional field lets a
    # caller carry an unabridged evidence payload without treating the
    # model-request budget as a persistence limit.
    full_source_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityEvidenceReference(SourceEvidenceReference):
    """One complete #2 entity-evidence record, including digest provenance."""

    evidence_id: Identifier
    entity_id: Identifier
    included_in_digest: bool | None = True
    digest_segment_id: Identifier | None = None
    digest_provenance: Literal["partial", "final"] | None = None
    sampling_state: Literal["included", "excluded", "not_applicable", "unknown"] | None = None


class EntityAliasDescription(_ExternalContract):
    """A human-readable description for one entity alias candidate."""

    alias: LabelText
    description: str | None = None
    evidence_ids: tuple[Identifier, ...] = ()


class EntityDigestSegment(_ExternalContract):
    """One bounded model-request segment retained as digest provenance."""

    digest_segment_id: Identifier
    summary: str
    evidence_unit_ids: tuple[Identifier, ...] = ()
    batch_indexes: tuple[int, ...] = ()


class EntityDigest(_ExternalContract):
    """Persisted A/B digest metadata; C candidates do not receive a digest."""

    entity_id: Identifier
    canonical_name: LabelText = Field(validation_alias=AliasChoices("canonical_name", "name"))
    level: Literal["A", "B", "C"]
    summary: str | None = None
    mechanical_local_description: str | None = None
    partial_digests: tuple[EntityDigestSegment, ...] = ()
    final_digest: str | EntityDigestSegment | None = None
    alias_descriptions: tuple[EntityAliasDescription, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()
    digest_segment_ids: tuple[Identifier, ...] = ()
    source_batch_ids: tuple[Identifier, ...] = ()
    digest_provenance: Literal["not_generated", "partial", "final"] = "not_generated"

    @model_validator(mode="before")
    @classmethod
    def _normalize_final_digest(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        final_digest = normalized.get("final_digest")
        if normalized.get("summary") is None and isinstance(final_digest, dict):
            normalized["summary"] = final_digest.get("summary")
        if normalized.get("final_digest") is None and normalized.get("summary") is not None:
            normalized["final_digest"] = normalized["summary"]
        if normalized.get("summary") is None and normalized.get("final_digest") is not None:
            normalized["summary"] = normalized["final_digest"]
        if normalized.get("final_digest") and not normalized.get("digest_provenance"):
            normalized["digest_provenance"] = "final"
        return normalized

    @model_validator(mode="after")
    def _keep_c_candidates_without_digest(self) -> "EntityDigest":
        if self.level == "C" and (
            self.summary is not None
            or self.final_digest is not None
            or self.partial_digests
            or self.digest_segment_ids
            or self.digest_provenance != "not_generated"
        ):
            raise ValueError("C-level entities do not receive a digest")
        if self.level in {"A", "B"} and self.final_digest is not None and self.digest_provenance != "final":
            raise ValueError("A/B final digests must be marked with final provenance")
        return self


class ChunkEdgeMetadata(_ExternalContract):
    """Immutable chunk-boundary signals used while stitching local fragments."""

    chunk_id: Identifier | None = None
    touches_chunk_start: bool = Field(
        default=False,
        validation_alias=AliasChoices("touches_chunk_start", "at_chunk_start"),
    )
    touches_chunk_end: bool = Field(
        default=False,
        validation_alias=AliasChoices("touches_chunk_end", "at_chunk_end"),
    )
    previous_unit_ids: tuple[Identifier, ...] = Field(default=(), max_length=MAX_EDGE_UNIT_COUNT)
    next_unit_ids: tuple[Identifier, ...] = Field(default=(), max_length=MAX_EDGE_UNIT_COUNT)

    @field_validator("previous_unit_ids", "next_unit_ids")
    @classmethod
    def _require_unique_unit_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("chunk edge unit IDs must be unique")
        return value


class LocalFragmentCard(_ExternalContract):
    """Immutable local narrative evidence and chunk-edge context."""

    fragment_id: Identifier
    summary: ShortText
    unit_ids: tuple[Identifier, ...] = Field(
        min_length=1,
        max_length=MAX_UNIT_COUNT,
        validation_alias=AliasChoices("unit_ids", "local_unit_ids"),
    )
    continuation_clues: tuple[ShortText, ...] = Field(default=(), max_length=20)
    boundary_includes: str | None = Field(default=None, min_length=1, max_length=MAX_BOUNDARY_LENGTH)
    boundary_excludes: str | None = Field(default=None, min_length=1, max_length=MAX_BOUNDARY_LENGTH)
    edge_metadata: ChunkEdgeMetadata
    source_evidence_refs: tuple[SourceEvidenceReference, ...] = Field(
        min_length=1,
        validation_alias=AliasChoices("source_evidence_refs", "source_evidence_references"),
    )

    @field_validator("unit_ids")
    @classmethod
    def _require_unique_unit_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("fragment unit IDs must be unique")
        return value

    @model_validator(mode="after")
    def _validate_evidence_units(self) -> "LocalFragmentCard":
        unit_ids = set(self.unit_ids)
        unknown_units = {
            evidence.local_unit_id
            for evidence in self.source_evidence_refs
            if evidence.local_unit_id is not None and evidence.local_unit_id not in unit_ids
        }
        if unknown_units:
            raise ValueError(
                "fragment evidence must reference one of the fragment unit IDs: "
                f"{sorted(unknown_units)}"
            )
        return self


class UnitRoute(_ExternalContract):
    """The only three legal delivery routes for a local unit."""

    local_unit_id: Identifier = Field(validation_alias=AliasChoices("local_unit_id", "unit_id"))
    route: UnitRouteKind = Field(validation_alias=AliasChoices("route", "route_kind"))
    fragment_ids: tuple[Identifier, ...] = Field(
        default=(), max_length=MAX_FRAGMENT_COUNT,
        validation_alias=AliasChoices("fragment_ids", "local_fragment_ids"),
    )
    entity_evidence: tuple[EntityEvidenceReference, ...] = ()
    entity_digests: tuple[EntityDigest, ...] = ()
    entity_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fragment_ids")
    @classmethod
    def _require_unique_fragment_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("unit route fragment IDs must be unique")
        return value

    @model_validator(mode="after")
    def _keep_reference_assets_out_of_event_context(self) -> "UnitRoute":
        if self.route != "narrative" and self.fragment_ids:
            raise ValueError("reference_asset and no_context routes cannot carry fragment IDs")
        return self


class Story(_ExternalContract):
    """Archive-only story container, not a translation delivery target."""

    story_id: Identifier
    group_ids: tuple[Identifier, ...] = Field(default=(), max_length=MAX_GROUP_COUNT)
    title: LabelText | None = None
    summary: ShortText | None = None

    @field_validator("group_ids")
    @classmethod
    def _require_unique_group_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("story group IDs must be unique")
        return value


class SiblingGroup(_ExternalContract):
    """Unordered sibling group whose fragment membership is ordered."""

    group_id: Identifier
    story_id: Identifier | None = None
    fragment_ids: tuple[Identifier, ...] = Field(default=(), max_length=MAX_FRAGMENT_COUNT)
    title: LabelText | None = None
    summary: ShortText | None = None

    @field_validator("fragment_ids")
    @classmethod
    def _require_unique_fragment_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("sibling group fragment IDs must be unique")
        return value


class OrderedFragmentEdge(_ExternalContract):
    """One position-bearing edge inside an unordered sibling group."""

    edge_id: Identifier | None = None
    group_id: Identifier
    from_fragment_id: Identifier = Field(
        validation_alias=AliasChoices("from_fragment_id", "previous_fragment_id", "predecessor_fragment_id")
    )
    to_fragment_id: Identifier = Field(
        validation_alias=AliasChoices("to_fragment_id", "next_fragment_id", "successor_fragment_id")
    )
    position: int = Field(
        ge=0, le=MAX_EDGE_COUNT,
        validation_alias=AliasChoices("position", "order", "sequence", "ordinal"),
    )

    @model_validator(mode="after")
    def _reject_self_edges(self) -> "OrderedFragmentEdge":
        if self.from_fragment_id == self.to_fragment_id:
            raise ValueError("ordered fragment edges cannot point to themselves")
        return self


class UnresolvedReference(_ExternalContract):
    """Preserved link that remained unresolved after the bounded repair attempt."""

    reference_id: Identifier
    reference_type: UnresolvedReferenceKind
    source_id: Identifier
    target_id: Identifier
    reason: str = Field(min_length=1, max_length=MAX_REASON_LENGTH)
    repair_attempts: int = Field(default=0, ge=0, le=1)
    repair_detail: str | None = Field(default=None, min_length=1, max_length=MAX_REASON_LENGTH)

    @property
    def unresolved_id(self) -> str:
        """Compatibility name used by the storage row without duplicating identity."""
        return self.reference_id

    def model_copy(self, *, update=None, deep=False):  # type: ignore[override]
        """Keep the one-repair bound even when callers request a model copy."""
        values = self.model_dump()
        values.update(update or {})
        return type(self).model_validate(values)


__all__ = [
    "ChunkEdgeMetadata", "Identifier", "LocalFragmentCard", "OrderedFragmentEdge",
    "EntityAliasDescription", "EntityDigest", "EntityDigestSegment", "EntityEvidenceReference", "ShortText",
    "SourceEvidenceReference", "Story", "SiblingGroup", "UnitRoute",
    "UnitRouteKind", "UnresolvedReference", "UnresolvedReferenceKind", "_ExternalContract",
    "MAX_EDGE_COUNT", "MAX_FRAGMENT_COUNT", "MAX_GROUP_COUNT",
    "MAX_REASON_LENGTH", "MAX_STORY_COUNT", "MAX_UNIT_COUNT",
]
