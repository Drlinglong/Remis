"""Developer-only human spot-check queue for archive A/B results.

The queue is append-only.  Its HTTP adapter is responsible for hiding arm and
judge identity until a review has been submitted and revealed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
from typing import Any, Iterable, Mapping

from scripts.developer_tools.archive_ab_contract import ArchiveCase, ERROR_TAGS, Scenario, canonical_json, sha256_text
from scripts.developer_tools.archive_ab_runner import BlindResult, TranslationPair


def developer_review_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Default closed; an explicit developer flag is required outside stable UI."""

    values = environ if environ is not None else os.environ
    return values.get("REMIS_ENABLE_ARCHIVE_AB_REVIEW") == "1"


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    case_id: str
    manifest_id: str
    anonymous_order: tuple[str, str]
    reviewer: str
    selection: str
    error_tags: tuple[str, ...]
    confidence: float
    note: str
    submitted_at: str
    revealed: bool = False
    needs_recheck: bool = False
    supersedes_review_id: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_index(results: Iterable[BlindResult]) -> dict[str, BlindResult]:
    return {result.case_id: result for result in results}


def sample_case_ids(
    pairs: Iterable[TranslationPair],
    results: Iterable[BlindResult],
    *,
    seed: int = 198,
    limit: int = 10,
    filters: Mapping[str, str] | None = None,
    suspicious_first: bool = True,
) -> list[str]:
    """Return unique stratified IDs, prioritising hard/judge-conflict cases."""

    result_by_id = _result_index(results)
    available = [pair for pair in pairs if not pair.skipped and pair.case.case_id in result_by_id]
    filters = filters or {}
    if filters:
        available = [pair for pair in available if _matches(pair, result_by_id[pair.case.case_id], filters)]
    suspicious = [pair for pair in available if _is_suspicious(result_by_id[pair.case.case_id])]
    ordinary = [pair for pair in available if pair not in suspicious]
    rng = random.Random(seed)
    rng.shuffle(suspicious)
    rng.shuffle(ordinary)
    ordered = (suspicious + ordinary) if suspicious_first else (ordinary + suspicious)
    return list(dict.fromkeys(pair.case.case_id for pair in ordered))[:limit]


def _matches(pair: TranslationPair, result: BlindResult, filters: Mapping[str, str]) -> bool:
    case = pair.case
    scenario = pair.scenario or Scenario("initial", "fresh")
    expected = {
        "dataset_id": case.dataset_id,
        "case_kind": case.case_kind,
        "chain_id": case.chain_id or "",
        "reference_batch_id": case.reference_batch_id or "",
        "llm_winner": result.winner,
        "scenario": scenario.kind,
        "archive_mode": scenario.archive_mode,
        "confidence_band": "high" if result.confidence >= 0.8 else "low",
    }
    for key, value in filters.items():
        if key == "error_tag":
            if value not in result.error_tags:
                return False
            continue
        if expected.get(key) != value:
            return False
    return True


def _is_suspicious(result: BlindResult) -> bool:
    return bool(result.needs_adjudication or not all(check.passed for check in result.hard_checks.values()))


def build_review_payload(
    pair: TranslationPair,
    result: BlindResult,
    manifest_id: str,
) -> dict[str, Any]:
    """Build pre-submit blind data, or post-submit data with an explicit reveal."""

    if pair.skipped or pair.candidate_a is None or pair.candidate_b is None:
        raise ValueError(f"skipped cases cannot enter review queue: {pair.case.case_id}")
    order = result.presentation_orders[0]
    candidates = {"A": pair.candidate_a.translations, "B": pair.candidate_b.translations}
    payload: dict[str, Any] = {
        "case_id": pair.case.case_id,
        "manifest_id": manifest_id,
        "dataset_id": pair.case.dataset_id,
        "case_kind": pair.case.case_kind,
        "chain_id": pair.case.chain_id,
        "reference_batch_id": pair.case.reference_batch_id,
        "chunk": {"index": pair.case.chunk_index, "count": pair.case.chunk_count, "reason": pair.case.chunk_reason},
        "source_entries": [asdict(entry) for entry in pair.case.source_entries],
        "gold_facts": list(pair.case.gold_facts),
        "wiki_evidence_ids": list(pair.case.wiki_evidence_ids),
        "anonymous_candidates": [candidates[arm] for arm in order],
        "anonymous_labels": ["left", "right"],
        "instructions": "Select left/right/tie/uncertain before reveal; do not infer archive arm.",
        "revealed": False,
    }
    return payload


