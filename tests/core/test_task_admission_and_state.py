"""Task admission rollback and in-memory/ledger consistency."""

import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.core.services.agent_job_admission import bind_agent_translation_job
from scripts.core.services.initial_translation_start_service import (
    ProjectTranslationLockError,
    claim_project_translation_lock,
)
from scripts.shared import task_state
from scripts.shared.task_admission import rollback_unstarted_task

WRITE_KEY = "project_translation_write:project-1"


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "tasks.sqlite"
    migrate_main_database(str(db_path))
    repo = TaskRepository(str(db_path))
    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    task_state.tasks.clear()
    task_state.configure_repository(repo)
    try:
        yield repo
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def _create_translation(task_id, *, status="pending", dedupe_key=WRITE_KEY):
    task_state.create_task(
        task_id,
        status=status,
        fields={"kind": "initial_translation", "project_id": "project-1", "blocking": True},
        dedupe_key=dedupe_key,
        reject_duplicate=True,
    )


def test_admission_failure_releases_the_project_write_key(repository):
    _create_translation("admitted")

    with pytest.raises(RuntimeError, match="enqueue failed"):
        with rollback_unstarted_task("admitted"):
            raise RuntimeError("enqueue failed")

    assert task_state.get_task("admitted")["status"] == "failed"
    assert repository.get_task("admitted")["status"] == "failed"
    assert task_state.find_active_task_by_dedupe_key(WRITE_KEY) is None


def test_admission_rollback_leaves_finished_tasks_untouched(repository):
    _create_translation("finished", status="completed", dedupe_key=None)

    with pytest.raises(RuntimeError):
        with rollback_unstarted_task("finished"):
            raise RuntimeError("late failure")

    assert task_state.get_task("finished")["status"] == "completed"


def test_lost_project_lock_race_releases_in_memory_write_key(repository):
    # The owner passed the write-key check first and then won the durable lock.
    repository.save_task(
        {
            "task_id": "owner",
            "kind": "initial_translation",
            "project_id": "project-1",
            "status": "running",
            "created_at": "2026-10-08T00:00:00Z",
            "updated_at": "2026-10-08T00:00:00Z",
        }
    )
    assert repository.acquire_project_lock(task_id="owner", project_id="project-1")
    _create_translation("loser")

    with pytest.raises(ProjectTranslationLockError):
        claim_project_translation_lock(task_id="loser", project_id="project-1")

    assert task_state.tasks["loser"]["status"] == "failed"
    assert task_state.find_active_task_by_dedupe_key(WRITE_KEY) is None
    assert repository.get_project_lock("project-1")["task_id"] == "owner"


def test_agent_binding_failure_releases_task_and_plan(repository):
    _create_translation("agent-job", status="starting")

    class BrokenRegistry:
        released = []

        def record_job(self, **_kwargs):
            raise OSError("registry is read-only")

        def release_plan(self, plan_id):
            self.released.append(plan_id)

    registry = BrokenRegistry()
    with pytest.raises(OSError):
        bind_agent_translation_job(
            job_id="agent-job",
            project_id="project-1",
            plan_id="plan-1",
            execution_args={},
            registry=registry,
        )

    assert task_state.get_task("agent-job")["status"] == "failed"
    assert registry.released == ["plan-1"]


@pytest.mark.parametrize(
    ("worker_status", "expected"),
    [("completed", "completed"), ("failed", "cancelled"), ("interrupted", "interrupted")],
)
def test_cancelling_accepts_the_workers_terminal_outcome(repository, worker_status, expected):
    _create_translation("cancel-me", status="running")
    task_state.request_task_cancellation("cancel-me")
    task_state.update_task("cancel-me", status="processing", push=False)
    assert task_state.get_task("cancel-me")["status"] == "cancelling"

    task_state.update_task("cancel-me", status=worker_status, push=False)

    assert task_state.get_task("cancel-me")["status"] == expected
    assert task_state.find_active_task_by_dedupe_key(WRITE_KEY) is None


def test_update_after_direct_ledger_write_keeps_the_ledger_change(repository):
    _create_translation("interrupted-run", status="running")
    task_state.update_task(
        "interrupted-run",
        status="interrupted",
        fields={"checkpoint": {"available": True, "stage": "Translating"}},
        push=False,
    )
    # A recovery action edits SQLite directly, as clear_project_checkpoint does.
    persisted = repository.get_task("interrupted-run")
    persisted["checkpoint"] = {"available": False, "stage": "cleared"}
    repository.save_task(persisted)

    task_state.update_task("interrupted-run", fields={"archived_at": "2026-10-08T00:00:00Z"}, push=False)

    stored = repository.get_task("interrupted-run")
    assert stored["archived_at"] == "2026-10-08T00:00:00Z"
    assert stored["checkpoint"]["stage"] == "cleared"


def test_reading_a_historical_task_does_not_grow_the_live_mirror(repository):
    repository.save_task(
        {
            "task_id": "old-task",
            "kind": "deployment",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )

    assert task_state.get_task("old-task")["status"] == "completed"
    assert "old-task" not in task_state.tasks

    archived = task_state.update_task("old-task", fields={"archived_at": "2026-10-08T00:00:00Z"}, push=False)
    assert archived["kind"] == "deployment"
    assert repository.get_task("old-task")["status"] == "completed"


def test_agent_binding_preserves_incremental_workflow_kind(repository):
    _create_translation("incremental-agent", status="starting")

    class Registry:
        def record_job(self, **kwargs):
            self.recorded = kwargs

    registry = Registry()
    bind_agent_translation_job(
        job_id="incremental-agent", project_id="project-1", plan_id="plan-1",
        execution_args={"workflow": "incremental"}, registry=registry,
    )
    assert repository.get_task("incremental-agent")["agent_job_kind"] == "incremental_translation"
    assert registry.recorded["kind"] == "incremental_translation"


def test_late_terminal_update_does_not_release_replacement_lock(repository):
    _create_translation("old-owner", status="running")
    claim_project_translation_lock(task_id="old-owner", project_id="project-1")
    task_state.update_task("old-owner", status="interrupted", push=False)
    _create_translation("replacement", status="running")
    claim_project_translation_lock(task_id="replacement", project_id="project-1")

    task_state.update_task("old-owner", fields={"archived_at": "2026-10-10T00:00:00Z"}, push=False)

    assert repository.get_project_lock("project-1")["task_id"] == "replacement"
    assert repository.get_task("replacement")["status"] == "running"


def test_diagnostic_on_historical_task_preserves_terminal_identity(repository):
    repository.save_task({"task_id": "history", "kind": "initial_translation", "status": "completed",
                          "project_id": "project-1", "result": {"output": "keep"}})
    assert "history" not in task_state.tasks
    task_state.append_task_event("history", "late diagnostic", push=False)
    stored = repository.get_task("history")
    assert stored["status"] == "completed"
    assert stored["kind"] == "initial_translation"
    assert stored["result"] == {"output": "keep"}


def test_failed_historical_lookup_does_not_write_a_default_snapshot(repository, monkeypatch):
    repository.save_task({"task_id": "history", "kind": "initial_translation", "status": "completed"})
    original_get = repository.get_task

    def denied(*_args, **_kwargs):
        raise OSError("ledger read denied")

    with monkeypatch.context() as patch:
        patch.setattr(repository, "get_task", denied)
        with pytest.raises(OSError, match="ledger read denied"):
            task_state.update_task("history", fields={"archived_at": "later"}, push=False)
    assert "history" not in task_state.tasks
    assert original_get("history")["status"] == "completed"
