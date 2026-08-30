"""Read-only Task Center projection for the embedded Help Copilot."""

from __future__ import annotations

from typing import Any

from scripts.core.agent_service import agent_registry
from scripts.core.services.agent_validation_policy import (
    classify_issues,
    job_allowed_actions,
    persisted_task_validation_issues,
)
from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.schemas.agent import AgentValidationSummary
from scripts.shared import task_state
from scripts.shared.services import project_manager


def _normalized_status(raw_status: Any, *, recovered: bool = False) -> str:
    value = str(raw_status or "").lower()
    if recovered and value not in task_state.TERMINAL_TASK_STATUSES:
        return "interrupted"
    return {
        "pending": "queued",
        "starting": "queued",
        "queued": "queued",
        "running": "running",
        "processing": "running",
        "in_progress": "running",
        "awaiting_approval": "awaiting_approval",
        "waiting_approval": "awaiting_approval",
        "completed": "completed",
        "complete": "completed",
        "success": "completed",
        "partial_failed": "partial_failed",
        "failed": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "interrupted": "interrupted",
    }.get(value, "unknown")


def _output_paths(task: dict[str, Any]) -> list[str]:
    paths = [str(path) for path in task.get("output_dirs") or [] if path]
    for path in (task.get("result") or {}).get("output_paths") or []:
        if path and str(path) not in paths:
            paths.append(str(path))
    result_path = task.get("result_path")
    if result_path and str(result_path) not in paths:
        paths.append(str(result_path))
    return paths


async def _validation_summary(project_id: str | None) -> AgentValidationSummary:
    if not project_id:
        return AgentValidationSummary()
    project = await project_manager.get_project(project_id)
    if not project:
        return AgentValidationSummary()
    status = ValidationSidecarService().load_status(project.get("source_path") or "")
    if not status:
        return AgentValidationSummary()
    files = await project_manager.get_project_files(project_id)
    issues = ValidationSidecarService.attach_project_file_ids(status.get("issues") or [], files)
    _, summary = classify_issues(issues)
    return summary


async def get_copilot_task_status(task_id: str) -> dict[str, Any]:
    """Return a bounded, authoritative task snapshot without logs or secrets."""
    identifier = str(task_id or "").strip()
    if not identifier or len(identifier) > 128:
        return {"found": False, "code": "invalid_task_id", "retryable": False}
    metadata = agent_registry.get_job(identifier)
    task = task_state.get_task(identifier)
    recovered = False
    if task is None and metadata:
        task = dict(metadata.get("last_snapshot") or {})
        recovered = True
    if not task:
        return {"found": False, "code": "task_not_found", "task_id": identifier, "retryable": False}

    project_id = task.get("project_id") or (metadata or {}).get("project_id")
    status = _normalized_status(task.get("status"), recovered=recovered)
    progress = task.get("progress") or {}
    validation = await _validation_summary(project_id)
    task_evidence = persisted_task_validation_issues(task)
    if task_evidence:
        _, evidence_summary = classify_issues(task_evidence)
        validation = AgentValidationSummary(
            errors=validation.errors + evidence_summary.errors,
            warnings=validation.warnings + evidence_summary.warnings,
            human_review_items=(
                validation.human_review_items + evidence_summary.human_review_items
            ),
            total=validation.total + evidence_summary.total,
            available=True,
            truncated=validation.truncated or evidence_summary.truncated,
        )
    paths = _output_paths(task)
    kind = str(task.get("agent_job_kind") or task.get("kind") or (metadata or {}).get("kind") or "task")
    policy_status = "failed" if status == "partial_failed" else status
    failure_summary = None
    if status in {"failed", "partial_failed", "interrupted"}:
        failure_summary = task.get("attention_reason") or task.get("message") or "Task did not complete cleanly."
    return {
        "found": True,
        "task_id": identifier,
        "project_id": project_id,
        "kind": kind,
        "status": status,
        "progress": {
            "completed_files": int(progress.get("current") or 0),
            "total_files": int(progress.get("total") or 0),
            "percent": int(progress.get("percent") or 0),
            "current_file": str(progress.get("current_file") or ""),
            "stage": str(progress.get("stage") or ""),
            "successful_batches": int(progress.get("successful_batches") or 0),
            "failed_batches": int(progress.get("failed_batches") or 0),
        },
        "validation": validation.model_dump(),
        "output_paths": paths,
        "failure_summary": failure_summary,
        "allowed_actions": job_allowed_actions(
            policy_status,
            validation,
            paths,
            kind=kind,
            agent_managed=metadata is not None,
        ),
        "recovery_source": "persisted_snapshot" if recovered else "task_center_ledger",
        "read_only": True,
    }
