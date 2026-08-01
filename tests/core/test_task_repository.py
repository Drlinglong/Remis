from datetime import datetime, timedelta, timezone

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.shared import task_state


def test_task_ledger_survives_memory_reset_with_ordered_events(tmp_path):
    db_path = tmp_path / "task-ledger.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    previous_tasks = dict(task_state.tasks)

    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository)
        task_state.create_task(
            "task-persisted",
            status="queued",
            log_message="Queued",
            fields={
                "kind": "initial_translation",
                "project_id": "project-that-may-no-longer-exist",
                "title": "Initial translation",
            },
        )
        task_state.update_task(
            "task-persisted",
            status="running",
            append_log="Started",
        )
        task_state.update_task(
            "task-persisted",
            status="completed",
            append_log="Completed",
        )

        task_state.tasks.clear()
        task_state.configure_repository(repository, hydrate=True)

        restored = task_state.get_task("task-persisted")
        assert restored["status"] == "completed"
        assert restored["started_at"]
        assert restored["finished_at"]
        assert restored["log"] == ["Queued", "Started", "Completed"]
        assert "blocking" not in restored
        assert "source_route" not in restored
        assert [event["message"] for event in task_state.get_task_events("task-persisted")] == [
            "Queued",
            "Started",
            "Completed",
        ]
    finally:
        task_state.configure_repository(None)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_task_page_filters_counts_and_paginates_without_loading_events(tmp_path, monkeypatch):
    db_path = tmp_path / "task-page.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))

    for index in range(205):
        timestamp = f"2026-07-22T{index // 60:02d}:{index % 60:02d}:00Z"
        repository.save_task({
            "task_id": f"completed-{index:03d}",
            "kind": "translation",
            "title": f"Completed {index}",
            "status": "completed",
            "created_at": timestamp,
            "updated_at": timestamp,
        }, event={"message": f"Completed event {index}", "timestamp": timestamp})
    repository.save_task({
        "task_id": "running-older-than-history",
        "kind": "translation",
        "title": "Still running",
        "status": "running",
        "created_at": "2026-07-21T00:00:00Z",
        "updated_at": "2026-07-21T00:00:00Z",
    }, event={"message": "Running event", "timestamp": "2026-07-21T00:00:00Z"})

    monkeypatch.setattr(
        repository,
        "list_events",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("summary pagination must not load task events")
        ),
    )

    active_page = repository.query_task_page(
        statuses={"running"},
        limit=200,
    )
    assert active_page["total_count"] == 1
    assert active_page["active_count"] == 1
    assert active_page["attention_count"] == 0
    assert [task["task_id"] for task in active_page["tasks"]] == [
        "running-older-than-history",
    ]
    assert "log" not in active_page["tasks"][0]

    history_page = repository.query_task_page(offset=200, limit=10)
    assert history_page["total_count"] == 206
    assert len(history_page["tasks"]) == 6


def test_task_page_can_exclude_child_tasks_from_rows_and_global_counts(tmp_path):
    db_path = tmp_path / "task-parent-filter.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    timestamp = "2026-07-26T12:00:00Z"
    repository.save_task({
        "task_id": "parent",
        "kind": "agent_workshop",
        "title": "Format Repair",
        "status": "running",
        "created_at": timestamp,
        "updated_at": timestamp,
    })
    repository.save_task({
        "task_id": "parent:batch:1",
        "kind": "agent_workshop_batch",
        "parent_task_id": "parent",
        "title": "Batch 1",
        "status": "failed",
        "created_at": timestamp,
        "updated_at": timestamp,
    })

    top_level = repository.query_task_page(include_children=False)
    complete_ledger = repository.query_task_page(include_children=True)

    assert [task["task_id"] for task in top_level["tasks"]] == ["parent"]
    assert top_level["total_count"] == 1
    assert top_level["active_count"] == 1
    assert top_level["attention_count"] == 0
    assert {task["task_id"] for task in complete_ledger["tasks"]} == {
        "parent",
        "parent:batch:1",
    }
    assert complete_ledger["total_count"] == 2
    assert complete_ledger["attention_count"] == 1


