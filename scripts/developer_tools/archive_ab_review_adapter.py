"""Safe local-file adapter for the archive A/B developer review UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.developer_tools.archive_ab_review_queue import (
    AppendOnlyReviewStore,
    ReviewRecord,
    make_review_record,
    make_reveal_record,
    reveal_review_payload,
    review_summary as calculate_review_summary,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_AB_OUTPUT_ROOT = REPOSITORY_ROOT / ".tmp" / "archive-ab"
REVIEW_QUEUE_PATH = ARCHIVE_AB_OUTPUT_ROOT / "review-queue.jsonl"


def _contained_path(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("archive A/B path must stay inside the benchmark output directory")
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    safe_path = _contained_path(ARCHIVE_AB_OUTPUT_ROOT, path)
    try:
        payload = json.loads(safe_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid archive A/B result file: {safe_path.name}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise ValueError(f"result file has no run manifest: {safe_path.name}")
    return payload


def _result_files() -> list[Path]:
    root = ARCHIVE_AB_OUTPUT_ROOT.resolve()
    if not root.exists():
        return []
    paths = [path for path in root.glob("*.json") if path.is_file()]
    return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)


def _manifest_id(path: Path, payload: Mapping[str, Any]) -> str:
    return str(payload.get("manifest", {}).get("manifest_id") or path.stem)


def _public_manifest(manifest: Mapping[str, Any], manifest_id: str) -> dict[str, Any]:
    protocol = manifest.get("protocol", {})
    scenario = protocol.get("scenario", {}) if isinstance(protocol, Mapping) else {}
    return {
        "manifest_id": manifest_id,
        "schema_version": manifest.get("schema_version"),
        "wiki_package": manifest.get("wiki_package", {}),
        "wiki_sources": manifest.get("wiki_sources", []),
        "scenario": {
            "kind": scenario.get("kind"),
            "archive_mode": scenario.get("archive_mode"),
        },
    }


def _records() -> list[ReviewRecord]:
    store = AppendOnlyReviewStore(_contained_path(ARCHIVE_AB_OUTPUT_ROOT, REVIEW_QUEUE_PATH))
    return store.records()


def _latest_records(records: Iterable[ReviewRecord]) -> dict[tuple[str, str], ReviewRecord]:
    latest: dict[tuple[str, str], ReviewRecord] = {}
    for record in records:
        latest[(record.manifest_id, record.case_id)] = record
    return latest


def list_manifests() -> list[dict[str, Any]]:
    """List only result metadata; candidate text is loaded by ``load_cases``."""
    manifests: list[dict[str, Any]] = []
    for path in _result_files():
        try:
            payload = _load_json(path)
        except ValueError:
            continue
        manifest = payload["manifest"]
        cases = payload.get("review_cases", [])
        manifests.append({
            "manifest_id": _manifest_id(path, payload),
            "file_name": path.name,
            "schema_version": manifest.get("schema_version"),
            "created_at": manifest.get("created_at"),
            "case_count": len(manifest.get("cases", [])),
            "reviewable_case_count": len(cases) if isinstance(cases, list) else 0,
            "has_score": bool(payload.get("score")),
        })
    return sorted(manifests, key=lambda item: item["file_name"], reverse=True)


def _find_payload(manifest_id: str | None) -> tuple[Path, dict[str, Any]] | None:
    for path in _result_files():
        try:
            payload = _load_json(path)
        except ValueError:
            continue
        if manifest_id is None or _manifest_id(path, payload) == manifest_id:
            return path, payload
    return None


def _public_record(record: ReviewRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "review_id": record.review_id,
        "selection": record.selection,
        "error_tags": list(record.error_tags),
        "confidence": record.confidence,
        "note": record.note,
        "submitted_at": record.submitted_at,
        "revealed": record.revealed,
        "needs_recheck": record.needs_recheck,
        "supersedes_review_id": record.supersedes_review_id,
    }


def _public_outputs(blind: Mapping[str, Any]) -> list[dict[str, Any]]:
    source_ids = [str(entry.get("source_id", "")) for entry in blind.get("source_entries", [])]
    candidates = blind.get("anonymous_candidates", [])
    outputs = []
    for index, candidate in enumerate(candidates[:2]):
        values = candidate if isinstance(candidate, Mapping) else {}
        outputs.append({
            "anonymous_label": "left" if index == 0 else "right",
            "entries": [
                {"source_id": source_id, "text": str(values.get(source_id, ""))}
                for source_id in source_ids
            ],
        })
    return outputs


def _public_case(
    blind: Mapping[str, Any],
    manifest_id: str,
    record: ReviewRecord | None,
    private: Mapping[str, Any],
) -> dict[str, Any]:
    public = {
        "case_id": str(blind.get("case_id", "")),
        "manifest_id": manifest_id,
        "dataset_id": blind.get("dataset_id"),
        "case_kind": blind.get("case_kind"),
        "chain_id": blind.get("chain_id"),
        "reference_batch_id": blind.get("reference_batch_id"),
        "chunk": blind.get("chunk", {}),
        "source_entries": blind.get("source_entries", []),
        "story_facts": blind.get("gold_facts", []),
        "wiki_evidence_ids": blind.get("wiki_evidence_ids", []),
        "anonymous_outputs": _public_outputs(blind),
        "review": _public_record(record),
        "revealed": False,
    }
    if record is not None:
        revealed = reveal_review_payload(blind, record, _blind_result(private))
        public["revealed"] = True
        public["reveal"] = revealed.get("reveal", {})
        identity_by_arm = private.get("semantic_identity_by_arm", {})
        if isinstance(identity_by_arm, Mapping):
            public["reveal"]["semantic_identity"] = {
                side: {
                    "arm": arm,
                    **dict(identity_by_arm.get(arm, {})),
                }
                for side, arm in zip(("left", "right"), record.anonymous_order)
            }
    return public


def _blind_result(private: Mapping[str, Any]):
    """Create the small result shape required by ``reveal_review_payload``."""
    class Result:
        winner = str(private.get("winner", "tie"))
        evidence = tuple(str(item) for item in private.get("evidence", []))
        error_tags = tuple(str(item) for item in private.get("error_tags", []))

    return Result()


def _iter_cases(payload: Mapping[str, Any]) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    for item in payload.get("review_cases", []):
        if not isinstance(item, Mapping):
            continue
        blind = item.get("blind", item)
        private = item.get("private", {})
        if isinstance(blind, Mapping) and isinstance(private, Mapping):
            yield blind, private


def review_summary(*, manifest_id: str | None = None) -> dict[str, Any]:
    """Expose case-unique human coverage and agreement without arm internals."""
    selected = _find_payload(manifest_id)
    if selected is None:
        return calculate_review_summary([], {})
    path, payload = selected
    resolved_manifest_id = _manifest_id(path, payload)
    result_by_id = {}
    for blind, private in _iter_cases(payload):
        result_by_id[str(blind.get("case_id", ""))] = _blind_result(private)
    records = [record for record in _records() if record.manifest_id == resolved_manifest_id]
    return calculate_review_summary(records, result_by_id)


def load_cases(
    *,
    manifest_id: str | None = None,
    dataset_id: str | None = None,
    case_kind: str | None = None,
    chain_id: str | None = None,
    reference_batch_id: str | None = None,
    status: str = "all",
) -> dict[str, Any]:
    selected = _find_payload(manifest_id)
    if selected is None:
        return {
            "manifests": list_manifests(), "cases": [], "total_count": 0, "reviewed_count": 0,
            "review_summary": calculate_review_summary([], {}),
        }
    path, payload = selected
    resolved_manifest_id = _manifest_id(path, payload)
    latest = _latest_records(_records())
    cases: list[dict[str, Any]] = []
    for blind, private in _iter_cases(payload):
        if dataset_id and blind.get("dataset_id") != dataset_id:
            continue
        if case_kind and blind.get("case_kind") != case_kind:
            continue
        if chain_id and blind.get("chain_id") != chain_id:
            continue
        if reference_batch_id and blind.get("reference_batch_id") != reference_batch_id:
            continue
        record = latest.get((resolved_manifest_id, str(blind.get("case_id", ""))))
        if status == "reviewed" and record is None:
            continue
        if status == "unreviewed" and record is not None:
            continue
        cases.append(_public_case(blind, resolved_manifest_id, record, private))
    reviewed_count = sum(
        1 for blind, _private in _iter_cases(payload)
        if (resolved_manifest_id, str(blind.get("case_id", ""))) in latest
    )
    return {
        "manifests": list_manifests(),
        "selected_manifest_id": resolved_manifest_id,
        "manifest": _public_manifest(payload.get("manifest", {}), resolved_manifest_id),
        "cases": cases,
        "total_count": len(cases),
        "reviewed_count": reviewed_count,
        "review_summary": review_summary(manifest_id=resolved_manifest_id),
    }


def submit_review(
    *,
    manifest_id: str,
    case_id: str,
    selection: str,
    error_tags: Iterable[str],
    confidence: float,
    note: str,
    reviewer: str,
) -> dict[str, Any]:
    selected = _find_payload(manifest_id)
    if selected is None:
        raise ValueError("benchmark result manifest was not found")
    path, payload = selected
    resolved_manifest_id = _manifest_id(path, payload)
    target = next(
        ((blind, private) for blind, private in _iter_cases(payload) if blind.get("case_id") == case_id),
        None,
    )
    if target is None:
        raise ValueError(f"review case was not found: {case_id}")
    blind, private = target
    order = private.get("presentation_order", [])
    if not isinstance(order, list) or len(order) != 2:
        raise ValueError("review case has no valid anonymous order")
    record = make_review_record(
        blind,
        reviewer=reviewer,
        selection=selection,
        anonymous_order=order,
        error_tags=error_tags,
        confidence=confidence,
        note=note.strip(),
    )
    store = AppendOnlyReviewStore(_contained_path(ARCHIVE_AB_OUTPUT_ROOT, REVIEW_QUEUE_PATH))
    store.append(record)
    revealed_record = make_reveal_record(record)
    store.append(revealed_record)
    return _public_case(blind, resolved_manifest_id, revealed_record, private)


def review_history(*, manifest_id: str | None = None, case_id: str | None = None) -> list[dict[str, Any]]:
    records = _records()
    return [
        _public_record(record) | {"manifest_id": record.manifest_id, "case_id": record.case_id}
        for record in records
        if (manifest_id is None or record.manifest_id == manifest_id)
        and (case_id is None or record.case_id == case_id)
    ]


__all__ = [
    "ARCHIVE_AB_OUTPUT_ROOT", "REVIEW_QUEUE_PATH", "list_manifests", "load_cases",
    "review_history", "review_summary", "submit_review",
]
