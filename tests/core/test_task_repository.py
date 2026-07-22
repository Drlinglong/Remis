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
