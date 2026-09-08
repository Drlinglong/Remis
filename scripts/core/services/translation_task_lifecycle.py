"""Persisted lifecycle and exclusive project ownership for translation tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from scripts.core.repositories.task_repository import (
    TRANSLATION_LOCK_ACTIVE_STATUSES,
    TRANSLATION_LOCK_TASK_KINDS,
    TaskRepository,
)


TRANSLATION_TASK_KINDS = set(TRANSLATION_LOCK_TASK_KINDS)
ACTIVE_STATUSES = set(TRANSLATION_LOCK_ACTIVE_STATUSES)
TERMINAL_STATUSES = {
    "completed",
    "complete",
    "success",
    "failed",
    "partial_failed",
    "cancelled",
    "canceled",
    "interrupted",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TranslationTaskLifecycle:
    """Own translation transitions and the durable project lock contract."""

    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def acquire_project_lock(self, *, task_id: str, project_id: str) -> bool:
        return self.repository.acquire_project_lock(
            task_id=task_id,
            project_id=project_id,
        )

    def get_project_lock(self, project_id: str) -> dict[str, Any] | None:
        return self.repository.get_project_lock(project_id)

    def transition(
        self,
        task_id: str,
        status: str,
        *,
        message: str | None = None,
        event_type: str = "status_changed",
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} does not exist")
        current = str(task.get("status") or "").lower()
        requested = str(status or "").lower()
        if current in TERMINAL_STATUSES and requested != current:
            raise ValueError(
                f"Task {task_id} is terminal ({current}) and cannot transition to {requested}"
            )
        if requested not in ACTIVE_STATUSES | TERMINAL_STATUSES:
            raise ValueError(f"Unsupported translation task status: {requested}")

        now = _utc_now_iso()
        task["status"] = requested
        task["updated_at"] = now
        if message is not None:
            task["message"] = message
        if requested not in {"pending", "queued"} and not task.get("started_at"):
            task["started_at"] = now
        if requested in TERMINAL_STATUSES:
            if not task.get("finished_at"):
                task["finished_at"] = now
            task["blocking"] = False
        task.setdefault("progress", {})["stage"] = requested.replace("_", " ").title()
        self.repository.save_task(
            task,
            event={
                "timestamp": now,
                "level": "warning" if requested in {"interrupted", "cancelled"} else "info",
                "event_type": event_type,
                "audience": "user",
                "message": message or f"Translation task status changed to {requested}.",
            },
        )
        return self.repository.get_task(task_id) or task

    def request_cancellation(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} does not exist")
        if str(task.get("status") or "").lower() in TERMINAL_STATUSES:
            return task
        task["cancellation_requested_at"] = _utc_now_iso()
        self.repository.save_task(task)
        return self.transition(
            task_id,
            "cancelling",
            message="Cancellation requested. Waiting for the active provider request to stop safely.",
            event_type="cancellation_requested",
        )

    def recover_orphaned_tasks(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        active = self.repository.list_tasks(
            statuses=ACTIVE_STATUSES,
            include_events=False,
        )
        for task in active:
            if str(task.get("kind") or "") not in TRANSLATION_TASK_KINDS:
                continue
            task_id = str(task["task_id"])
            recovered.append(
                self.transition(
                    task_id,
                    "interrupted",
                    message=(
                        "The previous translation worker is no longer running. "
                        "Recovery actions are available only when its task-owned checkpoint is compatible."
                    ),
                    event_type="recovery_interrupted",
                )
            )
        return recovered
