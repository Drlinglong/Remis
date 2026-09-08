import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.task_repository import (
    TaskIdempotencyConflictError,
    TaskRepository,
)
from scripts.shared import task_state


def _minimal_task(task_id: str, key: str, updated_at: str) -> dict:
    return {
        "task_id": task_id,
        "kind": "initial_translation",
        "title": "Initial translation",
        "status": "queued",
        "idempotency_key": key,
        "created_at": updated_at,
        "updated_at": updated_at,
    }


def test_idempotency_migration_reconciles_legacy_duplicates_and_blank_values(tmp_path):
    db_path = tmp_path / "legacy-idempotency.sqlite"
    migrate_main_database(str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DROP INDEX ux_background_tasks_idempotency_key_nonempty"
        )
        connection.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (24,),
        )
        connection.executemany(
            """
            INSERT INTO background_tasks
                (task_id, kind, title, status, idempotency_key,
                 created_at, updated_at, payload)
            VALUES (?, 'initial_translation', 'Translation', 'queued', ?, ?, ?, ?)
            """,
            [
                ("old-key", "legacy-key", "2026-08-01", "2026-08-01", '{"idempotency_key":"legacy-key"}'),
                ("new-key", " legacy-key ", "2026-08-02", "2026-08-02", '{"idempotency_key":" legacy-key "}'),
                ("blank-key", "", "2026-08-03", "2026-08-03", '{"note":"blank"}'),
                ("null-key", None, "2026-08-04", "2026-08-04", '{"note":"null"}'),
            ],
        )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION

    repository = TaskRepository(str(db_path))
    assert repository.find_by_idempotency_key("legacy-key")["task_id"] == "new-key"
    assert repository.get_task("old-key")["idempotency_key"] is None
    with sqlite3.connect(db_path) as connection:
        old_payload = connection.execute(
            "SELECT payload FROM background_tasks WHERE task_id = 'old-key'"
        ).fetchone()[0]
        assert "idempotency_key" not in old_payload
        assert connection.execute(
            "SELECT idempotency_key FROM background_tasks WHERE task_id = 'blank-key'"
        ).fetchone()[0] == ""
        assert connection.execute(
            "SELECT idempotency_key FROM background_tasks WHERE task_id = 'null-key'"
        ).fetchone()[0] is None
        index_names = {
            row[1] for row in connection.execute("PRAGMA index_list(background_tasks)")
        }
        assert "ux_background_tasks_idempotency_key_nonempty" in index_names


def test_separate_repository_connections_allow_one_idempotency_winner(tmp_path):
    db_path = tmp_path / "concurrent-idempotency.sqlite"
    migrate_main_database(str(db_path))
    barrier = Barrier(2)

    def persist(task_id: str):
        repository = TaskRepository(str(db_path))
        barrier.wait(timeout=10)
        try:
            repository.save_task(_minimal_task(task_id, "same-key", "2026-08-05"))
            return ("created", task_id)
        except TaskIdempotencyConflictError as exc:
            return ("conflict", exc.existing_task["task_id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(persist, ("worker-a", "worker-b")))

    assert sorted(result[0] for result in results) == ["conflict", "created"]
    repository = TaskRepository(str(db_path))
    winner = repository.find_by_idempotency_key("same-key")
    assert winner["task_id"] in {"worker-a", "worker-b"}
    assert sum(1 for result in results if result[1] == winner["task_id"]) == 2


def test_task_state_converts_repository_idempotency_conflict_to_existing_task():
    existing = _minimal_task("winner", "same-key", "2026-08-05")

    class RacingRepository:
        def find_by_idempotency_key(self, _key):
            return None

        def save_task(self, _task, *, event=None):
            raise TaskIdempotencyConflictError("same-key", existing)

    previous_repository = task_state.get_repository()
    previous_tasks = dict(task_state.tasks)
    try:
        task_state.tasks.clear()
        task_state.configure_repository(RacingRepository())
        with pytest.raises(task_state.DuplicateTaskError) as exc_info:
            task_state.create_task(
                "loser",
                fields={"kind": "initial_translation", "idempotency_key": "same-key"},
            )
        assert exc_info.value.existing_task["task_id"] == "winner"
        assert "loser" not in task_state.tasks
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)
