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
