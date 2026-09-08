"""Stable identity and queue policy for persisted validation issues.

Validation scans are repeatable observations, not new issues every time they
run.  This module keeps the identity of an issue independent from the current
target text so a repair attempt can be reconciled on the next scan while still
re-opening the issue when the target observation changes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional


TERMINAL_STATUSES = {"fixed", "ignored", "accepted_reasonable"}
HIDDEN_STATUSES = {"fixed", "ignored"}
INVALID_KEY_CODES = {"validation_invalid_key_format"}


def sha256_text(value: Any) -> str:
    """Hash text without exposing it in logs or replacing it with a token."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _classification(issue: Dict[str, Any]) -> str:
    params = issue.get("details_params")
    params = params if isinstance(params, dict) else {}
    explicit = params.get("classification") or issue.get("classification")
    if explicit:
        return str(explicit)
    if issue.get("requires_human_review") is True:
        return "human_review"
    if issue.get("error_code") in INVALID_KEY_CODES or issue.get("error_type") in INVALID_KEY_CODES:
        return "invalid_key"
    return "validation_failure"


def _queue_flags(issue: Dict[str, Any], classification: str) -> tuple[bool, bool, bool]:
    params = issue.get("details_params")
    params = params if isinstance(params, dict) else {}
    manual = classification in {"source_defect", "possible_reasonable_variation", "human_review", "invalid_key"}
    repair_queue = params.get("repairQueue")
    review_queue = params.get("reviewQueue")
    if repair_queue is None:
        repair_queue = not manual and not issue.get("requires_human_review", False)
    if review_queue is None:
        review_queue = manual or classification == "validation_failure" and str(issue.get("severity", "")).lower() == "warning"
    repairable = bool(repair_queue) and classification not in {"source_defect", "possible_reasonable_variation", "human_review", "invalid_key"}
    return bool(repairable), bool(repair_queue), bool(review_queue)


def _stable_identity_payload(issue: Dict[str, Any], occurrence: int) -> Dict[str, Any]:
    return {
        "project_id": str(issue.get("project_id") or ""),
        "target_lang": str(issue.get("target_lang") or ""),
        "file_name": str(issue.get("file_name") or "").replace("\\", "/").casefold(),
        "source_file": str(issue.get("source_file") or "").replace("\\", "/").casefold(),
        "key": str(issue.get("key") or ""),
        "error_code": str(issue.get("error_code") or issue.get("error_type") or ""),
        "details_code": str(issue.get("details_code") or ""),
        "source_hash": issue["source_hash"],
        "line_number": int(issue.get("line_number") or 0),
        "occurrence": occurrence,
    }


def enrich_issue(issue: Dict[str, Any], occurrence: int = 0) -> Dict[str, Any]:
    """Add persistence and queue metadata while preserving existing fields."""
    enriched = dict(issue)
    enriched["source_hash"] = enriched.get("source_hash") or sha256_text(enriched.get("source_str", ""))
    enriched["target_hash"] = enriched.get("target_hash") or sha256_text(enriched.get("target_str", ""))
    classification = _classification(enriched)
    repairable, repair_queue, review_queue = _queue_flags(enriched, classification)
    enriched["classification"] = classification
    enriched["repairable"] = repairable
    enriched["repair_queue"] = repair_queue
    enriched["review_queue"] = review_queue
    status = str(enriched.get("status") or "detected").lower()
    enriched["status"] = status
    if status in TERMINAL_STATUSES:
        disposition = status
    elif classification == "source_defect":
        disposition = "source_issue"
    elif classification == "possible_reasonable_variation":
        disposition = "human_review"
    elif classification in {"human_review", "invalid_key"}:
        disposition = "human_review"
    else:
        disposition = enriched.get("disposition") or "detected"
    enriched["disposition"] = str(disposition)
    enriched["attempts"] = int(enriched.get("attempts") or 0)
    observation = {
        "source_hash": enriched["source_hash"],
        "target_hash": enriched["target_hash"],
        "error_code": enriched.get("error_code") or enriched.get("error_type") or "",
        "details_code": enriched.get("details_code") or "",
        "classification": classification,
    }
    enriched["observation_fingerprint"] = enriched.get("observation_fingerprint") or hashlib.sha256(
        _canonical_json(observation).encode("utf-8")
    ).hexdigest()
    enriched["issue_id"] = enriched.get("issue_id") or hashlib.sha256(
        _canonical_json(_stable_identity_payload(enriched, occurrence)).encode("utf-8")
    ).hexdigest()
    return enriched


def enrich_issues(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich a scan while disambiguating repeated same-key findings."""
    occurrences: Dict[str, int] = {}
    enriched: List[Dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        base = (
            str(issue.get("project_id") or ""),
            str(issue.get("target_lang") or ""),
            str(issue.get("file_name") or "").replace("\\", "/").casefold(),
            str(issue.get("key") or ""),
            str(issue.get("error_code") or issue.get("error_type") or ""),
        )
        occurrence = occurrences.get("\x1f".join(base), 0)
        occurrences["\x1f".join(base)] = occurrence + 1
        enriched.append(enrich_issue(issue, occurrence))
    return enriched


def reconcile_issues(
    current: Iterable[Dict[str, Any]],
    previous: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Carry attempts/assessment across a rescan, reopening changed targets."""
    previous_by_id = {
        item.get("issue_id"): item
        for item in enrich_issues(previous)
        if item.get("issue_id")
    }
    reconciled: List[Dict[str, Any]] = []
    for item in enrich_issues(current):
        old = previous_by_id.get(item.get("issue_id"))
        if not old:
            reconciled.append(item)
            continue
        if old.get("observation_fingerprint") == item.get("observation_fingerprint"):
            for field in ("status", "disposition", "assessment", "attempts", "failure_reason", "failure_details", "last_suggested_fix", "last_attempt_at"):
                if field in old:
                    item[field] = old[field]
        else:
            item["status"] = "detected"
            item["disposition"] = "detected"
            item.pop("assessment", None)
            item["failure_reason"] = None
            item["failure_details"] = None
            item["last_suggested_fix"] = None
            item["last_attempt_at"] = None
        reconciled.append(item)
    return reconciled


def issue_is_active(issue: Dict[str, Any]) -> bool:
    # Reasonable-variation findings are terminal for repair, but remain visible
    # in the review queue until a human dismisses them.
    return str(issue.get("status", "detected")).lower() not in HIDDEN_STATUSES


def issue_is_repairable(issue: Dict[str, Any]) -> bool:
    return issue_is_active(issue) and bool(issue.get("repair_queue", issue.get("repairable", True)))


__all__ = [
    "TERMINAL_STATUSES",
    "enrich_issue",
    "enrich_issues",
    "issue_is_active",
    "issue_is_repairable",
    "reconcile_issues",
    "sha256_text",
]
