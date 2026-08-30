"""Classify Agent API validation items and select model-repairable scope."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scripts.core.services.workshop_writeback_service import (
    is_repairable_workshop_issue,
)
from scripts.schemas.agent import AgentValidationSummary


def classify_issues(
    issues: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], AgentValidationSummary]:
    """Build the public validation view without presenting manual work as repairable."""
    public_items = []
    counts = {"error": 0, "warning": 0, "human_review": 0}
    for raw in issues:
        category = _issue_category(raw)
        counts[category] += 1
        public_items.append(
            {
                "category": category,
                "code": str(
                    raw.get("error_code")
                    or raw.get("error_type")
                    or "unknown"
                ),
                "file_id": raw.get("file_id"),
                "file_name": raw.get("file_name"),
                "key": raw.get("key"),
                "line_number": raw.get("line_number"),
                "details": raw.get("details") or raw.get("message"),
                "status": raw.get("status", "detected"),
            }
        )
    summary = AgentValidationSummary(
        errors=counts["error"],
        warnings=counts["warning"],
        human_review_items=counts["human_review"],
        total=len(public_items),
        available=True,
    )
    return public_items, summary


def _issue_category(issue: dict[str, Any]) -> str:
    if issue.get("requires_human_review") is True:
        return "human_review"
    if not is_repairable_workshop_issue(issue):
        return "human_review"
    severity = str(issue.get("severity") or "").strip().lower()
    if severity in {"critical", "error", "fatal"}:
        return "error"
    if severity in {"warning", "warn", "info"}:
        return "warning"
    return "human_review"


def repairable_issues(
    issues: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only issues the Workshop writeback policy permits models to repair."""
    return [
        issue
        for issue in issues
        if is_repairable_workshop_issue(issue)
    ]


def validation_allowed_actions(
    issues: Iterable[dict[str, Any]],
    *,
    total: int,
) -> list[str]:
    """Expose repair only when at least one active item can reach the model."""
    if any(is_repairable_workshop_issue(issue) for issue in issues):
        return ["repair"]
    if total == 0:
        return ["approve_export"]
    return []


def job_allowed_actions(
    status: str,
    validation: AgentValidationSummary,
    output_paths: list[str],
    *,
    kind: str,
    agent_managed: bool = True,
) -> list[str]:
    """Expose only actions backed by an Agent registry record."""
    actions = ["poll"] if status in {"queued", "running"} else []
    if agent_managed and status in {"failed", "partial_failed", "interrupted"}:
        actions.append("retry")
    if status == "completed":
        if validation.available:
            actions.append("inspect_validation")
        if agent_managed and validation.errors:
            actions.append("repair")
        if agent_managed and kind == "dry_run":
            actions.append("create_translation_plan")
        elif (
            agent_managed
            and kind in {"translation", "initial_translation", "incremental_translation"}
            and output_paths
            and validation.errors == validation.human_review_items == 0
        ):
            actions.append("approve_export")
    return actions
