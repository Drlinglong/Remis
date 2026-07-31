"""Persist stable parent and child task projections for Format Repair runs."""

from __future__ import annotations

from typing import Any


class WorkshopTaskProjector:
    """Translate coordinator events into the existing task-state contract."""

    def __init__(
        self,
        *,
        task_store: Any,
        task_id: str,
        project_id: str,
        created_by: dict[str, Any],
        total: int,
        total_batches: int,
    ) -> None:
        self.task_store = task_store
        self.task_id = task_id
        self.project_id = project_id
        self.created_by = created_by
        self.total = total
        self.total_batches = total_batches
        self.child_task_ids: dict[int, str] = {}

    def queue_child_task(
        self,
        batch_number: int,
        batch: list[dict[str, Any]],
    ) -> str:
        child_task_id = f"{self.task_id}:batch:{batch_number}"
        self.child_task_ids[batch_number] = child_task_id
        self.task_store.create_task(
            child_task_id,
            status="queued",
            log_message=(
                f"Repair batch {batch_number}/{self.total_batches} queued."
            ),
            fields={
                "kind": "agent_workshop_batch",
                "project_id": self.project_id,
                "parent_task_id": self.task_id,
                "title": (
                    f"Format Repair batch {batch_number}/{self.total_batches}"
                ),
                "source_route": f"/tasks/{self.task_id}",
                "created_by": self.created_by,
                "blocking": False,
                "workflow_context": {
                    "mode": "repair_batch",
                    "project_id": self.project_id,
                    "parent_task_id": self.task_id,
                    "batch_number": batch_number,
                    "issue_count": len(batch),
                },
                "checkpoint": {
                    "available": False,
                    "resume_supported": False,
                    "stage": "queued",
                    "metadata": {
                        "batch_number": batch_number,
                        "issue_count": len(batch),
                    },
                },
            },
        )
        return child_task_id

    def start_parent(
        self,
        *,
        concurrency: int,
        rpm: int,
        max_retries: int,
    ) -> None:
        self.task_store.init_progress(
            self.task_id,
            {
                "total": self.total,
                "current": 0,
                "percent": 0,
                "stage": "Format Repair",
                "current_batch": 0,
                "total_batches": self.total_batches,
            },
        )
        self.task_store.update_task(
            self.task_id,
            status="processing",
            append_log=(
                f"Format Repair started repairing {self.total} issue(s) "
                f"in {self.total_batches} batch(es)."
            ),
        )
        self.task_store.append_task_event(
            self.task_id,
            (
                "Format Repair execution settings: "
                f"concurrency={concurrency}, rpm={rpm}, "
                f"max_retries={max_retries}."
            ),
            audience="diagnostic",
            level="debug",
            event_type="execution_settings",
        )

    def start_child(
        self,
        *,
        worker_id: int,
        batch_number: int,
        batch_size: int,
        completed: int,
    ) -> None:
        child_task_id = self.child_task_ids[batch_number]
        self.task_store.update_task(
            child_task_id,
            status="processing",
            progress={
                "current": 0,
                "total": batch_size,
                "percent": 0,
                "stage": "Repairing",
            },
            append_log=(
                f"Repair batch {batch_number}/{self.total_batches} started."
            ),
        )
        self.task_store.update_progress(
            self.task_id,
            current=completed,
            total=self.total,
            current_batch=batch_number,
            total_batches=self.total_batches,
            stage="Format Repair",
            log_message=(
                f"Worker {worker_id}: fixing batch {batch_number}/"
                f"{self.total_batches} ({batch_size} issue(s))."
            ),
            event_audience="diagnostic",
            push=True,
        )

    def complete_child(
        self,
        *,
        batch_number: int,
        batch_size: int,
        batch_results: list[dict[str, Any]],
        batch_success: int,
        batch_failed: int,
    ) -> None:
        child_status = "completed" if batch_failed == 0 else "partial_failed"
        child_summary = (
            f"{batch_success} fixed, {batch_failed} still require review."
        )
        self.task_store.update_task(
            self.child_task_ids[batch_number],
            status=child_status,
            progress={
                "current": batch_size,
                "total": batch_size,
                "percent": 100,
                "stage": "Completed" if batch_failed == 0 else "Needs review",
            },
            summary={
                "total": batch_size,
                "successCount": batch_success,
                "failedCount": batch_failed,
            },
            fields={
                "result": {
                    "types": ["workshop_repairs"],
                    "summary": child_summary,
                    "metadata": {
                        "batch_number": batch_number,
                        "results": batch_results,
                    },
                },
                "attention_reason": child_summary if batch_failed else None,
            },
            append_log=(
                f"Repair batch {batch_number}/{self.total_batches} completed."
                if batch_failed == 0
                else (
                    f"Repair batch {batch_number}/{self.total_batches} "
                    f"needs review: {batch_failed} item(s) failed."
                )
            ),
        )

    def record_batch_progress(
        self,
        *,
        batch_number: int,
        batch_size: int,
        batch_success: int,
        completed: int,
        success_count: int,
        failed_count: int,
    ) -> None:
        self.task_store.update_progress(
            self.task_id,
            current=completed,
            total=self.total,
            current_batch=batch_number,
            total_batches=self.total_batches,
            successful_batches=success_count,
            failed_batches=failed_count,
            stage="Format Repair",
            log_message=(
                f"Batch {batch_number}/{self.total_batches} completed: "
                f"{batch_success}/{batch_size} fixed."
            ),
            event_audience="diagnostic",
            push=True,
        )

    def fail_child(
        self,
        *,
        batch_number: int,
        batch_size: int,
        error: Exception,
        completed: int,
        failed_count: int,
    ) -> None:
        child_task_id = self.child_task_ids[batch_number]
        self.task_store.update_task(
            child_task_id,
            status="failed",
            message="The batch could not be completed.",
            progress={
                "current": batch_size,
                "total": batch_size,
                "percent": 100,
                "stage": "Failed",
            },
            fields={
                "result": {
                    "types": ["workshop_repairs"],
                    "summary": "No repairs from this batch were applied.",
                    "metadata": {"batch_number": batch_number},
                },
                "attention_reason": (
                    "The batch failed before producing a complete result."
                ),
            },
            append_log=(
                f"Repair batch {batch_number}/{self.total_batches} failed."
            ),
        )
        self.task_store.append_task_event(
            child_task_id,
            str(error),
            audience="diagnostic",
            level="error",
            event_type="batch_exception",
        )
        self.task_store.update_progress(
            self.task_id,
            current=completed,
            total=self.total,
            current_batch=batch_number,
            total_batches=self.total_batches,
            failed_batches=failed_count,
            stage="Format Repair",
            log_message=(
                f"Batch {batch_number}/{self.total_batches} failed: {error}"
            ),
            event_audience="diagnostic",
            push=True,
        )

    def complete_parent(
        self,
        *,
        summary: dict[str, Any],
        results: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
        success_count: int,
        failed_count: int,
    ) -> None:
        report_paths = sorted(
            {
                str(item.get("report_path"))
                for item in results
                if item.get("report_path")
            }
        )
        result_summary = (
            f"{success_count} issue(s) fixed."
            if failed_count == 0
            else (
                f"{success_count} issue(s) fixed; "
                f"{failed_count} still require review."
            )
        )
        self.task_store.update_task(
            self.task_id,
            status="completed" if failed_count == 0 else "partial_failed",
            progress={
                "current": self.total,
                "total": self.total,
                "percent": 100,
                "stage": "Completed" if failed_count == 0 else "Needs review",
            },
            summary=summary,
            fields={
                "results": results,
                "attempts": attempts,
                "result": {
                    "types": [
                        "workshop_repairs",
                        *(["repair_reports"] if report_paths else []),
                    ],
                    "output_paths": report_paths,
                    "summary": result_summary,
                    "metadata": {
                        "total": self.total,
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "batch_task_ids": [
                            self.child_task_ids[index]
                            for index in sorted(self.child_task_ids)
                        ],
                    },
                },
                "attention_reason": result_summary if failed_count else None,
            },
            append_log=(
                "Format Repair run completed."
                if failed_count == 0
                else (
                    "Format Repair run finished with "
                    f"{failed_count} item(s) requiring review."
                )
            ),
        )

    def fail_parent(self, error: Exception) -> None:
        self.task_store.update_task(
            self.task_id,
            status="failed",
            message="Format Repair could not complete this repair run.",
            append_log=(
                "Format Repair run failed. Open diagnostics for technical details."
            ),
        )
        self.task_store.append_task_event(
            self.task_id,
            str(error),
            audience="diagnostic",
            level="error",
            event_type="run_exception",
        )