def reveal_review_payload(payload: Mapping[str, Any], record: ReviewRecord, result: BlindResult) -> dict[str, Any]:
    """Reveal only from an already submitted append-only record."""

    if record.case_id != payload.get("case_id") or record.manifest_id != payload.get("manifest_id"):
        raise ValueError("review record does not match payload")
    revealed = dict(payload)
    revealed["revealed"] = True
    revealed["reveal"] = {"actual_order": list(record.anonymous_order), "llm_winner": result.winner, "llm_evidence": list(result.evidence), "llm_error_tags": list(result.error_tags)}
    return revealed


def make_reveal_record(record: ReviewRecord) -> ReviewRecord:
    """Append a reveal event without mutating the original human judgment."""

    if record.revealed:
        return record
    reveal_id = sha256_text(canonical_json({"reveals": record.review_id, "at": _utc_now()}))[:16]
    return replace(record, review_id=reveal_id, revealed=True, supersedes_review_id=record.review_id, submitted_at=_utc_now())


class AppendOnlyReviewStore:
    """JSONL audit store; corrections append a new record instead of overwriting."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: ReviewRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(asdict(record)) + "\n")

    def records(self) -> list[ReviewRecord]:
        if not self.path.exists():
            return []
        return [ReviewRecord(**json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_review_record(
    payload: Mapping[str, Any], *, reviewer: str, selection: str, anonymous_order: Iterable[str], error_tags: Iterable[str] = (), confidence: float = 0.0, note: str = "", needs_recheck: bool = False, supersedes_review_id: str | None = None,
) -> ReviewRecord:
    if selection not in {"left", "right", "tie", "uncertain", "skip"}:
        raise ValueError("selection must be left, right, tie, uncertain, or skip")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    tags = tuple(str(tag) for tag in error_tags)
    invalid_tags = set(tags) - ERROR_TAGS
    if invalid_tags:
        raise ValueError(f"unknown review error tags: {sorted(invalid_tags)}")
    review_key = canonical_json({"case_id": payload["case_id"], "manifest_id": payload["manifest_id"], "at": _utc_now(), "reviewer": reviewer})
    return ReviewRecord(
        review_id=sha256_text(review_key)[:16], case_id=str(payload["case_id"]), manifest_id=str(payload["manifest_id"]),
        anonymous_order=tuple(str(item) for item in anonymous_order), reviewer=reviewer,
        selection=selection, error_tags=tuple(sorted(set(tags))), confidence=confidence, note=note,
        submitted_at=_utc_now(), revealed=False, needs_recheck=needs_recheck, supersedes_review_id=supersedes_review_id,
    )


def review_summary(records: Iterable[ReviewRecord], result_by_id: Mapping[str, BlindResult]) -> dict[str, Any]:
    rows: dict[tuple[str, str], ReviewRecord] = {}
    for row in records:
        if row.revealed:
            continue
        rows[(row.manifest_id, row.case_id)] = row
    judgments = list(rows.values())
    covered = {row.case_id for row in judgments}
    comparable = [row for row in judgments if row.selection not in {"uncertain", "skip"}]
    matches = sum(_human_matches_llm(row, result_by_id.get(row.case_id)) for row in comparable)
    return {
        "reviewed_case_count": len(judgments), "record_count": len(judgments), "review_coverage_is_case_unique": True,
        "selection_counts": {value: sum(row.selection == value for row in judgments) for value in ("left", "right", "tie", "uncertain", "skip")},
        "human_llm_agreement_rate": matches / len(comparable) if comparable else None,
        "unreviewed_case_ids": sorted(set(result_by_id) - covered),
    }


def _human_matches_llm(record: ReviewRecord, result: BlindResult | None) -> int:
    if result is None or record.selection in {"uncertain", "skip"}:
        return 0
    actual = {"left": record.anonymous_order[0] if record.anonymous_order else "", "right": record.anonymous_order[1] if len(record.anonymous_order) > 1 else "", "tie": "tie"}[record.selection]
    return int(actual == result.winner)


__all__ = [
    "AppendOnlyReviewStore", "ReviewRecord", "build_review_payload", "developer_review_enabled", "reveal_review_payload",
    "make_reveal_record", "make_review_record", "review_summary", "sample_case_ids",
]
