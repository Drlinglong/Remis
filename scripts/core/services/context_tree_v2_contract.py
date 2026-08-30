"""Versioned, model-safe contracts for the context archive tree workflow v2.

The v10 contracts remain in their existing modules.  These contracts deliberately
keep the tree relationship layer separate: extraction owns local fragment cards
and unit routes, while catalog owns only IDs and the program owns delivery.
"""

from __future__ import annotations

from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scripts.core.neologism_extraction import (
    EntityContribution,
    EventChainContribution,
    FactContribution,
    RelationshipContribution,
    TermContribution,
)


TREE_V2_SCHEMA_VERSION = "context-tree-v2"
TREE_V2_PROMPT_VERSION = "context-archive-tree-v2"
TREE_V2_CHECKPOINT_COMPATIBILITY_VERSION = "context-analysis-tree-v2"

TreeRoute = Literal["narrative", "reference_asset", "no_context"]


class ChunkEdgeMetadata(BaseModel):
    """Stable boundary facts supplied to one extraction call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_index: int = Field(ge=0)
    chunk_count: int = Field(ge=1)
    core_unit_ids: list[str] = Field(min_length=1, max_length=80)
    edge_before_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    edge_after_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    has_previous_core_chunk: bool = False
    has_next_core_chunk: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> "ChunkEdgeMetadata":
        if self.chunk_index >= self.chunk_count:
            raise ValueError("chunk_index must be smaller than chunk_count")
        all_ids = [
            *self.core_unit_ids,
            *self.edge_before_unit_ids,
            *self.edge_after_unit_ids,
        ]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("chunk edge unit identities must be unique")
        if set(self.core_unit_ids) & {
            *self.edge_before_unit_ids,
            *self.edge_after_unit_ids,
        }:
            raise ValueError("core units cannot also be edge units")
        return self


class LocalFragment(BaseModel):
    """An immutable, batch-local narrative result used by the global catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fragment_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1200)
    unit_ids: list[str] = Field(min_length=1, max_length=80)
    continuation_cues: str | None = Field(default=None, max_length=500)
    boundary_includes: str | None = Field(default=None, max_length=500)
    boundary_excludes: str | None = Field(default=None, max_length=500)
    touches_chunk_start: bool = False
    touches_chunk_end: bool = False

    @model_validator(mode="after")
    def validate_units(self) -> "LocalFragment":
        if len(self.unit_ids) != len(set(self.unit_ids)):
            raise ValueError("fragment unit identities must be unique")
        return self


class UnitRoute(BaseModel):
    """The only extraction-owned delivery role for one core local unit."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    local_unit_id: str = Field(min_length=1, max_length=200)
    route: TreeRoute
    fragment_ids: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="before")
    @classmethod
    def accept_route_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "route" not in normalized:
            for alias in ("role", "context_role"):
                if alias in normalized:
                    normalized["route"] = normalized.pop(alias)
                    break
        return normalized

    @model_validator(mode="after")
    def validate_route(self) -> "UnitRoute":
        if len(self.fragment_ids) != len(set(self.fragment_ids)):
            raise ValueError("unit route fragment identities must be unique")
        if self.route == "narrative" and not self.fragment_ids:
            raise ValueError("narrative routes require at least one fragment")
        if self.route != "narrative" and self.fragment_ids:
            raise ValueError(
                "reference_asset and no_context routes cannot receive event fragments"
            )
        return self

    @property
    def role(self) -> TreeRoute:
        """Compatibility name for callers that call the route a role."""

        return self.route


class UnresolvedFragmentReference(BaseModel):
    """A preserved unit-to-fragment link that repair could not resolve."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    local_unit_id: str = Field(min_length=1, max_length=200)
    fragment_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    repair_attempts: int = Field(default=1, ge=0, le=1)


