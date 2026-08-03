import pytest

from scripts.routers import tasks as tasks_router
from scripts.shared import task_state


class FailingTaskRepository:
    def __init__(self):
        self.fail = True
        self.saved = []

    def save_task(self, task, *, event=None):
        if self.fail:
            raise OSError("task ledger is read-only")
        self.saved.append((dict(task), event))


def test_task_persistence_failure_is_structured_and_visible_to_api_projection():
    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    repository = FailingTaskRepository()
    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository)
        task_state.create_task(
            "persistence-failure",
            status="running",
            fields={"kind": "translation", "title": "Translation"},
        )

        task = task_state.get_task("persistence-failure")
        assert task["status"] == "running"
        assert task["persistence_failure"] == {
            "code": "task_persistence_failed",
            "retryable": True,
            "error_type": "OSError",
            "last_attempt_at": task["updated_at"],
        }

        summary = tasks_router._from_live_task(task, None)
        assert summary.persistence_failure.code == "task_persistence_failed"
        assert summary.persistence_failure.retryable is True
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_task_persistence_failure_clears_after_ledger_recovers():
    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    repository = FailingTaskRepository()
    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository)
        task_state.create_task("recoverable", status="running")
        assert task_state.get_task("recoverable")["persistence_failure"]

        repository.fail = False
        updated = task_state.update_task(
            "recoverable",
            status="completed",
            append_log="Completed after storage recovered.",
            push=False,
        )

        assert updated["status"] == "completed"
        assert "persistence_failure" not in updated
        assert repository.saved[-1][0]["status"] == "completed"
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_unexpected_repository_bug_is_not_silently_downgraded():
    class BuggyTaskRepository:
        def save_task(self, task, *, event=None):
            raise RuntimeError("programming defect")

    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(BuggyTaskRepository())
        with pytest.raises(RuntimeError, match="programming defect"):
            task_state.create_task("unexpected-defect", status="running")
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)
