"""Checkpoint-safe contracts for global narrative chain reconciliation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    links: list[_ModelLink] = Field(max_length=8)

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_assignment_state(cls, value: Any) -> Any:
        """State is backend-derived from links, not an independent model claim."""

        if not isinstance(value, dict) or "assignment_state" not in value:
            return value
        normalized = dict(value)
        normalized.pop("assignment_state", None)
        return normalized


class StandaloneDeliveryJustification(BaseModel):
    """Evidence that a one-unit event merits its own translation summary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    unit_id: str = Field(pattern=r"^unit_\d+$")
    independent_event_basis: str = Field(min_length=1, max_length=500)
    translation_value: str = Field(min_length=1, max_length=500)


class EventChainDefinition(BaseModel):
    """One concrete delivery chain, never a parent-story umbrella."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chain_id: str = Field(min_length=1, max_length=200)
    chain_level: str = Field(default="delivery_chain", pattern=r"^delivery_chain$")
    story_scope: str = Field(
        pattern=(
            r"^(concrete_child_quest|standalone_event|parent_story|"
            r"origin_level_story|cross_quest_macro)$"
        ),
    )
    parent_story_id: str | None = Field(default=None, max_length=200)
    event: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0)
    participants: list[str] = Field(default_factory=list, max_length=20)
    consequence: str | None = Field(default=None, max_length=500)
    boundary_includes: str | None = Field(default=None, max_length=500)
    boundary_excludes: str | None = Field(default=None, max_length=500)
    anchor_unit_ids: EvidenceUnitIds = Field(default_factory=list, max_length=8)
    evidence_unit_ids: EvidenceUnitIds = Field(min_length=1, max_length=5)
    standalone_justification: StandaloneDeliveryJustification | None = None


class ParentStoryDefinition(BaseModel):
    """Archive-only hierarchy node that cannot receive delivery assignments."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    story_id: str = Field(min_length=1, max_length=200)
    story_scope: str = Field(
        pattern=r"^(parent_story|origin_level_story|cross_quest_macro)$",
    )
    summary: str = Field(min_length=1, max_length=800)
    child_chain_ids: list[str] = Field(min_length=1, max_length=40)
    evidence_unit_ids: EvidenceUnitIds = Field(min_length=1, max_length=10)


def normalize_parent_story_ownership(
    parents: list[ParentStoryDefinition],
    chains: list[EventChainDefinition],
) -> None:
    """Resolve harmless one-child/multi-parent drift without changing delivery."""

    parent_by_id = {parent.story_id: parent for parent in parents}
    chain_by_id = {chain.chain_id: chain for chain in chains}
    claims: dict[str, list[str]] = {}
    for parent in parents:
        for child_id in parent.child_chain_ids:
            owners = claims.setdefault(child_id, [])
            if parent.story_id not in owners:
                owners.append(parent.story_id)

    owner_by_child: dict[str, str] = {}
    for chain in chains:
        declared = chain.parent_story_id
        if declared in parent_by_id:
            owner_by_child[chain.chain_id] = declared
        elif declared is None and claims.get(chain.chain_id):
            owner = claims[chain.chain_id][0]
            owner_by_child[chain.chain_id] = owner
            chain.parent_story_id = owner

    for parent in parents:
        normalized = [
            child_id
            for child_id in dict.fromkeys(parent.child_chain_ids)
            if child_id not in chain_by_id
            or owner_by_child.get(child_id, parent.story_id) == parent.story_id
        ]
        normalized.extend(
            chain.chain_id
            for chain in chains
            if owner_by_child.get(chain.chain_id) == parent.story_id
            and chain.chain_id not in normalized
        )
        parent.child_chain_ids = normalized
    parents[:] = [parent for parent in parents if parent.child_chain_ids]


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

    @model_validator(mode="before")
    @classmethod
    def normalize_exclusive_targets(cls, value: Any) -> Any:
        """Honor the explicit resolution when optional target fields conflict."""

        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        resolution = normalized.get("resolution")
        delivery_resolutions = {
            "merge_into", "keep_as_delivery_chain", "split_across",
        }
        if resolution in delivery_resolutions:
            normalized["parent_story_id"] = None
        else:
            normalized["final_chain_ids"] = []
            if resolution != "promote_to_parent_story":
                normalized["parent_story_id"] = None
        return normalized


