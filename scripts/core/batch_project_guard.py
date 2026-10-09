"""Hold the existing translation project lock only during local apply."""
from contextlib import contextmanager
from datetime import datetime, timezone
import uuid

from .batch_repository import BatchConflict


class BatchProjectGuard:
    def __init__(self, task_repository):
        self.repository = task_repository

    @contextmanager
    def __call__(self, project_id):
        identifier = "batch_apply_task_" + uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        task = {"task_id": identifier, "kind": "translation", "project_id": project_id,
                "status": "running", "created_at": now, "updated_at": now,
                "agent_job_kind": "batch_apply", "message": "Applying validated Batch output."}
        self.repository.save_task(task)
        outcome = "failed"
        try:
            if not self.repository.acquire_project_lock(task_id=identifier, project_id=project_id):
                raise BatchConflict("project_busy", "Another translation operation owns this project.")
            yield
            outcome = "completed"
        finally:
            task.update(status=outcome, updated_at=datetime.now(timezone.utc).isoformat())
            try:
                self.repository.save_task(task)
            finally:
                self.repository.release_project_lock(task_id=identifier)
