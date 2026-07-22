from __future__ import annotations

import pytest
from fastapi import HTTPException

from scripts.routers import tasks as tasks_router
from scripts.shared import task_state


class EmptyRegistry:
    def list_jobs(self):
        return []

    def get_job(self, _job_id):
        return None

    def update_snapshot(self, _job_id, _snapshot):
        return None


@pytest.fixture(autouse=True)
def isolated_tasks(monkeypatch):
    previous = dict(task_state.tasks)
    task_state.tasks.clear()
    monkeypatch.setattr(tasks_router, "agent_registry", EmptyRegistry())
    yield
    task_state.tasks.clear()
    task_state.tasks.update(previous)


@pytest.mark.asyncio
async def test_task_summary_exposes_actor_tree_recovery_and_result_contract():
    task_state.create_task(
        "task-1",
        status="running",
        fields={
            "kind": "incremental_translation",
            "project_id": "project-1",
            "parent_task_id": "agent-parent",
            "created_by": {"type": "remis_agent", "label": "Remis Agent"},
            "checkpoint": {
                "available": True,
                "resume_supported": True,
                "stage": "batch-4",
                "cursor": "4",
            },
            "result": {
                "types": ["files", "change_summary"],
                "output_paths": ["translated/project-1"],
                "summary": "4 files updated",
            },
            "blocking": True,
            "idempotency_key": "plan-1",
        },
        dedupe_key="project_translation_write:project-1",
    )
    task_state.init_progress("task-1", {"percent": 40, "stage": "Translating"})

    payload = await tasks_router.list_task_summaries()

    task = payload.tasks[0]
    assert task.created_by.type == "remis_agent"
    assert task.parent_task_id == "agent-parent"
    assert task.checkpoint.resume_supported is True
    assert task.result.types == ["files", "change_summary"]
    assert task.blocking is True
    assert task.dedupe_key == "project_translation_write:project-1"
    assert task.idempotency_key == "plan-1"


def test_duplicate_write_task_returns_existing_task_atomically():
    task_state.create_task(
        "task-original",
        status="running",
        dedupe_key="project_translation_write:project-1",
        reject_duplicate=True,
    )

    with pytest.raises(task_state.DuplicateTaskError) as exc_info:
        task_state.create_task(
            "task-duplicate",
            status="pending",
            dedupe_key="project_translation_write:project-1",
            reject_duplicate=True,
        )

    assert exc_info.value.existing_task["task_id"] == "task-original"
    assert "task-duplicate" not in task_state.tasks


def test_terminal_task_releases_dedupe_key():
    task_state.create_task(
        "task-complete",
        status="completed",
        dedupe_key="project_translation_write:project-1",
    )

    created = task_state.create_task(
        "task-next",
        status="pending",
        dedupe_key="project_translation_write:project-1",
        reject_duplicate=True,
    )

    assert created["task_id"] == "task-next"


@pytest.mark.asyncio
async def test_task_counts_are_global_and_non_mutating_agent_work_does_not_block():
    for index in range(3):
        task_state.create_task(
            f"dry-run-{index}",
            status="running",
            fields={"kind": "dry_run", "title": "Agent dry run"},
        )

    payload = await tasks_router.list_task_summaries(limit=1)

    assert len(payload.tasks) == 1
    assert payload.active_count == 3
    assert payload.tasks[0].blocking is False


@pytest.mark.asyncio
async def test_task_detail_is_bound_to_task_id_and_exposes_its_own_log():
    task_state.create_task(
        "failed-task",
        status="failed",
        log_message="Translation failed for old run",
        fields={"kind": "initial_translation", "title": "Old translation"},
    )
    task_state.create_task(
        "successful-task",
        status="completed",
        log_message="Translation completed for new run",
        fields={"kind": "initial_translation", "title": "New translation"},
    )

    failed = await tasks_router.get_task_detail("failed-task")
    successful = await tasks_router.get_task_detail("successful-task")

    assert failed.task_id == "failed-task"
    assert failed.status == "failed"
    assert [event.message for event in failed.events] == ["Translation failed for old run"]
    assert successful.task_id == "successful-task"
    assert successful.status == "completed"
    assert [event.message for event in successful.events] == ["Translation completed for new run"]


@pytest.mark.asyncio
async def test_terminal_task_can_be_archived_and_restored_but_active_task_cannot():
    task_state.create_task("finished", status="failed", log_message="Failed")
    task_state.create_task("active", status="running", log_message="Running")

    archived = await tasks_router.archive_task("finished")
    assert archived["archived_at"]
    visible = await tasks_router.list_task_summaries()
    assert [task.task_id for task in visible.tasks] == ["active"]

    detail = await tasks_router.get_task_detail("finished")
    assert detail.archived_at
    await tasks_router.restore_task("finished")
    restored = await tasks_router.list_task_summaries()
    assert {task.task_id for task in restored.tasks} == {"active", "finished"}

    with pytest.raises(HTTPException) as exc_info:
        await tasks_router.archive_task("active")
    assert exc_info.value.status_code == 409