class _CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_stories: list[ParentStoryDefinition] = Field(default_factory=list, max_length=40)
    final_chains: list[EventChainDefinition] = Field(default_factory=list, max_length=80)
    proposal_resolutions: list[LocalChainDisposition] = Field(
        default_factory=list, max_length=500
    )

    @model_validator(mode="before")
    @classmethod
    def require_explicit_story_scopes(cls, value: Any) -> Any:
        """Prevent model output from inheriting a permissive internal default."""

        if not isinstance(value, dict):
            return value
        missing_final = [
            str(item.get("chain_id") or "<unknown>")
            for item in value.get("final_chains", [])
            if isinstance(item, dict) and "story_scope" not in item
        ]
        missing_parent = [
            str(item.get("story_id") or "<unknown>")
            for item in value.get("parent_stories", [])
            if isinstance(item, dict) and "story_scope" not in item
        ]
        if missing_final or missing_parent:
            raise ValueError(
                "Catalog nodes require explicit story_scope classification: "
                f"final_chains={missing_final}, parent_stories={missing_parent}"
            )
        return value

    @model_validator(mode="after")
    def normalize_parent_ownership(self) -> "_CatalogResponse":
        normalize_parent_story_ownership(self.parent_stories, self.final_chains)
        return self


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
    """Require final chain identities to retain grounded local anchors."""

    card_by_id = {card["proposal_id"]: card for card in cards}
    allowed: dict[str, set[str]] = {}
    for disposition in dispositions:
        card = card_by_id[disposition.proposal_id]
        source_units = {
            *card.get("primary_unit_ids", ()),
            *card.get("evidence_unit_ids", ()),
        }
        for chain_id in disposition.final_chain_ids:
            allowed.setdefault(chain_id, set()).update(source_units)
    invalid = {
        chain.chain_id: sorted(set(chain.anchor_unit_ids) - allowed.get(chain.chain_id, set()))
        for chain in chains
        if not set(chain.anchor_unit_ids) <= allowed.get(chain.chain_id, set())
    }
    if invalid:
        raise ValueError(
            "Final chain anchors must come from local primary hints or grounded event "
            f"evidence: {invalid}"
        )


def validate_delivery_chain_scopes(
    chains: Sequence[EventChainDefinition],
    dispositions: Sequence[LocalChainDisposition],
    cards: Sequence[dict[str, Any]],
) -> None:
    """Keep macro stories out of delivery and gate one-unit exceptions."""

    prohibited_scopes = {"parent_story", "origin_level_story", "cross_quest_macro"}
    invalid_macro = {
        chain.chain_id: chain.story_scope
        for chain in chains
        if chain.story_scope in prohibited_scopes
    }
    if invalid_macro:
        raise ValueError(
            "Parent, origin-level, and cross-quest macro stories cannot be delivery "
            f"targets: {invalid_macro}"
        )

    card_by_id = {card["proposal_id"]: card for card in cards}
    grounded_units: dict[str, set[str]] = {}
    for disposition in dispositions:
        card = card_by_id.get(disposition.proposal_id, {})
        source_units = {
            *card.get("primary_unit_ids", ()),
            *card.get("evidence_unit_ids", ()),
        }
        for chain_id in disposition.final_chain_ids:
            grounded_units.setdefault(chain_id, set()).update(source_units)

    invalid_singletons: dict[str, str] = {}
    for chain in chains:
        units = grounded_units.get(chain.chain_id, set())
        if len(units) != 1:
            continue
        justification = chain.standalone_justification
        unit_id = next(iter(units))
        if chain.story_scope != "standalone_event":
            invalid_singletons[chain.chain_id] = (
                "single-unit chain must merge into its causally related concrete child "
                "quest or declare standalone_event"
            )
        elif justification is None:
            invalid_singletons[chain.chain_id] = (
                "standalone_event requires independent_event_basis and translation_value"
            )
        elif justification.unit_id != unit_id:
            invalid_singletons[chain.chain_id] = (
                f"standalone justification names {justification.unit_id}, expected {unit_id}"
            )
    if invalid_singletons:
        raise ValueError(
            "Single-unit delivery chains require a grounded standalone exception; "
            "otherwise merge them into the directly causal concrete child quest: "
            f"{invalid_singletons}"
        )


def _duplicates(values: Any) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)
