"""Contract tests for the Issue #213 translation task state machine.

These tests intentionally describe the API for the planned
``TranslationTaskLifecycle`` service before its implementation exists.

The contract assumed here is deliberately small:

* project lock acquisition is a durable, atomic compare-and-set operation;
* a terminal task transition releases only that task's project lock;
* startup recovery treats persisted active translation work as orphaned;
* cancellation is a persisted intermediate state and keeps the lock until
  the worker acknowledges a terminal transition.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.core.services.translation_task_lifecycle import TranslationTaskLifecycle


ACTIVE_TRANSLATION_KINDS = (
    "initial_translation",
    "translation",
    "incremental_translation",
)


def _task(
    task_id: str,
    *,
    kind: str = "initial_translation",
    project_id: str = "project-213",
    status: str = "running",
) -> dict:
    timestamp = "2026-08-31T00:00:00+00:00"
    return {
        "task_id": task_id,
        "kind": kind,
        "title": f"Translation {task_id}",
        "project_id": project_id,
        "status": status,
        "created_at": timestamp,
        "started_at": timestamp,
        "updated_at": timestamp,
        "progress": {"stage": "Translating"},
        "checkpoint": {"available": False, "resume_supported": True},
        "dedupe_key": f"project_translation_write:{project_id}",
        "blocking": True,
    }


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "translation-task-lifecycle.sqlite"
    migrate_main_database(str(db_path))
    return TaskRepository(str(db_path))


def test_project_lock_acquisition_is_atomic_under_concurrent_claims(repository):
    """Exactly one task may own a project's lock, even when both claim at once."""

    repository.save_task(_task("task-lock-a"))
    repository.save_task(_task("task-lock-b"))
    claim_barrier = Barrier(2)

    def claim(task_id):
        lifecycle = TranslationTaskLifecycle(repository)
        claim_barrier.wait(timeout=5)
        return lifecycle.acquire_project_lock(
            task_id=task_id,
            project_id="project-213",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, ("task-lock-a", "task-lock-b")))

    assert sorted(outcomes) == [False, True]
    owner = TranslationTaskLifecycle(repository).get_project_lock("project-213")
    assert owner is not None
    assert owner["task_id"] in {"task-lock-a", "task-lock-b"}


def test_terminal_commit_cannot_be_followed_by_a_project_lock_claim(repository, monkeypatch):
    """A claim that read active state before a terminal commit must be rejected."""

    repository.save_task(_task("task-terminal-race"))
    task_read = Event()
    original_get_task = repository.get_task

    def observe_task_read(task_id):
        task = original_get_task(task_id)
        task_read.set()
        return task

    monkeypatch.setattr(repository, "get_task", observe_task_read)
    terminal_connection = sqlite3.connect(repository.db_path, timeout=10)
    try:
        terminal_connection.execute("BEGIN IMMEDIATE")
        terminal_connection.execute(
            "UPDATE background_tasks SET status = ? WHERE task_id = ?",
            ("completed", "task-terminal-race"),
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                TranslationTaskLifecycle(repository).acquire_project_lock,
                task_id="task-terminal-race",
                project_id="project-213",
            )
            task_read.wait(timeout=1)
            terminal_connection.commit()
            assert future.result(timeout=5) is False
    finally:
        terminal_connection.close()

    assert repository.get_project_lock("project-213") is None


def test_terminal_transition_releases_the_task_project_lock(repository):
    repository.save_task(_task("task-terminal"))
    lifecycle = TranslationTaskLifecycle(repository)

    assert lifecycle.acquire_project_lock(
        task_id="task-terminal",
        project_id="project-213",
    ) is True

    completed = lifecycle.transition("task-terminal", "completed")

    assert completed["status"] == "completed"
    assert repository.get_task("task-terminal")["status"] == "completed"
    assert lifecycle.get_project_lock("project-213") is None


def test_project_lock_reacquisition_is_idempotent_for_the_same_active_task(repository):
    repository.save_task(_task("task-idempotent-lock"))
    lifecycle = TranslationTaskLifecycle(repository)

    assert lifecycle.acquire_project_lock(
        task_id="task-idempotent-lock",
        project_id="project-213",
    ) is True
    assert lifecycle.acquire_project_lock(
        task_id="task-idempotent-lock",
        project_id="project-213",
    ) is True
    assert lifecycle.get_project_lock("project-213")["task_id"] == "task-idempotent-lock"


@pytest.mark.parametrize(
    "status",
    (
        "completed",
        "complete",
        "success",
        "failed",
        "partial_failed",
        "cancelled",
        "canceled",
        "interrupted",
    ),
)
def test_terminal_translation_task_cannot_acquire_project_lock(repository, status):
    repository.save_task(_task(f"terminal-{status}", status=status))

    assert TranslationTaskLifecycle(repository).acquire_project_lock(
        task_id=f"terminal-{status}",
        project_id="project-213",
    ) is False
    assert repository.get_project_lock("project-213") is None


def test_non_translation_task_cannot_acquire_project_lock(repository):
    repository.save_task(_task("workshop", kind="agent_workshop"))

    assert TranslationTaskLifecycle(repository).acquire_project_lock(
        task_id="workshop",
        project_id="project-213",
    ) is False
    assert repository.get_project_lock("project-213") is None


@pytest.mark.parametrize("kind", ACTIVE_TRANSLATION_KINDS)
def test_restart_recovery_interrupts_each_translation_kind_idempotently(repository, kind):
    task_id = f"orphan-{kind}"
    repository.save_task(_task(task_id, kind=kind))
    lifecycle = TranslationTaskLifecycle(repository)
    assert lifecycle.acquire_project_lock(
        task_id=task_id,
        project_id="project-213",
    ) is True

    lifecycle.recover_orphaned_tasks()
    recovered = repository.get_task(task_id)
    first_events = repository.list_events(task_id)

    assert recovered["status"] == "interrupted"
    assert recovered["finished_at"]
    assert lifecycle.get_project_lock("project-213") is None
    assert [event["event_type"] for event in first_events].count(
        "recovery_interrupted"
    ) == 1

    # A second desktop start must not create another transition or event.
    lifecycle = TranslationTaskLifecycle(repository)
    lifecycle.recover_orphaned_tasks()
    recovered_again = repository.get_task(task_id)
    second_events = repository.list_events(task_id)

    assert recovered_again["status"] == "interrupted"
    assert recovered_again["finished_at"] == recovered["finished_at"]
    assert second_events == first_events


def test_terminal_task_cannot_be_moved_back_to_cancelling(repository):
    repository.save_task(_task("task-already-complete", status="completed"))
    lifecycle = TranslationTaskLifecycle(repository)

    with pytest.raises(ValueError, match="terminal"):
        lifecycle.transition("task-already-complete", "cancelling")

    assert repository.get_task("task-already-complete")["status"] == "completed"


def test_cancellation_request_is_persisted_and_keeps_lock_until_acknowledged(repository):
    repository.save_task(_task("task-cancel"))
    lifecycle = TranslationTaskLifecycle(repository)
    assert lifecycle.acquire_project_lock(
        task_id="task-cancel",
        project_id="project-213",
    ) is True

    requested = lifecycle.request_cancellation("task-cancel")

    assert requested["status"] == "cancelling"
    assert repository.get_task("task-cancel")["status"] == "cancelling"
    assert lifecycle.get_project_lock("project-213")["task_id"] == "task-cancel"

    lifecycle = TranslationTaskLifecycle(repository)
    assert lifecycle.transition("task-cancel", "cancelled")["status"] == "cancelled"
    assert lifecycle.get_project_lock("project-213") is None
