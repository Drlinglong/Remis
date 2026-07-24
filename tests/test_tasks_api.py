from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.routers import tasks as tasks_router
from scripts.shared import task_state


class EmptyRegistry:
    def list_jobs(self):
        return []

    def get_job(self, _job_id):
        return None

    def update_snapshot(self, _job_id, _snapshot):
        return None


class ProjectManagerStub:
    def __init__(self, projects=None):
        self.projects = projects or []

    async def get_projects(self):
        return self.projects


@pytest.fixture(autouse=True)
def isolated_tasks(monkeypatch):
    previous = dict(task_state.tasks)
    task_state.tasks.clear()
    monkeypatch.setattr(tasks_router, "agent_registry", EmptyRegistry())
    monkeypatch.setattr(tasks_router, "project_manager", ProjectManagerStub())
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
    assert task.blocking_reason


@pytest.mark.asyncio
async def test_task_detail_aggregates_child_progress_and_attention():
    task_state.create_task(
        "parent",
        status="running",
        fields={"kind": "agent_workshop", "title": "Parent task"},
    )
    task_state.create_task(
        "child-running",
        status="running",
        fields={"parent_task_id": "parent", "title": "Running child"},
    )
    task_state.init_progress("child-running", {"percent": 40})
    task_state.create_task(
        "child-complete",
        status="completed",
        fields={"parent_task_id": "parent", "title": "Completed child"},
    )
    task_state.init_progress("child-complete", {"percent": 100})
    task_state.create_task(
        "child-failed",
        status="failed",
        fields={"parent_task_id": "parent", "title": "Failed child"},
    )
    task_state.init_progress("child-failed", {"percent": 20})

    detail = await tasks_router.get_task_detail("parent")

    assert detail.child_aggregate.total == 3
    assert detail.child_aggregate.active == 1
    assert detail.child_aggregate.attention == 1
    assert detail.child_aggregate.completed == 1
    assert detail.child_aggregate.progress == 53


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


def test_idempotency_key_reuses_persisted_operation_even_after_memory_reset(tmp_path):
    db_path = tmp_path / "task-idempotency.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    task_state.configure_repository(repository)
    try:
        task_state.create_task(
            "task-original",
            status="completed",
            fields={"idempotency_key": "approved-plan-1"},
        )
        task_state.tasks.clear()

        with pytest.raises(task_state.DuplicateTaskError) as exc_info:
            task_state.create_task(
                "task-replayed",
                status="pending",
                fields={"idempotency_key": "approved-plan-1"},
            )

        assert exc_info.value.existing_task["task_id"] == "task-original"
        assert "task-replayed" not in task_state.tasks
    finally:
        task_state.configure_repository(None)


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
async def test_persisted_task_api_keeps_old_actionable_work_visible_and_latest_completion(tmp_path):
    db_path = tmp_path / "task-api.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    task_state.configure_repository(repository)
    try:
        task_state.create_task(
            "running-before-history",
            status="running",
            fields={
                "kind": "translation",
                "title": "Still running",
                "created_at": "2026-07-20T00:00:00Z",
                "updated_at": "2026-07-20T00:00:00Z",
            },
        )
        for index in range(60):
            task_state.create_task(
                f"completed-{index:02d}",
                status="completed",
                fields={
                    "kind": "translation",
                    "title": f"Completed {index}",
                    "created_at": f"2026-07-22T00:{index:02d}:00Z",
                    "updated_at": f"2026-07-22T00:{index:02d}:00Z",
                },
            )

        queue = await tasks_router.list_task_summaries(active_only=True, limit=200)
        latest_completed = await tasks_router.list_task_summaries(
            status="completed",
            limit=1,
        )

        assert queue.total_count == 1
        assert queue.active_count == 1
        assert [task.task_id for task in queue.tasks] == ["running-before-history"]
        assert [task.task_id for task in latest_completed.tasks] == ["completed-59"]
        assert latest_completed.total_count == 60
    finally:
        task_state.configure_repository(None)


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
async def test_task_detail_hides_diagnostics_by_default_and_exports_them_explicitly(tmp_path):
    db_path = tmp_path / "task-diagnostics.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    task_state.configure_repository(repository)
    try:
        task_state.create_task(
            "diagnostic-task",
            status="running",
            log_message="Translation started.",
        )
        task_state.append_task_event(
            "diagnostic-task",
            "Traceback: provider request timed out",
            audience="diagnostic",
            level="error",
            event_type="traceback",
        )

        default_detail = await tasks_router.get_task_detail("diagnostic-task")
        diagnostic_detail = await tasks_router.get_task_detail(
            "diagnostic-task",
            include_diagnostics=True,
        )
        default_export = await tasks_router.export_task_events("diagnostic-task")
        diagnostic_export = await tasks_router.export_task_events(
            "diagnostic-task",
            include_diagnostics=True,
        )

        assert [event.message for event in default_detail.events] == [
            "Translation started.",
        ]
        assert [event.audience for event in diagnostic_detail.events] == [
            "user",
            "diagnostic",
        ]
        assert b"Traceback: provider request timed out" not in default_export.body
        assert b"Traceback: provider request timed out" in diagnostic_export.body
        assert "attachment;" in diagnostic_export.headers["content-disposition"]
    finally:
        task_state.configure_repository(None)


