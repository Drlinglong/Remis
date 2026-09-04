"""Bind model repair requests to the current persisted validation observation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from fastapi import HTTPException

from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.core.services.workshop_writeback_service import is_repairable_workshop_issue
from scripts.utils.validation_issue_identity import enrich_issue
from scripts.utils.validation_logger import ValidationLogger


HASH_FIELDS = ("source_hash", "target_hash")


def _same_path(left: Any, right: Any) -> bool:
    return str(left or "").replace("\\", "/").casefold() == str(right or "").replace("\\", "/").casefold()


def _same_snapshot(candidate: Dict[str, Any], submitted: Dict[str, Any]) -> bool:
    if not _same_path(candidate.get("file_name"), submitted.get("file_name")):
        return False
    for field in ("key", "source_str", "target_str"):
        if candidate.get(field, "") != submitted.get(field, ""):
            return False
    for field in HASH_FIELDS:
        submitted_hash = submitted.get(field)
        if submitted_hash and candidate.get(field) != submitted_hash:
            return False
    submitted_error = submitted.get("error_code") or submitted.get("error_type")
    candidate_error = candidate.get("error_code") or candidate.get("error_type")
    return not submitted_error or not candidate_error or submitted_error == candidate_error


def _current_issues(project: Dict[str, Any], sidecars: ValidationSidecarService) -> List[Dict[str, Any]]:
    source_path = project.get("source_path")
    if not source_path:
        return []
    return [enrich_issue(dict(issue)) for issue in sidecars.current_translation_issues(source_path)]


def _stale_request(project: Dict[str, Any], submitted: Dict[str, Any], reason: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "stale_validation_issue",
            "message": "The validation issue is stale or no longer matches the current translation.",
            "reason": reason,
            "issue_id": submitted.get("issue_id"),
            "file_name": submitted.get("file_name"),
            "key": submitted.get("key"),
        },
    )


def _mark_stale_if_known(project: Dict[str, Any], issue: Dict[str, Any], reason: str) -> None:
    issue_id = issue.get("issue_id")
    if not issue_id or not project.get("source_path"):
        return
    ValidationLogger.mark_attempt_result(
        project["source_path"],
        str(issue.get("file_name") or ""),
        str(issue.get("key") or ""),
        status="review",
        issue_id=str(issue_id),
        disposition="stale_issue",
        failure_reason="stale_validation_issue",
        failure_details=reason,
    )


def bind_repair_issues(
    project: Dict[str, Any],
    submitted_issues: Iterable[Dict[str, Any]],
    *,
    sidecars: ValidationSidecarService | None = None,
) -> List[Dict[str, Any]]:
    """Return canonical current issues or reject stale/ambiguous requests."""
    sidecars = sidecars or ValidationSidecarService()
    current = _current_issues(project, sidecars)
    bound: List[Dict[str, Any]] = []
    for submitted in submitted_issues:
        submitted = dict(submitted)
        issue_id = submitted.get("issue_id")
        if issue_id:
            matches = [issue for issue in current if issue.get("issue_id") == issue_id]
            if len(matches) != 1:
                raise _stale_request(project, submitted, "issue_id_not_current")
            candidate = matches[0]
            project_id = str(project.get("project_id") or "")
            candidate_project_id = str(candidate.get("project_id") or "")
            if project_id and candidate_project_id and project_id != candidate_project_id:
                raise _stale_request(project, submitted, "issue_project_mismatch")
            if not _same_snapshot(candidate, submitted):
                ValidationLogger.ensure_issue_identity(project.get("source_path", ""), candidate)
                _mark_stale_if_known(project, candidate, "submitted_snapshot_changed")
                raise _stale_request(project, submitted, "submitted_snapshot_changed")
        else:
            matches = [issue for issue in current if _same_snapshot(issue, submitted)]
            if len(matches) != 1:
                reason = "issue_snapshot_not_current" if not matches else "ambiguous_issue_snapshot"
                raise _stale_request(project, submitted, reason)
            candidate = matches[0]

        project_id = str(project.get("project_id") or "")
        candidate_project_id = str(candidate.get("project_id") or "")
        if project_id and candidate_project_id and project_id != candidate_project_id:
            raise _stale_request(project, submitted, "issue_project_mismatch")

        ValidationLogger.ensure_issue_identity(project.get("source_path", ""), candidate)

        if not is_repairable_workshop_issue(candidate):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "unsupported_repair_issue",
                    "message": "This validation issue is review-only and cannot be sent to a model.",
                    "issues": [{
                        "file_name": candidate.get("file_name"),
                        "key": candidate.get("key"),
                        "error_code": candidate.get("error_code"),
                        "issue_id": candidate.get("issue_id"),
                    }],
                },
            )
        bound.append(candidate)
    return bound


__all__ = ["bind_repair_issues"]
