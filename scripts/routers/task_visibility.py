"""Translate durable task visibility failures into HTTP responses."""

from fastapi import HTTPException
from scripts.shared import task_state


def persist_visibility(task_id, archived_at):
    try:
        return task_state.set_task_archived_at(task_id, archived_at)
    except task_state.TaskPersistenceError as error:
        raise HTTPException(status_code=503, detail=error.failure) from error
