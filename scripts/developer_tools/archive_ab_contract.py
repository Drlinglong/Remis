"""Contracts and deterministic helpers for the Issue #198 archive A/B benchmark.

This module is intentionally developer-tool code.  It does not call a provider
and it never changes the Context Archive gold files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Literal, Mapping


CaseKind = Literal["event_chain", "reference_batch"]
ScenarioKind = Literal["initial", "incremental"]
ArchiveMode = Literal["none", "fresh", "stale"]


def canonical_json(value: Any) -> str:
    """Return stable JSON for hashes and manifests."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    key: str
    version: int
    text: str
    unit_id: str
    group_key: str


@dataclass(frozen=True)
class ArchiveCase:
    case_id: str
    dataset_id: str
    case_kind: CaseKind
    chain_id: str | None
    reference_batch_id: str | None
    source_entries: tuple[SourceEntry, ...]
    gold_facts: tuple[str, ...] = ()
    wiki_evidence_ids: tuple[str, ...] = ()
    wiki_context: str = ""
    chunk_index: int = 0
    chunk_count: int = 1
    chunk_reason: str = "not_chunked"
    adjacent_source_text: tuple[str, ...] = ()
    glossary: Mapping[str, str] = field(default_factory=dict)
    mod_summary: str = ""
    matched_chain_context: str = ""
    old_mod_summary: str = ""
    persisted_archive_context: str = ""
    persisted_old_archive_context: str = ""
    persisted_archive_metadata: Mapping[str, Any] = field(default_factory=dict)
    persisted_old_archive_metadata: Mapping[str, Any] = field(default_factory=dict)
    changed_source_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.case_kind == "event_chain" and not self.chain_id:
            raise ValueError(f"event_chain case requires chain_id: {self.case_id}")
        if self.case_kind == "reference_batch" and not self.reference_batch_id:
            raise ValueError(f"reference_batch case requires reference_batch_id: {self.case_id}")
        if not self.source_entries:
            raise ValueError(f"case has no source entries: {self.case_id}")
        if self.chunk_index < 0 or self.chunk_count < 1 or self.chunk_index >= self.chunk_count:
            raise ValueError(f"invalid chunk metadata: {self.case_id}")

    @property
    def member_source_ids(self) -> tuple[str, ...]:
        return tuple(entry.source_id for entry in self.source_entries)

    @property
    def is_changed(self) -> bool:
        return bool(set(self.member_source_ids) & set(self.changed_source_ids))


@dataclass(frozen=True)
class Recipe:
    provider: str
    model: str
    reasoning: str
    prompt_version: str
    glossary: Mapping[str, str] = field(default_factory=dict)
    retry_policy: str = "same_request_once"
    batch_policy: str = "case_once"
    reference_reuse: str = "disabled"
    provider_revision: str = "unknown"
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 198
    request_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0 or not 0.0 < self.top_p <= 1.0:
            raise ValueError("recipe sampling parameters are out of range")
        if not self.request_fingerprint:
            payload = asdict(self)
            payload["request_fingerprint"] = ""
            object.__setattr__(self, "request_fingerprint", sha256_text(canonical_json(payload)))

    @property
    def fingerprint(self) -> str:
        return sha256_text(canonical_json(asdict(self)))


@dataclass(frozen=True)
class Scenario:
    kind: ScenarioKind
    archive_mode: ArchiveMode
    changed_source_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.kind == "initial" and self.changed_source_ids:
            raise ValueError("initial scenario cannot declare changed source IDs")
        if self.archive_mode == "stale" and self.kind != "incremental":
            raise ValueError("stale archive is only valid for incremental scenarios")


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_tokens + other.cached_tokens,
            self.reasoning_tokens + other.reasoning_tokens,
            self.cost_usd + other.cost_usd,
        )

    def as_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class Candidate:
    arm: Literal["A", "B"]
    translations: Mapping[str, str]
    usage: Usage = Usage()
    prompt_hash: str = ""
    request_fingerprint: str = ""


HARD_ERROR_TAGS = frozenset({
    "missing_source_id",
    "extra_source_id",
    "placeholder_mismatch",
    "entry_count_mismatch",
    "empty_translation",
    "newline_mismatch",
    "escape_mismatch",
    "dynamic_variable_mismatch",
    "color_tag_mismatch",
    "icon_mismatch",
    "format_marker_mismatch",
    "postprocess_validation_error",
})

ERROR_TAGS = frozenset({
    "wrong_referent",
    "broken_causality",
    "inconsistent_entity",
    "branch_misread",
    "missing_story_context",
    "invented_information",
    "terminology_inconsistency",
    "fluency_problem",
})


def case_manifest(case: ArchiveCase) -> dict[str, Any]:
    """Serialize case identity without leaking a candidate or provider output."""

    return {
        "case_id": case.case_id,
        "dataset_id": case.dataset_id,
        "case_kind": case.case_kind,
        "chain_id": case.chain_id,
        "reference_batch_id": case.reference_batch_id,
        "member_source_ids": list(case.member_source_ids),
        "chunk_index": case.chunk_index,
        "chunk_count": case.chunk_count,
        "chunk_reason": case.chunk_reason,
        "wiki_evidence_ids": list(case.wiki_evidence_ids),
        "archive_context_available": bool(case.persisted_archive_context),
        "archive_artifact": dict(case.persisted_archive_metadata),
        "old_archive_artifact": dict(case.persisted_old_archive_metadata),
    }


__all__ = [
    "ArchiveCase", "ArchiveMode", "Candidate", "CaseKind", "ERROR_TAGS",
    "HARD_ERROR_TAGS", "Recipe", "Scenario", "ScenarioKind", "SourceEntry",
    "Usage", "canonical_json", "case_manifest", "sha256_bytes", "sha256_text",
]