def test_task_events_default_to_user_audience_and_can_include_diagnostics(tmp_path):
    db_path = tmp_path / "task-events.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(repository)
        task_state.create_task(
            "task-with-diagnostics",
            status="running",
            log_message="Translation started.",
        )
        task_state.append_task_event(
            "task-with-diagnostics",
            "worker=2 batch=4 response_time_ms=850",
            audience="diagnostic",
            level="debug",
            metadata={"worker": 2, "batch": 4},
        )

        user_events = task_state.get_task_events("task-with-diagnostics")
        all_events = task_state.get_task_events(
            "task-with-diagnostics",
            include_diagnostics=True,
        )

        assert [event["message"] for event in user_events] == ["Translation started."]
        assert [event["audience"] for event in all_events] == ["user", "diagnostic"]
        assert all_events[1]["metadata"] == {"worker": 2, "batch": 4}
    finally:
        task_state.configure_repository(None)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_hydration_interrupts_only_explicitly_non_resumable_workshop_tasks(tmp_path):
    db_path = tmp_path / "task-recovery.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        repository.save_task({
            "task_id": "workshop-running",
            "kind": "agent_workshop",
            "title": "Agent Workshop repair",
            "status": "processing",
            "created_at": "2026-07-24T00:00:00Z",
            "updated_at": "2026-07-24T00:01:00Z",
            "checkpoint": {
                "available": False,
                "resume_supported": False,
                "stage": "repairing",
            },
        })
        repository.save_task({
            "task_id": "translation-running",
            "kind": "translation",
            "title": "Translation",
            "status": "processing",
            "created_at": "2026-07-24T00:00:00Z",
            "updated_at": "2026-07-24T00:01:00Z",
        })
        repository.save_task({
            "task_id": "context-running",
            "kind": "neologism_mining",
            "title": "Context analysis",
            "status": "running",
            "created_at": "2026-07-24T00:00:00Z",
            "updated_at": "2026-07-24T00:01:00Z",
        })

        task_state.configure_repository(repository, hydrate=True, replace=True)

        workshop = task_state.get_task("workshop-running")
        translation = task_state.get_task("translation-running")
        context = task_state.get_task("context-running")
        assert workshop["status"] == "interrupted"
        assert workshop["checkpoint"]["stage"] == "interrupted"
        assert workshop["finished_at"]
        assert translation["status"] == "processing"
        assert context["status"] == "interrupted"
        assert context["attention_reason"] == (
            "This context-analysis task cannot resume automatically. Start it again."
        )
        assert task_state.get_task_events("workshop-running")[0]["event_type"] == "recovery_interrupted"
        assert task_state.get_task_events("context-running")[0]["event_type"] == "recovery_interrupted"
    finally:
        task_state.configure_repository(None)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_retention_prunes_only_old_or_excess_terminal_tasks_and_cascades_events(tmp_path):
    db_path = tmp_path / "task-retention.sqlite"
    migrate_main_database(str(db_path))
    repository = TaskRepository(str(db_path))
    now = datetime(2026, 7, 24, tzinfo=timezone.utc)

    for index in range(2):
        timestamp = (now - timedelta(days=index)).isoformat()
        repository.save_task({
            "task_id": f"recent-{index}",
            "status": "completed",
            "title": "Recent task",
            "created_at": timestamp,
            "updated_at": timestamp,
            "finished_at": timestamp,
        }, event={"timestamp": timestamp, "message": "recent"})
    for index in range(4):
        timestamp = (now - timedelta(days=400 + index)).isoformat()
        repository.save_task({
            "task_id": f"old-{index}",
            "status": "failed",
            "title": "Old task",
            "created_at": timestamp,
            "updated_at": timestamp,
            "finished_at": timestamp,
        }, event={"timestamp": timestamp, "message": "old"})
    active_timestamp = (now - timedelta(days=500)).isoformat()
    repository.save_task({
        "task_id": "active-old",
        "status": "running",
        "title": "Active task",
        "created_at": active_timestamp,
        "updated_at": active_timestamp,
    }, event={"timestamp": active_timestamp, "message": "active"})

    result = repository.prune_terminal_tasks(
        retention_days=30,
        max_terminal_tasks=3,
        min_terminal_tasks=1,
        now=now,
    )

    assert result == {
        "terminal_tasks_before": 6,
        "tasks_deleted": 4,
        "terminal_tasks_after": 2,
    }
    assert repository.get_task("recent-0") is not None
    assert repository.get_task("recent-1") is not None
    assert repository.get_task("old-0") is None
    assert repository.get_task("active-old") is not None
    with repository._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM task_events WHERE task_id LIKE 'old-%'"
        ).fetchone()[0] == 0
