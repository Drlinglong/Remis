"""Focused, persistence-free contracts for the context-tree v2 candidate slice.

The v10 candidate contracts remain intentionally untouched.  These models are
the small boundary used by the v2 candidate governance and entity-digest
services while the surrounding tree workflow is still being integrated.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TreeCandidateGrade(str, Enum):
    """Program-owned grade derived from distinct local-unit coverage."""

    A = "A"
    B = "B"
    C = "C"


class TreeCandidateKind(str, Enum):
    """Candidate roles needed by the v2 digest boundary."""

    ENTITY = "entity"
    TERM = "term"


class TreeCandidate(BaseModel):
    """An alias-merged candidate with source-grounded coverage evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, max_length=240)
    canonical_name: str = Field(min_length=1, max_length=500)
    aliases: tuple[str, ...] = Field(min_length=1, max_length=100)
    kind: TreeCandidateKind
    local_unit_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    source_item_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=1000)
    event_group_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    local_descriptions: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    mention_count: int = Field(default=0, ge=0)
    local_unit_coverage: int = Field(default=0, ge=0)
    automatic_grade: TreeCandidateGrade
    grade: TreeCandidateGrade
    grade_source: str = Field(default="automatic", max_length=40)
    manual_grade_override: TreeCandidateGrade | None = None

    @property
    def is_digest_eligible(self) -> bool:
        """Only A/B entities may receive an entity digest call."""

        return self.kind is TreeCandidateKind.ENTITY and self.grade in {
            TreeCandidateGrade.A,
            TreeCandidateGrade.B,
        }


class TreeCandidateGovernanceResult(BaseModel):
    """Candidate governance output before or after semantic entity merging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "context-tree-v2-candidates-v1"
    candidates: tuple[TreeCandidate, ...] = Field(default_factory=tuple, max_length=500)
    source_language: str = "en"
    report: dict[str, Any] = Field(default_factory=dict)

    def candidate_for(self, candidate_id: str) -> TreeCandidate | None:
        """Return a candidate by its stable aggregate identity."""

        return next(
            (candidate for candidate in self.candidates if candidate.candidate_id == candidate_id),
            None,
        )


class SemanticEntityMerge(BaseModel):
    """Model suggestion for a semantic merge, validated by the service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_candidate_id: str = Field(min_length=1, max_length=240)
    member_candidate_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)


class EntityDigest(BaseModel):
    """A validated digest for one final A/B entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=4000)
    evidence_unit_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    semantic_merge: SemanticEntityMerge | None = None
