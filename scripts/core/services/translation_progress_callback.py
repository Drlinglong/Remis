"""Progress callback factory for the V2 translation workflow."""

import time
from typing import Optional

from scripts.shared import task_state


def build_translation_progress_callback(
    task_id: str,
    *,
    use_resume: bool,
):
    """Build a callback that persists throttled workflow progress."""
    last_update_time = [0.0]

    def progress_callback(
        current,
        total,
        current_file,
        stage="Translating",
        current_batch=0,
        total_batches=0,
        successful_batches=0,
        failed_batches=0,
        error_count=0,
        glossary_issues=0,
        glossary_issue_details=None,
        recovered_retries=0,
        format_issues=0,
        format_repair=None,
        workshop_progress=None,
        log_message: Optional[str] = None,
        event_level: Optional[str] = None,
    ):
        current_time = time.time()
        is_final = stage in ("Completed", "Failed") or (
            total > 0 and current >= total
        )
        should_push = is_final or current_time - last_update_time[0] >= 0.2
        if should_push:
            last_update_time[0] = current_time

        task_state.update_progress(
            task_id,
            current=current,
            total=total,
            current_file=current_file,
            stage=stage,
            current_batch=current_batch,
            total_batches=total_batches,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            error_count=error_count,
            glossary_issues=glossary_issues,
            glossary_issue_details=glossary_issue_details,
            recovered_retries=recovered_retries,
            format_issues=format_issues,
            format_repair=format_repair,
            workshop_progress=workshop_progress,
            log_message=log_message,
            event_level=event_level,
            push=should_push,
            fields={
                "checkpoint": {
                    "available": bool(current > 0 and not is_final),
                    "resume_supported": True,
                    "stage": stage,
                    "cursor": current_file or str(current),
                    "updated_at": task_state.utc_now_iso(),
                    "metadata": {
                        "completed": current,
                        "total": total,
                        "current_batch": current_batch,
                        "total_batches": total_batches,
                        "resume_requested": bool(use_resume),
                    },
                },
            },
        )

    return progress_callback
