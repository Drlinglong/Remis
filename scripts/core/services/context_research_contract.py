"""Evidence-first contracts for Agent context research.

This module is deliberately a boundary, not another context workflow.  The
Tree v2 implementation remains the source of truth for extraction and
projection; this contract gives Agent callers a small, resumeless execution
context and a typed, source-grounded result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.neologism_extraction import AnalysisScope, SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


class ContextResearchContractError(ValueError):
    """Raised when a research result cannot be proven safe to consume."""


class UnknownSourceItemReference(ContextResearchContractError):
    """Raised when evidence points outside the request's source snapshot."""


class ContextResearchCancelled(ContextResearchContractError):
    """Raised when the owner asks a backend to stop cooperatively."""


@runtime_checkable
class CancellationSignal(Protocol):
    """Cooperative cancellation supplied by the execution owner."""

    def is_cancelled(self) -> bool:
        """Return true once the current operation should stop."""


@runtime_checkable
class UsageSink(Protocol):
    """Sink for non-secret usage accounting."""

    def record(self, event: str, **metadata: Any) -> None:
        """Record one usage event without accepting provider secrets."""


@runtime_checkable
class EventSink(Protocol):
    """Sink for progress and diagnostic events."""

    def emit(self, event: str, payload: Mapping[str, Any] | None = None) -> None:
        """Emit a structured, non-secret event."""


class _NeverCancelled:
    def is_cancelled(self) -> bool:
        return False


class _NullUsageSink:
    def record(self, event: str, **metadata: Any) -> None:
        del event, metadata


class _NullEventSink:
    def emit(self, event: str, payload: Mapping[str, Any] | None = None) -> None:
        del event, payload


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    """Immutable provider/runtime handles for one Agent operation.

    This object intentionally has no ``run``, ``resume`` or ``fork`` method.
    Lifecycle orchestration belongs to the task/workflow owner, while this
    value only carries the execution dependencies needed by a backend.
    """

    provider_selection_id: str
    model_id: str | None = None
    provider_runtime: ProviderRuntimeSnapshot | None = None
    cancellation: CancellationSignal = field(default_factory=_NeverCancelled)
    usage: UsageSink = field(default_factory=_NullUsageSink)
    events: EventSink = field(default_factory=_NullEventSink)

    def __post_init__(self) -> None:
        if not self.provider_selection_id.strip():
            raise ValueError("provider_selection_id must not be empty")
        if self.model_id is not None and not self.model_id.strip():
            raise ValueError("model_id must not be blank when supplied")

    @property
    def provider_runtime_snapshot(self) -> ProviderRuntimeSnapshot | None:
        """Compatibility spelling that makes the snapshot boundary explicit."""

        return self.provider_runtime

    @property
    def runtime(self) -> ProviderRuntimeSnapshot | None:
        """Short compatibility spelling used by existing workflow services."""

        return self.provider_runtime


class EvidenceReference(BaseModel):
    """One non-authoritative excerpt backed by one or more source item IDs."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True,
    )

    source_item_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    snippet: str | None = Field(default=None, max_length=2_000)
    relative_path: str | None = Field(default=None, max_length=500)
    item_key: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _require_unique_ids(self) -> "EvidenceReference":
        if len(self.source_item_ids) != len(set(self.source_item_ids)):
            raise ValueError("evidence source_item_ids must be unique")
        return self


class _EvidenceItem(BaseModel):
    """Shared strictness and evidence requirement for draft entries."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True,
    )

    source_item_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    evidence: tuple[EvidenceReference, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def _evidence_must_be_subset(self) -> "_EvidenceItem":
        direct = set(self.source_item_ids)
        for reference in self.evidence:
            if not set(reference.source_item_ids) <= direct:
                raise ValueError("evidence source_item_ids must be listed on the item")
        return self


class ArchiveNarrative(_EvidenceItem):
    """An archive-only narrative card; it can never be a delivery target."""

    narrative_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_200)
    delivery_target: Literal[False] = False

    @model_validator(mode="after")
    def _reject_delivery_target(self) -> "ArchiveNarrative":
        if self.delivery_target is not False:
            raise ValueError("archive narratives are never delivery targets")
        return self


EntityKind = Literal[
    "person", "place", "organization", "polity", "technology", "concept", "item", "other",
]
EntityImportance = Literal["primary", "supporting", "background"]
EntityFrequencyGrade = Literal["A", "B", "C"]


