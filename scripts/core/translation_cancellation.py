"""Cooperative cancellation boundary for background translation workflows."""

from functools import wraps

from scripts.core.parallel_processor import ProcessingCancelledError
from scripts.shared import task_state


def _finalize_cancelled(task_id: str) -> None:
    task_state.update_task(
        task_id,
        status="cancelled",
        message="Translation cancelled. No further provider requests will be made.",
        append_log="Translation cancelled. No further provider requests will be made.",
        progress={"stage": "Cancelled"},
        push=True,
    )


def cancellable_translation_workflow(workflow):
    """Keep cancellation terminal handling outside the legacy router workflow."""
    @wraps(workflow)
    def wrapped(*args, **kwargs):
        task_id = str(args[0] if args else kwargs["task_id"])
        if task_state.is_task_cancellation_requested(task_id):
            _finalize_cancelled(task_id)
            return None
        try:
            result = workflow(*args, **kwargs)
        except ProcessingCancelledError:
            _finalize_cancelled(task_id)
            return None
        if task_state.is_task_cancellation_requested(task_id):
            _finalize_cancelled(task_id)
        return result

    return wrapped
