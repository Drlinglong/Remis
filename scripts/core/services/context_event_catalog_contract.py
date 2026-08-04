"""Checkpoint-safe contracts for global narrative chain reconciliation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from scripts.core.context_local_units import DeliveryAssignment
from scripts.core.context_unit_id_contract import EvidenceUnitIds
from scripts.core.neologism_extraction import EventChainContribution


class _ModelLink(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_chain_id: str = Field(min_length=1, max_length=200)
    relation: str = Field(pattern=r"^(primary_member|supporting_context|theme_related)$")
    confidence: float = Field(ge=0.0, le=1.0)


class _ModelAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    local_unit_id: str = Field(pattern=r"^unit_\d+$")
    assignment_state: str = Field(pattern=r"^(assigned|unassigned)$")
    links: list[_ModelLink] = Field(default_factory=list, max_length=8)


class EventChainDefinition(BaseModel):
    """One concrete delivery chain, never a parent-story umbrella."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chain_id: str = Field(min_length=1, max_length=200)
    chain_level: str = Field(default="delivery_chain", pattern=r"^delivery_chain$")
    parent_story_id: str | None = Field(default=None, max_length=200)
    event: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0)
    participants: list[str] = Field(default_factory=list, max_length=20)
    consequence: str | None = Field(default=None, max_length=500)
    boundary_includes: str | None = Field(default=None, max_length=500)
    boundary_excludes: str | None = Field(default=None, max_length=500)
    anchor_unit_ids: EvidenceUnitIds = Field(default_factory=list, max_length=8)
    evidence_unit_ids: EvidenceUnitIds = Field(min_length=1, max_length=5)


class ParentStoryDefinition(BaseModel):
    """Archive-only hierarchy node that cannot receive delivery assignments."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    story_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=800)
    child_chain_ids: list[str] = Field(min_length=2, max_length=40)
    evidence_unit_ids: EvidenceUnitIds = Field(min_length=1, max_length=10)


class LocalChainDisposition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proposal_id: str = Field(min_length=1, max_length=80)
    resolution: str = Field(
        pattern=(
            r"^(merge_into|keep_as_delivery_chain|promote_to_parent_story|"
            r"reject_non_event|split_across|unresolved)$"
        )
    )
    final_chain_ids: list[str] = Field(default_factory=list, max_length=8)
    parent_story_id: str | None = Field(default=None, max_length=200)


class _CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_stories: list[ParentStoryDefinition] = Field(default_factory=list, max_length=40)
    final_chains: list[EventChainDefinition] = Field(default_factory=list, max_length=80)
    proposal_resolutions: list[LocalChainDisposition] = Field(
        default_factory=list, max_length=500
    )


class _AssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[_ModelAssignment] = Field(default_factory=list, max_length=80)


class EventChainCatalogResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_stories: list[ParentStoryDefinition] = Field(default_factory=list, max_length=40)
    final_chains: list[EventChainDefinition] = Field(default_factory=list, max_length=80)
    proposal_resolutions: list[LocalChainDisposition] = Field(
        default_factory=list, max_length=500
    )
    local_chain_cards: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    repair_count: int = Field(default=0, ge=0, le=1)
    repair_reason: str | None = None
    repair_detail: str | None = None


class EventAssignmentBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[DeliveryAssignment] = Field(default_factory=list, max_length=80)
    repair_count: int = Field(default=0, ge=0, le=1)
    repair_reason: str | None = None
    repair_detail: str | None = None


@dataclass(frozen=True)
class EventReconciliationResult:
    events: list[EventChainContribution]
    delivery_assignments: list[DeliveryAssignment]
    diagnostics: dict[str, Any]


def validate_parent_stories(
    parents: Sequence[ParentStoryDefinition],
    chains: Sequence[EventChainDefinition],
    valid_units: set[str],
) -> set[str]:
    """Validate the non-delivery hierarchy and return its identities."""

    parent_ids = [parent.story_id for parent in parents]
    duplicate = _duplicates(parent_id.casefold() for parent_id in parent_ids)
    if duplicate:
        raise ValueError(f"Parent story identities must be unique: {duplicate}")
    valid_parents = set(parent_ids)
    valid_chains = {chain.chain_id for chain in chains}
    collisions = valid_parents & valid_chains
    if collisions:
        raise ValueError(f"Parent stories cannot be delivery chains: {sorted(collisions)}")
    unknown_children = {
        child for parent in parents for child in parent.child_chain_ids
        if child not in valid_chains
    }
    unknown_evidence = {
        unit_id for parent in parents for unit_id in parent.evidence_unit_ids
        if unit_id not in valid_units
    }
    child_parents = Counter(child for parent in parents for child in parent.child_chain_ids)
    duplicate_children = sorted(child for child, count in child_parents.items() if count > 1)
    declared_parent = {
        child: parent.story_id for parent in parents for child in parent.child_chain_ids
    }
    inconsistent_links = {
        chain.chain_id
        for chain in chains
        if chain.parent_story_id != declared_parent.get(chain.chain_id)
    }
    if unknown_children or unknown_evidence or duplicate_children or inconsistent_links:
        raise ValueError(
            "Parent story hierarchy invalid: "
            f"unknown_children={sorted(unknown_children)}, "
            f"unknown_evidence={sorted(unknown_evidence)}, "
            f"duplicate_children={duplicate_children}, "
            f"inconsistent_links={sorted(inconsistent_links)}"
        )
    return valid_parents


def validate_anchor_sources(
    chains: Sequence[EventChainDefinition],
    dispositions: Sequence[LocalChainDisposition],
    cards: Sequence[dict[str, Any]],
) -> None:
    """Require final chain identities to retain local primary anchors."""

    card_by_id = {card["proposal_id"]: card for card in cards}
    allowed: dict[str, set[str]] = {}
    for disposition in dispositions:
        card = card_by_id[disposition.proposal_id]
        source_units = set(card.get("primary_unit_ids", ()))
        for chain_id in disposition.final_chain_ids:
            allowed.setdefault(chain_id, set()).update(source_units)
    invalid = {
        chain.chain_id: sorted(set(chain.anchor_unit_ids) - allowed.get(chain.chain_id, set()))
        for chain in chains
        if not set(chain.anchor_unit_ids) <= allowed.get(chain.chain_id, set())
    }
    if invalid:
        raise ValueError(f"Final chain anchors must come from local primary hints: {invalid}")


def _duplicates(values: Any) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)
