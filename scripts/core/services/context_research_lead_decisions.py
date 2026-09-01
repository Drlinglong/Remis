"""Sparse Lead decisions applied on top of collected child findings.

Lead is not a second findings compiler.  It returns only cross-shard decisions;
reducers start from the complete collector result and preserve every finding
that a decision does not explicitly name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FindingKind = Literal[
    "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
]


class EventMemberDecision(BaseModel):
    """Regroup selected members into one ordered event-chain step."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    chain_id: str = Field(
        min_length=1,
        max_length=240,
        description=(
            "New canonical output chain ID. This names the regrouped result and is never an "
            "input finding identity."
        ),
    )
    sequence: int = Field(ge=0)
    finding_ids: tuple[str, ...] = Field(
        default=(),
        max_length=100,
        description=(
            "Exact existing event finding IDs copied from child decision_index entries. Never "
            "put the new chain_id here."
        ),
    )
    local_unit_ids: tuple[str, ...] = Field(
        default=(),
        max_length=100,
        description=(
            "Exact existing local unit IDs from child decision_index entries. Prefer these for "
            "cross-shard regrouping when finding identities differ."
        ),
    )

    @model_validator(mode="after")
    def _requires_members(self) -> "EventMemberDecision":
        if not self.finding_ids and not self.local_unit_ids:
            raise ValueError("event member decision must name findings or local units")
        return self


class EntityMergeDecision(BaseModel):
    """Merge duplicate entity finding identities into one canonical identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    canonical_finding_id: str = Field(min_length=1, max_length=240)
    merged_finding_ids: tuple[str, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _canonical_not_merged(self) -> "EntityMergeDecision":
        if self.canonical_finding_id in self.merged_finding_ids:
            raise ValueError("canonical entity finding cannot also be merged into itself")
        return self


class FindingDiscardDecision(BaseModel):
    """Discard one explicitly named finding with an auditable reason."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    finding_kind: FindingKind
    finding_id: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=500)


class FindingPatchDecision(BaseModel):
    """Apply bounded fields to one finding; it is not a replacement document."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    finding_kind: FindingKind
    finding_id: str = Field(min_length=1, max_length=240)
    fields: Mapping[str, Any] = Field(min_length=1, max_length=20)


class LeadRepairFinding(BaseModel):
    """Optional sparse repair payload for one existing finding identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    finding_kind: FindingKind
    finding_id: str = Field(min_length=1, max_length=240)
    fields: Mapping[str, Any] = Field(min_length=1, max_length=20)


class LeadResearchDecisions(BaseModel):
    """Sparse cross-shard decisions; no complete findings collection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_members: tuple[EventMemberDecision, ...] = Field(default=(), max_length=500)
    entity_merges: tuple[EntityMergeDecision, ...] = Field(default=(), max_length=200)
    discards: tuple[FindingDiscardDecision, ...] = Field(default=(), max_length=500)
    patches: tuple[FindingPatchDecision, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def _unique_actions(self) -> "LeadResearchDecisions":
        event_keys = [(item.chain_id, item.sequence) for item in self.event_members]
        direct_keys = [(item.finding_kind, item.finding_id) for item in self.discards]
        patch_keys = [(item.finding_kind, item.finding_id) for item in self.patches]
        if len(event_keys) != len(set(event_keys)):
            raise ValueError("lead event chain_id/sequence pairs must be unique")
        if len(direct_keys) != len(set(direct_keys)):
            raise ValueError("lead discard finding identities must be unique")
        if len(patch_keys) != len(set(patch_keys)):
            raise ValueError("lead patch finding identities must be unique")
        if set(direct_keys) & set(patch_keys):
            raise ValueError("a finding cannot be discarded and patched together")
        return self

    def named_finding_ids(self) -> tuple[tuple[str, str], ...]:
        """Return all finding identities explicitly named by a decision."""

        values = [
            ("event_chains", item)
            for decision in self.event_members for item in decision.finding_ids
        ]
        values.extend(("entities", item.canonical_finding_id) for item in self.entity_merges)
        values.extend(
            ("entities", item)
            for decision in self.entity_merges for item in decision.merged_finding_ids
        )
        values.extend((item.finding_kind, item.finding_id) for item in self.discards)
        values.extend((item.finding_kind, item.finding_id) for item in self.patches)
        return tuple(dict.fromkeys(values))


class LeadResearchResult(BaseModel):
    """Lead output containing decisions only, plus optional sparse repairs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decisions: LeadResearchDecisions = Field(default_factory=LeadResearchDecisions)
    repair_findings: tuple[LeadRepairFinding, ...] = Field(default=(), max_length=200)
    notes: str | None = Field(default=None, max_length=2_000)


__all__ = [
    "EntityMergeDecision", "EventMemberDecision", "FindingDiscardDecision",
    "FindingKind", "FindingPatchDecision", "LeadRepairFinding", "LeadResearchDecisions",
    "LeadResearchResult",
]