class ResearchEntity(_EvidenceItem):
    """A named archive entity, separate from events and static UI assets."""

    entity_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    entity_type: EntityKind
    summary: str = Field(min_length=1, max_length=1_000)
    aliases: tuple[str, ...] = Field(default=(), max_length=20)
    importance: EntityImportance = Field(
        default="supporting",
        description="Model-authored plot importance; independent of frequency_grade.",
    )
    mention_count: int = Field(default=0, ge=0)
    local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)
    local_unit_coverage: int = Field(default=0, ge=0)
    source_files: tuple[str, ...] = Field(default=(), max_length=500)
    file_spread: int = Field(default=0, ge=0)
    event_chain_ids: tuple[str, ...] = Field(default=(), max_length=500)
    event_participation_count: int = Field(default=0, ge=0)
    frequency_grade: EntityFrequencyGrade = "C"

    @model_validator(mode="after")
    def _validate_frequency_grade(self) -> "ResearchEntity":
        if len(self.local_unit_ids) != len(set(self.local_unit_ids)):
            raise ValueError("entity local_unit_ids must be unique")
        if self.local_unit_coverage != len(self.local_unit_ids):
            raise ValueError("entity local_unit_coverage must match local_unit_ids")
        if len(self.source_files) != len(set(self.source_files)):
            raise ValueError("entity source_files must be unique")
        if self.file_spread != len(self.source_files):
            raise ValueError("entity file_spread must match source_files")
        if len(self.event_chain_ids) != len(set(self.event_chain_ids)):
            raise ValueError("entity event_chain_ids must be unique")
        if self.event_participation_count != len(self.event_chain_ids):
            raise ValueError("entity event_participation_count must match event_chain_ids")
        expected = "A" if self.local_unit_coverage >= 3 else (
            "B" if self.local_unit_coverage == 2 else "C"
        )
        if self.frequency_grade != expected:
            raise ValueError("entity frequency_grade must match local-unit coverage")
        return self


class EventChain(_EvidenceItem):
    """One ordered event step; sibling steps may share one chain identity."""

    chain_id: str = Field(
        min_length=1, max_length=200,
        validation_alias=AliasChoices("chain_id", "event_chain_id"),
    )
    event: str = Field(min_length=1, max_length=1_000)
    sequence: int = Field(default=0, ge=0)
    local_unit_ids: tuple[str, ...] = Field(default=(), max_length=20)
    archive_context_ids: tuple[str, ...] = Field(default=(), max_length=80)
    entity_ids: tuple[str, ...] = Field(default=(), max_length=80)


class ReferenceAsset(_EvidenceItem):
    """A static asset route, intentionally carrying no event-chain context."""

    asset_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1_000)
    local_unit_id: str | None = Field(default=None, max_length=200)
    receives_event_context: Literal[False] = False


UnresolvedKind = Literal[
    "fragment", "fragment_edge", "group", "story", "unit_route", "source_evidence",
]


class Unresolved(_EvidenceItem):
    """A preserved unknown link; it is safe to expose, never silently repair."""

    unresolved_id: str = Field(min_length=1, max_length=200)
    reference_type: UnresolvedKind
    source_id: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    repair_attempts: int = Field(default=0, ge=0, le=1)
    repair_detail: str | None = Field(default=None, max_length=500)

    @property
    def reference_id(self) -> str:
        """Storage-compatible spelling for the unresolved identity."""

        return self.unresolved_id


