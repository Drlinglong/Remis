"""Roll back tasks that were admitted but never handed to their worker.

A route creates the task record (and its project write key or lock) before it
enqueues the background worker. Anything that fails in between would otherwise
leave an active task that no worker will ever finish, blocking the project.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from scripts.shared import task_state

logger = logging.getLogger(__name__)

TASK_NOT_STARTED_REASON = (
    "Remis could not start this task, so no work was performed. Try again."
)


def abandon_unstarted_task(task_id: str, reason: str = TASK_NOT_STARTED_REASON) -> None:
    """Fail a still-active task and release its project ownership."""
    try:
        task = task_state.get_task(task_id)
        if task is None:
            return
        if str(task.get("status") or "").lower() not in task_state.ACTIVE_TASK_STATUSES:
            return
        task_state.update_task(
            task_id,
            status="failed",
            message=reason,
            append_log=reason,
            fields={"attention_reason": reason, "blocking": False},
        )
    except Exception:
        logger.exception("Could not release unstarted task %s", task_id)


@contextmanager
def rollback_unstarted_task(
    task_id: str,
    reason: str = TASK_NOT_STARTED_REASON,
) -> Iterator[None]:
    """Fail the task if the guarded admission steps raise anything."""
    try:
        yield
    except BaseException:
        abandon_unstarted_task(task_id, reason)
        raise