@pytest.mark.asyncio
async def test_terminal_task_can_be_archived_and_restored_but_active_task_cannot():
    task_state.create_task("finished", status="failed", log_message="Failed", fields={"blocking": True})
    task_state.create_task("active", status="running", log_message="Running")

    archived = await tasks_router.archive_task("finished")
    assert archived["archived_at"]
    visible = await tasks_router.list_task_summaries()
    assert [task.task_id for task in visible.tasks] == ["active"]

    detail = await tasks_router.get_task_detail("finished")
    assert detail.archived_at
    assert detail.blocking is False
    await tasks_router.restore_task("finished")
    restored = await tasks_router.list_task_summaries()
    assert {task.task_id for task in restored.tasks} == {"active", "finished"}

    with pytest.raises(HTTPException) as exc_info:
        await tasks_router.archive_task("active")
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_task_history_filters_by_time_range_and_reports_total_before_pagination():
    task_state.create_task(
        "day-one",
        status="completed",
        fields={"created_at": "2026-07-21T23:30:00Z", "title": "Previous local day"},
    )
    task_state.create_task(
        "day-two-a",
        status="failed",
        fields={"created_at": "2026-07-22T00:30:00Z", "title": "First selected-day task"},
    )
    task_state.create_task(
        "day-two-b",
        status="completed",
        fields={"created_at": "2026-07-22T08:30:00Z", "title": "Second selected-day task"},
    )
    await tasks_router.archive_task("day-two-a")

    payload = await tasks_router.list_task_summaries(
        include_archived=True,
        from_time=datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc),
        to_time=datetime(2026, 7, 23, 0, 0, tzinfo=timezone.utc),
        offset=1,
        limit=1,
    )

    assert payload.total_count == 2
    assert len(payload.tasks) == 1
    assert payload.tasks[0].task_id == "day-two-a"
    assert payload.tasks[0].archived_at is not None


@pytest.mark.asyncio
async def test_task_history_filters_glossary_health_checks_by_glossary_id():
    task_state.create_task(
        "health-preview",
        status="running",
        fields={
            "kind": "glossary_health_check",
            "title": "Check glossary",
            "result": {
                "types": ["glossary_health_preview"],
                "metadata": {"preview": {"glossary_ids": [12], "score": 94}},
            },
        },
    )
    task_state.create_task(
        "health-report",
        status="completed",
        fields={
            "kind": "glossary_health_check",
            "title": "Check another glossary",
            "result": {
                "types": ["glossary_health_report"],
                "metadata": {"glossary_ids": [99], "score": 100},
            },
        },
    )
    task_state.create_task(
        "unrelated",
        status="completed",
        fields={
            "kind": "glossary_merge",
            "title": "Merge glossary",
            "result": {"metadata": {"glossary_ids": [12]}},
        },
    )

    payload = await tasks_router.list_task_summaries(
        kind="glossary_health_check",
        glossary_id=12,
    )

    assert payload.total_count == 1
    assert [task.task_id for task in payload.tasks] == ["health-preview"]


@pytest.mark.asyncio
async def test_task_summary_resolves_human_project_context(monkeypatch):
    monkeypatch.setattr(
        tasks_router,
        "project_manager",
        ProjectManagerStub([{
            "project_id": "project-readable",
            "name": "Remis Plan - Demo Mod",
            "game_id": "victoria3",
        }]),
    )
    task_state.create_task(
        "task-with-project",
        status="running",
        fields={
            "kind": "initial_translation",
            "project_id": "project-readable",
            "blocking": True,
        },
    )

    detail = await tasks_router.get_task_detail("task-with-project")

    assert detail.project_context is not None
    assert detail.project_context.name == "Remis Plan - Demo Mod"
    assert detail.project_context.game_id == "victoria3"
    assert detail.blocking is True
