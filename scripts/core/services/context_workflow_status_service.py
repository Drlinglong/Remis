"""Thread-safe status and task projection for context analysis workflows."""

from __future__ import annotations

import threading
from typing import Any

from scripts.core.neologism_extraction import AnalysisScope
from scripts.shared import task_state


class ContextWorkflowStatusService:
    """Own per-project reservations, status snapshots, and task updates."""

    ACTIVE_STATUSES = {"queued", "starting", "running"}

    def __init__(self, task_backend: Any = task_state):
        self.task_backend = task_backend
        self._status_lock = threading.RLock()
        self._statuses: dict[str, dict[str, Any]] = {}

    def reserve(self, project_id: str, task_id: str, scope: AnalysisScope) -> bool:
        """Atomically reserve one context-analysis run for a project."""
        normalized = AnalysisScope(scope)
        with self._status_lock:
            current = self._statuses.get(project_id)
            if current and current.get("status") in self.ACTIVE_STATUSES:
                return False
            self._statuses[project_id] = {
                **self._idle_status(),
                "status": "queued",
                "task_id": task_id,
                "analysis_scope": normalized.value,
            }
        return True

    def release_reservation(self, project_id: str, task_id: str) -> None:
        """Release a queued reservation when task creation fails."""
        with self._status_lock:
            current = self._statuses.get(project_id)
            if (
                current
                and current.get("task_id") == task_id
                and current.get("status") == "queued"
            ):
                self._statuses[project_id] = self._idle_status()

    def get_status(self, project_id: str) -> dict[str, Any]:
        with self._status_lock:
            status = self._statuses.get(project_id)
            if status is not None:
                return dict(status)
        return self._idle_status()

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "status": "idle",
            "processed_files": 0,
            "total_files": 0,
            "new_terms": 0,
            "duplicate_terms": 0,
            "current_file": None,
            "error": None,
            "task_id": None,
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "source_snapshot_hash": None,
            "context_release_id": None,
        }

    def mark_running(
        self,
        project_id: str,
        task_id: str | None,
        scope: AnalysisScope,
        total_files: int,
        source_snapshot_hash: str,
        affected_source_items: list[dict[str, str]],
    ) -> None:
        self._set_status(
            project_id,
            status="running",
            task_id=task_id,
            processed_files=0,
            total_files=total_files,
            analysis_scope=scope.value,
            source_snapshot_hash=source_snapshot_hash,
            affected_source_items=affected_source_items,
        )
        self.update_task(
            task_id,
            status="running",
            message="Context analysis started.",
            fields={"stage_code": "extracting", "workflow_context": {"analysis_scope": scope.value}},
        )

    def mark_completed(
        self,
        project_id: str,
        task_id: str | None,
        result: dict[str, Any],
        total_files: int,
    ) -> None:
        self._set_status(
            project_id,
            status="completed",
            processed_files=total_files,
            total_files=total_files,
            current_file=None,
            error=None,
            **result,
        )
        self.update_task(
            task_id,
            status="completed",
            message="Context analysis completed.",
            progress={"current": total_files, "total": total_files, "percent": 100, "stage": "Completed"},
            summary=result,
            fields={"stage_code": "completed"},
        )

    def mark_failed(
        self,
        project_id: str,
        task_id: str | None,
        total_files: int,
        processed_files: int,
        error: Exception,
    ) -> None:
        message = str(error) or error.__class__.__name__
        self._set_status(
            project_id,
            status="failed",
            total_files=total_files,
            processed_files=processed_files,
            error=message,
        )
        self.update_task(
            task_id,
            status="failed",
            message=message,
            fields={
                "stage_code": "failed",
                "attention_reason": message,
                "attention_reason_code": "context_analysis_failed",
            },
        )

    def update_task(self, task_id: str | None, **updates: Any) -> None:
        if task_id:
            push = updates.pop("push", True)
            self.task_backend.update_task(task_id, push=push, **updates)

    def set_status(self, project_id: str, **updates: Any) -> None:
        self._set_status(project_id, **updates)

    def _set_status(self, project_id: str, **updates: Any) -> None:
        with self._status_lock:
            current = self._statuses.get(project_id)
            if current is None:
                current = self._idle_status()
                self._statuses[project_id] = current
            current.update(updates)