class ContextTreeV2Extraction(BaseModel):
    """Full and terms-only extraction contract for one source chunk."""

    model_config = ConfigDict(extra="forbid")

    local_fragments: list[LocalFragment] = Field(default_factory=list, max_length=80)
    unit_routes: list[UnitRoute] = Field(default_factory=list, max_length=80)
    entities: list[EntityContribution] = Field(default_factory=list, max_length=50)
    terms: list[TermContribution] = Field(default_factory=list, max_length=100)
    facts: list[FactContribution] = Field(default_factory=list, max_length=50)
    events: list[EventChainContribution] = Field(default_factory=list, max_length=50)
    relationships: list[RelationshipContribution] = Field(default_factory=list, max_length=100)
    unresolved_fragment_references: list[UnresolvedFragmentReference] = Field(
        default_factory=list, max_length=80
    )
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.unresolved_fragment_references

    def contribution_lists(self) -> tuple[Sequence[Any], ...]:
        return (self.terms, self.entities, self.facts, self.events, self.relationships)


class FragmentRepairResponse(BaseModel):
    """Targeted model response: only definitions for missing fragment IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    local_fragments: list[LocalFragment] = Field(default_factory=list, max_length=8)


class TreeStory(BaseModel):
    """A stable archive container; it carries no temporal ordering."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    story_id: str = Field(min_length=1, max_length=200)
    group_ids: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_groups(self) -> "TreeStory":
        if len(self.group_ids) != len(set(self.group_ids)):
            raise ValueError("story group identities must be unique")
        return self


class TreeGroup(BaseModel):
    """One event group whose fragment_ids are the only ordered relation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    group_id: str = Field(min_length=1, max_length=200)
    fragment_ids: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_fragments(self) -> "TreeGroup":
        if len(self.fragment_ids) != len(set(self.fragment_ids)):
            raise ValueError("group fragment identities must be unique")
        return self


class ContextTreeCatalog(BaseModel):
    """ID-only global catalog response; summaries never come back from the model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stories: list[TreeStory] = Field(default_factory=list, max_length=80)
    groups: list[TreeGroup] = Field(default_factory=list, max_length=80)
    unresolved_fragment_ids: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_ids(self) -> "ContextTreeCatalog":
        story_ids = [story.story_id for story in self.stories]
        group_ids = [group.group_id for group in self.groups]
        if len(story_ids) != len(set(story_ids)):
            raise ValueError("story identities must be unique")
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("group identities must be unique")
        unknown_story_groups = {
            group_id for story in self.stories for group_id in story.group_ids
            if group_id not in set(group_ids)
        }
        if unknown_story_groups:
            raise ValueError(
                f"stories referenced unknown groups: {sorted(unknown_story_groups)}"
            )
        unresolved = self.unresolved_fragment_ids
        if len(unresolved) != len(set(unresolved)):
            raise ValueError("unresolved fragment identities must be unique")
        return self


class TreeCatalogResult(BaseModel):
    """Backend result around the ID-only catalog contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog: ContextTreeCatalog
    repair_count: int = Field(default=0, ge=0, le=1)
    repair_reason: str | None = None
    repair_detail: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ProjectedUnitRoute(BaseModel):
    """Program projection of unit -> fragment -> group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    local_unit_id: str = Field(min_length=1, max_length=200)
    route: TreeRoute
    fragment_ids: list[str] = Field(default_factory=list, max_length=8)
    group_ids: list[str] = Field(default_factory=list, max_length=80)
    unresolved_fragment_ids: list[str] = Field(default_factory=list, max_length=8)
    receives_event_context: bool


class TreeProjectionResult(BaseModel):
    """All deterministic delivery projections for one catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_routes: list[ProjectedUnitRoute] = Field(default_factory=list, max_length=500)
    unresolved_fragment_references: list[UnresolvedFragmentReference] = Field(
        default_factory=list, max_length=80
    )


class EventGroupContext(BaseModel):
    """Program-built group context; fragment order is preserved inside a group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1, max_length=200)
    fragment_ids: list[str] = Field(min_length=1, max_length=80)
    summary_bullets: list[str] = Field(min_length=1, max_length=80)


class TranslationContextProjection(BaseModel):
    """Final program projection used by a translator, never model-synthesized."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    local_unit_id: str = Field(min_length=1, max_length=200)
    route: TreeRoute
    project_summary: str = ""
    event_groups: list[EventGroupContext] = Field(default_factory=list, max_length=80)
    unresolved_fragment_ids: list[str] = Field(default_factory=list, max_length=8)

    @property
    def receives_event_context(self) -> bool:
        return self.route == "narrative" and bool(self.event_groups)
