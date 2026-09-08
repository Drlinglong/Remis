"""Persist an initial-translation task and claim its project write lock."""

from __future__ import annotations

from typing import Any

from scripts.core.services.translation_task_lifecycle import TranslationTaskLifecycle
from scripts.shared import task_state


class ProjectTranslationLockError(RuntimeError):
    def __init__(self, existing_task_id: str | None):
        self.existing_task_id = existing_task_id
        super().__init__("Another translation task owns the project lock")


def claim_project_translation_lock(*, task_id: str, project_id: str) -> None:
    repository = task_state.get_repository()
    if repository is None:
        return
    lifecycle = TranslationTaskLifecycle(repository)
    if lifecycle.acquire_project_lock(task_id=task_id, project_id=project_id):
        return
    owner = lifecycle.get_project_lock(project_id) or {}
    lifecycle.transition(
        task_id,
        "failed",
        message="Another translation task acquired the project lock first.",
    )
    raise ProjectTranslationLockError(owner.get("task_id"))


def archive_recovered_task(*, previous_task_id: str | None, replacement_task_id: str) -> None:
    """Hide the superseded terminal task after its replacement owns the lock."""
    if not previous_task_id:
        return
    if task_state.get_task(previous_task_id) is None:
        return
    task_state.update_task(
        previous_task_id,
        fields={"archived_at": task_state.utc_now_iso()},
        append_log=f"Archived after recovery task {replacement_task_id} started.",
    )


def create_initial_translation_task(
    *,
    task_id: str,
    project: dict[str, Any],
    request: Any,
    context_resolution: Any,
    provider_fields: dict[str, Any],
    recovery: dict[str, Any],
    resume_supported: bool,
) -> None:
    """Create the durable run record, then atomically claim project ownership."""
    workflow_context = {}
    if context_resolution.warning:
        workflow_context["context_resolution"] = context_resolution.warning
    if request.resume_from_task_id:
        workflow_context["resume_from_task_id"] = request.resume_from_task_id
    task_state.create_task(
        task_id,
        status="pending",
        log_message=context_resolution.user_message,
        fields={
            "kind": "initial_translation",
            "project_id": request.project_id,
            "project_context": {
                "name": project["name"],
                "game_id": project.get("game_id"),
            },
            "title": (
                f"Resume translation for {project['name']}"
                if request.resume_from_task_id
                else f"Translate {project['name']}"
            ),
            "source_route": "/translation",
            "created_by": {"type": "user"},
            "blocking": True,
            "idempotency_key": request.idempotency_key,
            "recovery": recovery,
            "checkpoint": {
                "available": False,
                "resume_supported": resume_supported,
                "stage": "Queued",
                "metadata": {
                    "resume_requested": bool(request.resume_from_task_id),
                    "run_id": recovery["run_id"],
                },
            },
            "translation_context_mode": request.translation_context_mode,
            **({"workflow_context": workflow_context} if workflow_context else {}),
            **provider_fields,
        },
        dedupe_key=f"project_translation_write:{request.project_id}",
        reject_duplicate=True,
    )
    claim_project_translation_lock(
        task_id=task_id,
        project_id=request.project_id,
    )
    archive_recovered_task(
        previous_task_id=request.resume_from_task_id,
        replacement_task_id=task_id,
    )
