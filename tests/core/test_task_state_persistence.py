import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
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

    def find_active_by_dedupe_key(self, *_args, **_kwargs):
        return None


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


def test_required_task_persistence_rejects_admission_and_releases_task_id():
    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(FailingTaskRepository())

        with pytest.raises(task_state.TaskPersistenceError) as exc_info:
            task_state.create_task(
                "durable-task",
                status="pending",
                dedupe_key="durable-operation",
                require_persistence=True,
            )

        assert exc_info.value.failure["code"] == "task_persistence_failed"
        assert "durable-task" not in task_state.tasks
        assert task_state.find_active_task_by_dedupe_key("durable-operation") is None
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


@pytest.mark.parametrize(
    "kind",
    ["initial_translation", "translation", "incremental_translation"],
)
def test_startup_recovers_each_translation_kind_and_releases_project_lock(tmp_path, kind):
    db_path = tmp_path / "translation-recovery.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    task_id = f"orphan-{kind}"
    repository.save_task(
        {
            "task_id": task_id,
            "kind": kind,
            "project_id": f"project-{kind}",
            "status": "running",
            "created_at": "2026-08-31T00:00:00Z",
            "updated_at": "2026-08-31T00:01:00Z",
            "checkpoint": {"available": True, "resume_supported": True},
            "blocking": True,
        }
    )
    assert repository.acquire_project_lock(
        task_id=task_id,
        project_id=f"project-{kind}",
    ) is True

    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository, hydrate=True, replace=True)

        recovered = task_state.get_task(task_id)
        assert recovered["status"] == "interrupted"
        assert recovered["attention_reason"]
        assert repository.get_project_lock(f"project-{kind}") is None
        assert repository.get_task(task_id)["status"] == "interrupted"
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_cancellation_request_survives_in_memory_state_reset(tmp_path):
    db_path = tmp_path / "translation-cancellation.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    repository.save_task(
        {
            "task_id": "persisted-cancellation",
            "kind": "translation",
            "status": "running",
            "created_at": "2026-08-31T00:00:00Z",
            "updated_at": "2026-08-31T00:01:00Z",
        }
    )

    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository)
        task_state.request_task_cancellation("persisted-cancellation")
        task_state.tasks.clear()
        task_state._CANCELLATION_EVENTS.clear()

        assert task_state.is_task_cancellation_requested("persisted-cancellation") is True
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_translation_task_cannot_leave_terminal_state():
    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.configure_repository(None)
        task_state.tasks.clear()
        task_state.create_task(
            "terminal-translation",
            status="completed",
            fields={"kind": "translation"},
        )

        with pytest.raises(ValueError, match="terminal"):
            task_state.update_task("terminal-translation", status="cancelled")
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)
