"""Finalize Agent Workshop batch results after model validation."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from scripts.utils.validation_logger import ValidationLogger


def _matching_issue(issues: List[Dict[str, Any]], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    issue_id = result.get("issue_id")
    if issue_id:
        return next((issue for issue in issues if issue.get("issue_id") == issue_id), None)
    matches = [
        issue for issue in issues
        if issue.get("file_name") == result.get("file_name")
        and issue.get("key") == result.get("key")
    ]
    return matches[0] if len(matches) == 1 else None


def _mark_review(
    project: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    ValidationLogger.mark_attempt_result(
        project["source_path"],
        result.get("file_name", ""),
        result.get("key", ""),
        status="review",
        issue_id=result.get("issue_id"),
        disposition=result.get("disposition") or "human_review",
        last_suggested_fix=result.get("suggested_fix", ""),
    )


def finalize_batch_result(
    project: Dict[str, Any],
    game_id: str,
    issues: List[Dict[str, Any]],
    result: Dict[str, Any],
    *,
    apply_fix: Callable[..., tuple[bool, str, str]],
    reflection_builder: Callable[..., str],
    target_lang_resolver: Callable[..., Optional[str]],
    report_writer: Callable[..., Optional[str]],
) -> Dict[str, Any]:
    """Write only SUCCESS results; preserve REVIEW results as active findings."""
    if result.get("status") != "SUCCESS":
        if result.get("status") == "REVIEW":
            _mark_review(project, result)
        result["report_path"] = None
        return result

    original = _matching_issue(issues, result)
    if original is None:
        result.update({
            "status": "REVIEW",
            "disposition": "stale_issue",
            "classification": "human_review",
            "parity_message": "Validation issue is no longer current; no file write was attempted.",
            "report_path": None,
        })
        return result
    source = original.get("source_str", "") if original else ""
    target = original.get("target_str", "") if original else ""
    error_type = original.get("error_type", "") if original else ""
    details = original.get("details", "") if original else ""
    reflection = reflection_builder(
        error_type,
        details,
        source,
        target,
        result.get("suggested_fix", ""),
        original.get("source_context_status", "found") if original else "found",
        original.get("source_context_origin", "source_file") if original else "source_file",
        original.get("source_context_warning") if original else None,
    )
    target_lang = target_lang_resolver(
        result.get("file_name"),
        original.get("target_lang") if original else None,
    )
    applied, failure_reason, message = apply_fix(
        project=project,
        game_id=game_id,
        file_name=result["file_name"],
        file_path=original.get("file_path") if original else None,
        key=result["key"],
        source_str=source,
        suggested_fix=result.get("suggested_fix", ""),
        target_lang=target_lang,
    )
    if applied:
        ValidationLogger.mark_attempt_result(
            project["source_path"],
            result["file_name"],
            result["key"],
            status="fixed",
            issue_id=result.get("issue_id"),
            last_suggested_fix=result.get("suggested_fix", ""),
        )
        result["report_path"] = report_writer(
            project["source_path"],
            result["file_name"],
            result["key"],
            source,
            target,
            error_type,
            details,
            result.get("suggested_fix", ""),
            reflection,
            original.get("source_context_status", "found") if original else "found",
            original.get("source_context_origin", "source_file") if original else "source_file",
            original.get("source_context_warning") if original else None,
        )
        result["parity_message"] = message
        return result

    ValidationLogger.mark_attempt_result(
        project["source_path"],
        result["file_name"],
        result["key"],
        status="failed",
        issue_id=result.get("issue_id"),
        failure_reason=failure_reason,
        failure_details=message,
        last_suggested_fix=result.get("suggested_fix", ""),
    )
    result.update({"status": "FAILED", "parity_message": message, "report_path": None})
    return result


__all__ = ["finalize_batch_result"]
