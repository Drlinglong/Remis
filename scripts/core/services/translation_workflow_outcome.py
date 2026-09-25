import asyncio
import logging
from typing import List, Optional

from scripts.core.services.translation_task_runtime import (
    finalize_translation_task,
    resolve_task_output_directories,
)
from scripts.core.feature_policy import checkpoint_resume_enabled
from scripts.shared import task_state


def workflow_outcome_values(outcome: object) -> tuple[str, str, int]:
    status = getattr(outcome, "status", None)
    if status not in {"completed", "partial_failed"}:
        return "completed", "Translation workflow completed successfully.", 0
    message = (
        getattr(outcome, "message", None)
        or "Translation workflow completed successfully."
    )
    return status, message, int(getattr(outcome, "issue_count", 0) or 0)


def history_completion_description(status: str) -> str:
    if status == "partial_failed":
        return "Translation completed with source-file warnings"
    return "Translation completed successfully"


def record_context_metadata(task_id: str, workflow_result: object) -> None:
    context_metadata = (
        workflow_result.get("context")
        if isinstance(workflow_result, dict)
        else getattr(workflow_result, "context_metadata", None)
    )
    if not context_metadata:
        return
    warning = context_metadata.get("warning") or {}
    task_state.update_task(
        task_id,
        fields={
            "context": context_metadata,
            "result": {"metadata": {"context": context_metadata}},
        },
        append_log=(
            f"Project context warning: {warning.get('code')}."
            if warning.get("code")
            else None
        ),
        push=False,
    )


def finalize_successful_v2_translation(
    task_id: str,
    mod_name: str,
    project_id: Optional[str],
    target_languages: List[dict],
    recovery_identity: Optional[dict],
    game_profile: dict,
    outcome: object,
    project_manager_client,
    run_async=asyncio.run,
) -> None:
    record_context_metadata(task_id, outcome)
    logging.info("Returned from initial_translate.run")
    task_state.update_task(
        task_id,
        fields={
            "output_dirs": resolve_task_output_directories(
                mod_name,
                target_languages,
                project_id,
                recovery_identity,
                game_profile,
            ),
            "reference_metrics": list(getattr(outcome, "reference_metrics", ())),
            "checkpoint": {
                "available": False,
                "resume_supported": checkpoint_resume_enabled(),
                "stage": "Completed",
                "updated_at": task_state.utc_now_iso(),
            },
        },
        push=False,
    )
    status, message, issue_count = workflow_outcome_values(outcome)
    finalize_translation_task(task_id, status, message, "Completed", issue_count)
    if project_id:
        try:
            run_async(project_manager_client.log_history_event(
                project_id=project_id,
                action_type="translation_workflow",
                description=history_completion_description(status),
            ))
        except Exception as exc:
            logging.error(f"Failed to log completion activity (v2): {exc}")
