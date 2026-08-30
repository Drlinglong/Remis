"""Frozen contracts for deterministic Mod Context candidate governance."""

from __future__ import annotations

from enum import Enum
import re
from typing import Any
import unicodedata

from pydantic import BaseModel, ConfigDict, Field


_ARTICLE_RE = re.compile(r"^(?:a|an|the)(?=\s)")
ENTITY_AGGREGATE_PREFIX = "entity:"


def normalized_match_key(surface: str, source_language: str = "en") -> str:
    """Normalize only deterministic literal aliases for candidate matching."""

    value = unicodedata.normalize("NFKC", str(surface)).casefold()
    name_reference = re.fullmatch(r"\$name_([^$]+)\$", value.strip())
    if name_reference:
        value = name_reference.group(1).replace("_", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = _strip_edge_punctuation(value)
    if _is_english(source_language):
        value = _ARTICLE_RE.sub("", value, count=1)
        value = re.sub(r"\s+", " ", value).strip()
        value = _strip_edge_punctuation(value)
    return value


def candidate_aggregate_key(surface: str, source_language: str = "en") -> str:
    """Return the canonical namespace-preserving aggregate identity."""

    return f"{ENTITY_AGGREGATE_PREFIX}{normalized_match_key(surface, source_language)}"


def _is_english(language: str) -> bool:
    normalized = str(language or "").casefold().replace("_", "-")
    return normalized == "en" or normalized.startswith("en-") or normalized == "english"


def _strip_edge_punctuation(value: str) -> str:
    while value:
        value = value.strip()
        start = 0
        end = len(value)
        while start < end and unicodedata.category(value[start]).startswith(("P", "S")):
            start += 1
        while end > start and unicodedata.category(value[end - 1]).startswith(("P", "S")):
            end -= 1
        trimmed = value[start:end]
        if trimmed == value:
            return value
        value = trimmed
    return ""


class CandidateKind(str, Enum):
    """The bounded semantic role of a source-grounded candidate."""

    ENTITY = "entity"
    GLOSSARY_TERM = "glossary_term"
    NAMED_PHRASE = "named_phrase"
    INCIDENTAL_CONCEPT = "incidental_concept"


class CandidateTier(str, Enum):
    """The deterministic review and delivery tier for a candidate."""

    CORE = "core"
    SECONDARY = "secondary"
    INCIDENTAL = "incidental"


class ContextCandidate(BaseModel):
    """One alias-merged candidate with backend-computed evidence metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_key: str = Field(min_length=1)
    normalized_match_key: str = Field(min_length=1)
    canonical_display_name: str = Field(min_length=1)
    canonical_candidate: str | None = Field(default=None, max_length=500)
    canonical_suggestions: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    semantic_canonical_suggestions: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=20,
    )
    aliases: tuple[str, ...] = Field(min_length=1, max_length=50)
    candidate_kind: CandidateKind
    mention_count: int = Field(default=0, ge=0)
    source_item_coverage: int = Field(default=0, ge=0)
    local_unit_coverage: int = Field(default=0, ge=0)
    event_chain_coverage: int = Field(default=0, ge=0)
    policy_coverage: int = Field(default=0, ge=0)
    tier: CandidateTier
    source_item_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    local_unit_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    event_chain_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    promotion_reasons: tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    summary_eligible: bool = False
    glossary_eligible: bool = False
    audit_only: bool = False

    @property
    def literal_surfaces(self) -> tuple[str, ...]:
        """Expose the literal alias set with a descriptive integration name."""

        return self.aliases


class CandidatePolicy(BaseModel):
    """Policy-only projection keyed by the deterministic aggregate key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_key: str = Field(min_length=1)
    candidate_kind: CandidateKind
    tier: CandidateTier
    policy_coverage: int = Field(default=0, ge=0)
    event_chain_coverage: int = Field(default=0, ge=0)
    summary_eligible: bool = False
    glossary_eligible: bool = False
    audit_only: bool = False
    promotion_reasons: tuple[str, ...] = Field(default_factory=tuple, max_length=10)


class ContextCandidateGovernanceResult(BaseModel):
    """Immutable integration boundary for candidate governance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: tuple[ContextCandidate, ...] = Field(default_factory=tuple, max_length=250)
    policy_by_aggregate_key: dict[str, CandidatePolicy] = Field(default_factory=dict)
    governed_extractions: tuple[Any, ...] = Field(default_factory=tuple)
    synthesis_eligible_aggregate_keys: tuple[str, ...] = Field(default_factory=tuple)
    glossary_eligible_match_keys: tuple[str, ...] = Field(default_factory=tuple)
    source_aliases: dict[str, str] = Field(default_factory=dict)
    raw_extraction_checkpoints: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    source_language: str = "en"
    report: dict[str, Any] = Field(default_factory=dict)

    def aggregate_key_for_surface(self, surface: str) -> str:
        """Use the exact same normalization as the governance service."""

        return candidate_aggregate_key(surface, self.source_language)
