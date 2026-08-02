"""Persistence port for observable context-workflow checkpoints.

The current candidate and context adapters do not yet implement replay from a
batch cursor.  This module therefore persists an inspection-grade checkpoint
without claiming that a failed run can be resumed automatically.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Protocol


class ContextWorkflowCheckpointPort(Protocol):
    """Storage boundary for task-scoped context workflow checkpoints."""

    def save_checkpoint(self, task_id: str, checkpoint: Mapping[str, Any]) -> None:
        """Persist the latest checkpoint projection for a task."""

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        """Load a checkpoint projection, if the task backend has one."""


class TaskStateCheckpointPort:
    """Adapt Remis' persistent task state to the checkpoint storage port."""

    def __init__(self, task_backend: Any):
        self.task_backend = task_backend

    def save_checkpoint(self, task_id: str, checkpoint: Mapping[str, Any]) -> None:
        self.task_backend.update_task(
            task_id,
            fields={"checkpoint": deepcopy(dict(checkpoint))},
            push=False,
        )

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        get_task = getattr(self.task_backend, "get_task", None)
        if get_task is None:
            return None
        task = get_task(task_id) or {}
        checkpoint = task.get("checkpoint")
        return deepcopy(checkpoint) if isinstance(checkpoint, dict) else None