class ContextAnalysisRequest(BaseModel):
    """Immutable source snapshot and presentation settings for one analysis."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True,
    )

    request_id: str = Field(default="context-research", min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    research_question: str = Field(
        default="Which source-grounded archive context is relevant to translation?",
        min_length=1,
        max_length=1_000,
    )
    source_items: tuple[SourceItem, ...] = Field(default=())
    source_item_ids: tuple[str, ...] = Field(default=())
    scope: AnalysisScope = AnalysisScope.NARRATIVE_CONTEXT
    game_name: str = Field(default="Paradox Game", min_length=1, max_length=200)
    target_language: str = Field(default="the configured target language", min_length=1, max_length=100)
    reasoning_language: str = Field(default="the configured review language", min_length=1, max_length=100)
    description_language: str = Field(default="en", min_length=1, max_length=40)
    project_summary: str = Field(default="", max_length=4_000)
    chunks: tuple[ContextUnitChunk, ...] | None = None

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "ContextAnalysisRequest":
        item_ids = tuple(item.source_item_id for item in self.source_items)
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("source item identities must be unique")
        declared = self.source_item_ids or item_ids
        if len(declared) != len(set(declared)):
            raise ValueError("source_item_ids must be unique")
        if item_ids and tuple(declared) != item_ids:
            raise ValueError("source_item_ids must match source_items in source order")
        if not declared:
            raise ValueError("ContextAnalysisRequest requires source item IDs")
        if self.chunks is not None:
            known = set(declared)
            chunk_ids = {
                item.source_item_id
                for chunk in self.chunks
                for item in chunk.source_items
            }
            if not chunk_ids <= known:
                raise UnknownSourceItemReference(
                    f"chunks reference unknown source items: {sorted(chunk_ids - known)}"
                )
        return self

    @property
    def known_source_item_ids(self) -> frozenset[str]:
        return frozenset(self.source_item_ids or (item.source_item_id for item in self.source_items))

    @property
    def local_units(self) -> tuple[LocalTextUnit, ...]:
        """Return deterministic key-family units in source order."""

        return ContextLocalUnitBuilder.build(self.source_items)


class ContextResearchDraft(BaseModel):
    """Source-grounded research output with no implicit delivery semantics."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True,
    )

    source_item_ids: tuple[str, ...] = Field(default=())
    archive_narratives: tuple[ArchiveNarrative, ...] = Field(default=(), max_length=500)
    entities: tuple[ResearchEntity, ...] = Field(default=(), max_length=500)
    event_chains: tuple[EventChain, ...] = Field(default=(), max_length=500)
    reference_assets: tuple[ReferenceAsset, ...] = Field(default=(), max_length=500)
    unresolved: tuple[Unresolved, ...] = Field(default=(), max_length=500)
    diagnostics: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_internal_references(self) -> "ContextResearchDraft":
        self._require_unique_ids()
        if not self.source_item_ids:
            inferred = tuple(dict.fromkeys(
                source_id
                for item in self._items()
                for source_id in item.source_item_ids
            ))
            object.__setattr__(self, "source_item_ids", inferred)
        known = set(self.source_item_ids)
        actual = {
            source_id
            for item in self._items()
            for source_id in item.source_item_ids
        }
        unknown = sorted(actual - known)
        if unknown:
            raise UnknownSourceItemReference(
                f"draft item references unknown source items: {unknown}"
            )
        if known != actual:
            raise ValueError(
                "draft source_item_ids must equal the union of item source_item_ids"
            )
        for item in self._items():
            if not set(item.source_item_ids) <= known:
                unknown = sorted(set(item.source_item_ids) - known)
                raise UnknownSourceItemReference(f"draft item references unknown source items: {unknown}")
        narrative_ids = {item.narrative_id for item in self.archive_narratives}
        entity_ids = {item.entity_id for item in self.entities}
        for event in self.event_chains:
            unknown = set(event.archive_context_ids) - narrative_ids
            if unknown:
                raise ContextResearchContractError(
                    f"event chain references unknown archive context: {sorted(unknown)}"
                )
            unknown_entities = set(event.entity_ids) - entity_ids
            if unknown_entities:
                raise ContextResearchContractError(
                    f"event chain references unknown entities: {sorted(unknown_entities)}"
                )
        return self

    def validate_against(self, request: ContextAnalysisRequest) -> "ContextResearchDraft":
        """Validate the draft against the immutable source snapshot."""

        expected = set(request.known_source_item_ids)
        if not set(self.source_item_ids) <= expected:
            unknown = sorted(set(self.source_item_ids) - expected)
            raise UnknownSourceItemReference(
                f"draft source_item_ids reference unknown source items: {unknown}"
            )
        values = self.model_dump()
        values["source_item_ids"] = self.source_item_ids
        candidate = type(self).model_validate(values)
        for item in candidate._items():
            unknown = set(item.source_item_ids) - expected
            if unknown:
                raise UnknownSourceItemReference(f"unknown source item IDs: {sorted(unknown)}")
        return candidate

    def _items(self) -> tuple[_EvidenceItem, ...]:
        return (
            *self.archive_narratives, *self.entities, *self.event_chains,
            *self.reference_assets, *self.unresolved,
        )

    def _require_unique_ids(self) -> None:
        groups = (
            ("narrative", [item.narrative_id for item in self.archive_narratives]),
            ("entity", [item.entity_id for item in self.entities]),
            ("chain", [(item.chain_id, item.sequence) for item in self.event_chains]),
            ("asset", [item.asset_id for item in self.reference_assets]),
            ("unresolved", [item.unresolved_id for item in self.unresolved]),
        )
        for label, identities in groups:
            if len(identities) != len(set(identities)):
                raise ContextResearchContractError(f"duplicate {label} identities")


@runtime_checkable
class ContextResearchBackend(Protocol):
    """Async backend boundary; lifecycle remains outside the backend."""

    async def analyze(
        self,
        request: ContextAnalysisRequest,
        execution_context: AgentExecutionContext,
    ) -> ContextResearchDraft:
        """Analyze a request and return a source-grounded draft."""


# Explicit names make the tagged conceptual vocabulary easy to discover.
ArchiveNarrativeDTO = ArchiveNarrative
EventChainDTO = EventChain
ReferenceAssetDTO = ReferenceAsset
ResearchEntityDTO = ResearchEntity
UnresolvedDTO = Unresolved
UnresolvedReferenceDTO = Unresolved


__all__ = [
    "AgentExecutionContext", "ArchiveNarrative", "ArchiveNarrativeDTO", "CancellationSignal",
    "ContextAnalysisRequest", "ContextResearchBackend", "ContextResearchCancelled",
    "ContextResearchContractError",
    "ContextResearchDraft", "EvidenceReference", "EntityFrequencyGrade", "EntityImportance",
    "EntityKind", "EventChain",
    "EventChainDTO", "EventSink", "ResearchEntity", "ResearchEntityDTO",
    "ReferenceAsset", "ReferenceAssetDTO", "UnknownSourceItemReference", "Unresolved", "UnresolvedDTO",
    "UnresolvedReferenceDTO", "UsageSink",
]
