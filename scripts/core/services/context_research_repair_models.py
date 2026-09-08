"""Immutable DTOs for bounded context-research repair packets.

Keeping the packet contract separate from diagnostic policy makes the policy
module easier to audit while preserving the same Pydantic validation rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FailureClass = Literal["repairable", "discard_only", "systemic_corruption"]
CoverageKind = Literal[
    "modeled", "intentionally_unmodeled", "excluded_by_policy", "uninspected",
]
FindingType = Literal[
    "archive_narrative", "entity", "event_chain", "reference_asset", "unresolved", "system",
]

MAX_REPAIR_ATTEMPTS = 2


class CoverageDisposition(BaseModel):
    """The explicit inspection state of one source shard."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    shard_id: str = Field(min_length=1, max_length=300)
    disposition: CoverageKind
    key_shard: bool = False
    source_item_ids: tuple[str, ...] = Field(default=(), max_length=500)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _source_ids_are_unique(self) -> "CoverageDisposition":
        if len(self.source_item_ids) != len(set(self.source_item_ids)):
            raise ValueError("coverage source_item_ids must be unique")
        return self


class CoverageAssessment(BaseModel):
    """Coverage facts and the narrow publication gate derived from them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dispositions: tuple[CoverageDisposition, ...] = Field(default=(), max_length=500)
    blocking_uninspected_shards: tuple[str, ...] = Field(default=(), max_length=500)
    blocks_key_shard_gate: bool = False

    @model_validator(mode="after")
    def _gate_matches_dispositions(self) -> "CoverageAssessment":
        expected = tuple(
            item.shard_id
            for item in self.dispositions
            if item.key_shard and item.disposition == "uninspected"
        )
        if self.blocking_uninspected_shards != expected:
            raise ValueError("coverage gate must only contain key uninspected shards")
        if self.blocks_key_shard_gate != bool(expected):
            raise ValueError("coverage gate flag does not match blocking shards")
        return self


class RepairTarget(BaseModel):
    """One failed finding and the narrow repair contract for it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_type: FindingType
    finding_id: str = Field(min_length=1, max_length=300)
    sequence: int | None = Field(default=None, ge=0)
    failure_codes: tuple[str, ...] = Field(min_length=1, max_length=20)
    classification: FailureClass
    allowed_fields: tuple[str, ...] = Field(default=(), max_length=20)
    source_allow_list: tuple[str, ...] = Field(default=(), max_length=500)
    related_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def _event_identity_is_complete(self) -> "RepairTarget":
        if self.finding_type == "event_chain" and self.sequence is None:
            raise ValueError("event-chain repair targets require sequence")
        return self


class RepairBatch(BaseModel):
    """A deterministic, same-shape group of repair targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_id: str = Field(min_length=1, max_length=100)
    finding_type: FindingType
    allowed_fields: tuple[str, ...] = Field(default=(), max_length=20)
    target_keys: tuple[str, ...] = Field(min_length=1, max_length=10)


class RepairPacket(BaseModel):
    """A provider-agnostic, at-most-two-attempt repair instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "context-repair-packet-v1"
    attempt: int = Field(ge=0, le=MAX_REPAIR_ATTEMPTS)
    max_attempts: int = MAX_REPAIR_ATTEMPTS
    remaining_attempts: int = Field(ge=0, le=MAX_REPAIR_ATTEMPTS)
    targets: tuple[RepairTarget, ...] = Field(default=(), max_length=500)
    repair_batches: tuple[RepairBatch, ...] = Field(default=(), max_length=500)
    batch_count: int = Field(default=0, ge=0, le=500)
    batch_sizes: tuple[int, ...] = Field(default=(), max_length=500)
    valid_source_allow_list: tuple[str, ...] = Field(default=(), max_length=500)
    related_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)
    coverage: CoverageAssessment = Field(default_factory=CoverageAssessment)
    preserve_valid_results: bool = True
    model_call_allowed: bool = False
    systemic_corruption: bool = False

    @model_validator(mode="after")
    def _budget_and_gate_are_consistent(self) -> "RepairPacket":
        expected_remaining = max(0, self.max_attempts - self.attempt)
        if self.max_attempts != MAX_REPAIR_ATTEMPTS:
            raise ValueError("repair packet max_attempts is fixed at two")
        if self.remaining_attempts != expected_remaining:
            raise ValueError("repair packet remaining_attempts is inconsistent")
        expected_allowed = bool(
            self.targets
            and self.remaining_attempts > 0
            and any(item.classification == "repairable" for item in self.targets)
            and all(
                item.source_allow_list
                for item in self.targets
                if item.classification == "repairable"
            )
            and self.valid_source_allow_list
            and not self.systemic_corruption
        )
        if self.model_call_allowed != expected_allowed:
            raise ValueError("model_call_allowed must be derived from repairable targets and budget")
        expected_sizes = tuple(len(batch.target_keys) for batch in self.repair_batches)
        if self.batch_count != len(self.repair_batches) or self.batch_sizes != expected_sizes:
            raise ValueError("repair batch audit fields are inconsistent")
        if any(size > 10 or size < 1 for size in self.batch_sizes):
            raise ValueError("repair batch sizes must be between one and ten")
        return self


__all__ = [
    "CoverageAssessment", "CoverageDisposition", "CoverageKind", "FailureClass",
    "FindingType", "MAX_REPAIR_ATTEMPTS", "RepairBatch", "RepairPacket", "RepairTarget",
]
