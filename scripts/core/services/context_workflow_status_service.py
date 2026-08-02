"""Thread-safe status and task projection for context analysis workflows."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping

from scripts.core.neologism_extraction import AnalysisScope
from scripts.core.services.context_workflow_checkpoint import (
    ContextWorkflowCheckpointPort,
    TaskStateCheckpointPort,
)
from scripts.shared import task_state


class ContextWorkflowStatusService:
    """Own reservations and project a truthful, batch-aware workflow state."""

    ACTIVE_STATUSES = {"queued", "starting", "running"}
    STAGES = {"extracting", "reviewing", "synthesizing", "publishing", "completed", "failed"}
    STAGE_LABELS = {
        "extracting": "Extracting",
        "reviewing": "Reviewing",
        "synthesizing": "Synthesizing",
        "publishing": "Publishing",
        "completed": "Completed",
        "failed": "Failed",
    }

    def __init__(
        self,
        task_backend: Any = task_state,
        *,
        checkpoint_port: ContextWorkflowCheckpointPort | None = None,
    ):
        self.task_backend = task_backend
        self.checkpoint_port = checkpoint_port or TaskStateCheckpointPort(task_backend)
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
            if current and current.get("task_id") == task_id and current.get("status") == "queued":
                self._statuses[project_id] = self._idle_status()

    def get_status(self, project_id: str) -> dict[str, Any]:
        with self._status_lock:
            status = self._statuses.get(project_id)
            if status is not None:
                return _copy(status)
        return self._idle_status()

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "status": "idle",
            "stage": None,
            "processed_files": 0,
            "total_files": 0,
            "source_items": 0,
            "current_batch": 0,
            "total_batches": 0,
            "successful_batches": 0,
            "failed_batches": 0,
            "conflict_review_count": 0,
            "new_terms": 0,
            "duplicate_terms": 0,
            "current_file": None,
            "error": None,
            "task_id": None,
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "scope": AnalysisScope.TERMS_ONLY.value,
            "provider": None,
            "model": None,
            "source_lang": None,
            "target_lang": None,
            "target": None,
            "description_language": None,
            "description": None,
            "source_snapshot_hash": None,
            "context_release_id": None,
            "affected_source_item_count": 0,
            "checkpoint": None,
        }

    def mark_running(
        self,
        project_id: str,
        task_id: str | None,
        scope: AnalysisScope,
        total_files: int,
        source_snapshot_hash: str,
        affected_source_items: list[dict[str, str]] | None = None,
        *,
        source_items: int = 0,
        total_batches: int = 0,
        workflow_context: Mapping[str, Any] | None = None,
    ) -> None:
        normalized_scope = AnalysisScope(scope).value
        context = dict(workflow_context or {})
        checkpoint = self._new_checkpoint(
            normalized_scope,
            source_snapshot_hash,
            source_items,
            total_batches,
            context,
        )
        status_updates = {
            "status": "running",
            "stage": "extracting",
            "task_id": task_id,
            "processed_files": 0,
            "total_files": total_files,
            "source_items": source_items,
            "current_batch": 0,
            "total_batches": total_batches,
            "successful_batches": 0,
            "failed_batches": 0,
            "analysis_scope": normalized_scope,
            "scope": normalized_scope,
            "source_snapshot_hash": source_snapshot_hash,
            "affected_source_item_count": len(affected_source_items or []),
            "checkpoint": checkpoint,
            **self._configuration_fields(context),
        }
        self._set_status(project_id, **status_updates)
        self._save_checkpoint(task_id, checkpoint)
        self.update_task(
            task_id,
            status="running",
            message="Context analysis started.",
            progress=self._progress(checkpoint, current=0, total=total_batches),
            fields={"stage_code": "extracting", "workflow_context": context},
        )

    def begin_stage(
        self,
        project_id: str,
        task_id: str | None,
        stage: str,
        total_batches: int,
        *,
        source_item_ids: list[str] | None = None,
    ) -> None:
        self._validate_stage(stage)
        checkpoint = self._checkpoint(project_id)
        stage_record = self._stage_record(checkpoint, stage)
        stage_record.update({
            "total_batches": max(0, total_batches),
            "successful_batch_ids": [],
            "failed_batch_ids": [],
            "batches": {},
            "source_item_ids": _unique_strings(source_item_ids or []),
        })
        checkpoint["stage"] = stage
        checkpoint["cursor"] = f"{stage}:0"
        self._update_stage_projection(
            project_id,
            task_id,
            stage,
            current_batch=0,
            total_batches=max(0, total_batches),
            successful_batches=0,
            failed_batches=0,
            conflict_review_count=0,
            checkpoint=checkpoint,
        )

    def complete_stage(
        self,
        project_id: str,
        task_id: str | None,
        stage: str,
        *,
        skipped: bool = False,
    ) -> None:
        """Close a stage, including an explicitly skipped zero-work review."""
        self._validate_stage(stage)
        checkpoint = self._checkpoint(project_id)
        record = self._stage_record(checkpoint, stage)
        record["completed"] = True
        record["skipped"] = skipped
        checkpoint["updated_at"] = _now()
        self._set_status(
            project_id,
            conflict_review_count=int(record.get("conflict_review_count") or 0),
            checkpoint=checkpoint,
        )
        self._save_checkpoint(task_id, checkpoint)

    def record_batch(
        self,
        project_id: str,
        task_id: str | None,
        stage: str,
        batch_id: str,
        *,
        success: bool,
        source_item_ids: list[str] | None = None,
        error: str | None = None,
        conflict_review_count: int = 0,
    ) -> None:
        self._validate_stage(stage)
        checkpoint = self._checkpoint(project_id)
        record = self._stage_record(checkpoint, stage)
        batch_status = "succeeded" if success else "failed"
        batches = record.setdefault("batches", {})
        batches[batch_id] = {
            "status": batch_status,
            "source_item_ids": _unique_strings(source_item_ids or []),
            **({"error": (error or "")[:500]} if error else {}),
        }
        successful = _unique_strings(record.setdefault("successful_batch_ids", []))
        failed = _unique_strings(record.setdefault("failed_batch_ids", []))
        if success:
            successful.append(batch_id)
            failed = [item for item in failed if item != batch_id]
        else:
            failed.append(batch_id)
            successful = [item for item in successful if item != batch_id]
        record["successful_batch_ids"] = _unique_strings(successful)
        record["failed_batch_ids"] = _unique_strings(failed)
        record["conflict_review_count"] = int(record.get("conflict_review_count") or 0) + max(0, conflict_review_count)
        checkpoint["cursor"] = batch_id
        total_batches = max(
            int(record.get("total_batches") or 0),
            len(record["successful_batch_ids"]) + len(record["failed_batch_ids"]),
        )
        record["total_batches"] = total_batches
        self._update_stage_projection(
            project_id,
            task_id,
            stage,
            current_batch=len(record["successful_batch_ids"]) + len(record["failed_batch_ids"]),
            total_batches=total_batches,
            successful_batches=len(record["successful_batch_ids"]),
            failed_batches=len(record["failed_batch_ids"]),
            conflict_review_count=int(record.get("conflict_review_count") or 0),
            checkpoint=checkpoint,
        )

    def mark_completed(
        self,
        project_id: str,
        task_id: str | None,
        result: dict[str, Any],
        total_files: int,
    ) -> None:
        checkpoint = self._checkpoint(project_id)
        successful, failed = self._terminal_batch_counts(checkpoint)
        checkpoint.update({"available": False, "stage": "completed", "cursor": None})
        checkpoint.setdefault("metadata", {}).update({
            "terminal_status": "completed",
            "terminal_batch_counts": {"successful": successful, "failed": failed},
        })
        self._set_status(
            project_id,
            status="completed",
            stage="completed",
            processed_files=total_files,
            total_files=total_files,
            current_batch=successful + failed,
            successful_batches=successful,
            failed_batches=failed,
            error=None,
            checkpoint=checkpoint,
            **result,
        )
        self._save_checkpoint(task_id, checkpoint)
        self.update_task(
            task_id,
            status="completed",
            message="Context analysis completed.",
            progress=self._progress(checkpoint, current=100, total=100, percent=100, stage="Completed"),
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
        checkpoint = self._checkpoint(project_id)
        successful, failed = self._terminal_batch_counts(checkpoint)
        failed_stage = checkpoint.get("stage")
        checkpoint.update({"available": True, "resume_supported": False, "stage": "failed"})
        checkpoint.setdefault("metadata", {}).update({
            "terminal_status": "failed",
            "error": message[:500],
            "failed_stage": failed_stage,
            "terminal_batch_counts": {"successful": successful, "failed": failed},
        })
        self._set_status(
            project_id,
            status="failed",
            stage="failed",
            total_files=total_files,
            processed_files=processed_files,
            successful_batches=successful,
            failed_batches=failed,
            error=message,
            checkpoint=checkpoint,
        )
        self._save_checkpoint(task_id, checkpoint)
        self.update_task(
            task_id,
            status="failed",
            message=message,
            progress=self._progress(checkpoint, stage="Failed"),
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

    def _checkpoint(self, project_id: str) -> dict[str, Any]:
        with self._status_lock:
            status = self._statuses.setdefault(project_id, self._idle_status())
            checkpoint = status.get("checkpoint") or self._new_checkpoint(
                status.get("analysis_scope", AnalysisScope.TERMS_ONLY.value),
                status.get("source_snapshot_hash"),
                status.get("source_items", 0),
                status.get("total_batches", 0),
                self._configuration_fields(status),
            )
            checkpoint = _copy(checkpoint)
            status["checkpoint"] = checkpoint
            return checkpoint

    def _save_checkpoint(self, task_id: str | None, checkpoint: dict[str, Any]) -> None:
        if task_id:
            self.checkpoint_port.save_checkpoint(task_id, checkpoint)

    def _update_stage_projection(
        self,
        project_id: str,
        task_id: str | None,
        stage: str,
        *,
        current_batch: int,
        total_batches: int,
        successful_batches: int,
        failed_batches: int,
        conflict_review_count: int,
        checkpoint: dict[str, Any],
    ) -> None:
        checkpoint["stage"] = stage
        checkpoint["updated_at"] = _now()
        self._set_status(
            project_id,
            status="running",
            stage=stage,
            current_batch=current_batch,
            total_batches=total_batches,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            conflict_review_count=conflict_review_count,
            checkpoint=checkpoint,
        )
        self._save_checkpoint(task_id, checkpoint)
        self.update_task(
            task_id,
            progress=self._progress(checkpoint, current=current_batch, total=total_batches),
            fields={"stage_code": stage},
            push=False,
        )

    def _new_checkpoint(
        self,
        scope: str,
        source_snapshot_hash: str | None,
        source_items: int,
        total_batches: int,
        configuration: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "available": True,
            "resume_supported": False,
            "stage": "extracting",
            "cursor": "extracting:0",
            "updated_at": _now(),
            "metadata": {
                "schema": "context-workflow-checkpoint-v1",
                "analysis_scope": scope,
                "source_snapshot_hash": source_snapshot_hash,
                "source_items": source_items,
                "total_batches": total_batches,
                "configuration": dict(configuration),
                "resume_contract": "inspection_only_until_batch_adapters_are_resumable",
                "stages": {},
            },
        }

    @staticmethod
    def _stage_record(checkpoint: dict[str, Any], stage: str) -> dict[str, Any]:
        stages = checkpoint.setdefault("metadata", {}).setdefault("stages", {})
        return stages.setdefault(stage, {})

    @staticmethod
    def _current_batch(checkpoint: Mapping[str, Any]) -> int:
        stages = (checkpoint.get("metadata") or {}).get("stages") or {}
        record = stages.get(checkpoint.get("stage"), {})
        return len(record.get("successful_batch_ids") or []) + len(record.get("failed_batch_ids") or [])

    @classmethod
    def _terminal_batch_counts(cls, checkpoint: Mapping[str, Any]) -> tuple[int, int]:
        metadata = checkpoint.get("metadata") or {}
        terminal = metadata.get("terminal_batch_counts") or {}
        if terminal:
            return int(terminal.get("successful") or 0), int(terminal.get("failed") or 0)
        stages = metadata.get("stages") or {}
        for stage in ("publishing", "synthesizing", "reviewing", "extracting"):
            record = stages.get(stage) or {}
            successful = len(record.get("successful_batch_ids") or [])
            failed = len(record.get("failed_batch_ids") or [])
            if successful or failed:
                return successful, failed
        return 0, 0

    @classmethod
    def _progress(
        cls,
        checkpoint: Mapping[str, Any],
        *,
        current: int | None = None,
        total: int | None = None,
        percent: int | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        metadata = checkpoint.get("metadata") or {}
        stages = metadata.get("stages") or {}
        record = stages.get(checkpoint.get("stage"), {})
        if not record and checkpoint.get("stage") in {"completed", "failed"}:
            counts = metadata.get("terminal_batch_counts") or {}
            record = {
                "successful_batch_ids": [None] * int(counts.get("successful") or 0),
                "failed_batch_ids": [None] * int(counts.get("failed") or 0),
            }
        total_value = int(total if total is not None else record.get("total_batches") or metadata.get("total_batches") or 0)
        if current is None and checkpoint.get("stage") in {"completed", "failed"}:
            terminal = metadata.get("terminal_batch_counts") or {}
            current = int(terminal.get("successful") or 0) + int(terminal.get("failed") or 0)
        current_value = int(current if current is not None else cls._current_batch(checkpoint))
        successful = len(record.get("successful_batch_ids") or [])
        failed = len(record.get("failed_batch_ids") or [])
        return {
            "current": current_value,
            "total": total_value,
            "percent": percent if percent is not None else (int(current_value / total_value * 100) if total_value else 0),
            "current_batch": current_value,
            "total_batches": total_value,
            "successful_batches": successful,
            "failed_batches": failed,
            "stage": stage or cls.STAGE_LABELS.get(str(checkpoint.get("stage")), "Running"),
        }

    @classmethod
    def _validate_stage(cls, stage: str) -> None:
        if stage not in cls.STAGES - {"completed", "failed"}:
            raise ValueError(f"Unknown context workflow stage: {stage}")

    @staticmethod
    def _configuration_fields(context: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "provider": context.get("provider"),
            "model": context.get("model"),
            "source_lang": context.get("source_lang"),
            "target_lang": context.get("target_lang"),
            "target": context.get("target", context.get("target_lang")),
            "description_language": context.get("description_language"),
            "description": context.get("description", context.get("description_language")),
        }

    def _set_status(self, project_id: str, **updates: Any) -> None:
        with self._status_lock:
            current = self._statuses.setdefault(project_id, self._idle_status())
            current.update(_copy(updates))


def _copy(value: Any) -> Any:
    from copy import deepcopy

    return deepcopy(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unique_strings(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
