"""Real SQLite failure/restart regressions for weekly P2 repairs."""
import asyncio
import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.core.db_migrations import migrate_main_database, MAIN_DB_TARGET_VERSION
from scripts.core.db_manager import db_manager
from scripts.core.glossary_manager import GlossaryManager
from scripts.core.repositories.task_repository import TaskRepository
from scripts.routers.tasks import router
from scripts.shared import task_state


@pytest.mark.asyncio
async def test_project_glossary_binding_failure_rolls_back_and_retry_reuses_single_row(tmp_path, monkeypatch):
    path = tmp_path / "glossary.sqlite"
    migrate_main_database(str(path))
    monkeypatch.setattr(db_manager, "db_path", str(path))
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects(project_id,name,game_id,source_path,source_language,status) VALUES ('p','Probe','stellaris','x','en','active')")
        conn.execute("CREATE TRIGGER reject_binding BEFORE INSERT ON project_glossary_bindings BEGIN SELECT RAISE(ABORT,'injected'); END")
    manager = GlossaryManager()
    assert await manager.get_or_create_project_glossary("stellaris", "p", "Probe") is None
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM glossaries").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_glossary_bindings").fetchone()[0] == 0
        conn.execute("DROP TRIGGER reject_binding")
    first, second = await asyncio.gather(*[manager.get_or_create_project_glossary("stellaris", "p", "Probe") for _ in range(2)])
    assert first["glossary_id"] == second["glossary_id"]
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM glossaries").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM project_glossary_bindings").fetchone()[0] == 1
    await db_manager.close_async_engine()


@pytest.mark.asyncio
@pytest.mark.parametrize("owner_key", ["project_id", "owner_project_id"])
async def test_legacy_unbound_glossary_is_rebound_without_duplication(tmp_path, monkeypatch, owner_key):
    path = tmp_path / "legacy-glossary.sqlite"
    migrate_main_database(str(path))
    monkeypatch.setattr(db_manager, "db_path", str(path))
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects(project_id,name,game_id,source_path,source_language,status) VALUES ('p','Probe','stellaris','x','en','active')")
        conn.execute("INSERT INTO glossaries(game_id,name,is_main,raw_metadata) VALUES ('stellaris','Legacy',0,?)", (json.dumps({"kind":"project_neologism_glossary", owner_key:"p"}),))
        original = conn.execute("SELECT glossary_id FROM glossaries").fetchone()[0]
    result = await GlossaryManager().get_or_create_project_glossary("stellaris", "p", "Probe")
    assert result["glossary_id"] == original
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM glossaries").fetchone()[0] == 1
        assert conn.execute("SELECT glossary_id FROM project_glossary_bindings").fetchone()[0] == original
    await db_manager.close_async_engine()


@pytest.mark.parametrize("action, old_value", [("archive", None), ("restore", "2026-10-01T00:00:00Z")])
@pytest.mark.parametrize("historical", [False, True])
def test_task_visibility_failure_preserves_db_and_mirror_then_retry_survives_restart(tmp_path, action, old_value, historical):
    path = tmp_path / "tasks.sqlite"
    migrate_main_database(str(path))
    repository = TaskRepository(str(path))
    task_state.tasks.clear()
    task_state.configure_repository(repository)
    try:
        task_state.create_task("probe", status="completed", fields={"kind":"translation", "archived_at":old_value})
        if historical:
            task_state.tasks.clear()
        before_events = repository.list_events("probe")
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TRIGGER reject_visibility BEFORE UPDATE OF archived_at ON background_tasks WHEN NEW.archived_at IS NOT OLD.archived_at BEGIN SELECT RAISE(ABORT,'injected'); END")
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        response = client.post(f"/api/tasks/probe/{action}")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "task_persistence_failed"
        assert response.json()["detail"]["retryable"] is True
        assert repository.get_task("probe")["archived_at"] == old_value
        assert task_state.get_task("probe")["archived_at"] == old_value
        assert repository.list_events("probe") == before_events
        with sqlite3.connect(path) as conn:
            conn.execute("DROP TRIGGER reject_visibility")
        response = client.post(f"/api/tasks/probe/{action}")
        assert response.status_code == 200
        expected = response.json()["archived_at"]
        assert bool(expected) == (action == "archive")
        task_state.tasks.clear()
        task_state.configure_repository(repository, hydrate=True)
        assert task_state.get_task("probe")["archived_at"] == expected
    finally:
        task_state.configure_repository(None)
        task_state.tasks.clear()


@pytest.mark.parametrize("table, default", [("projects","active"), ("project_files","todo"), ("project_watches","never_scanned")])
def test_v27_nullable_status_upgrade_repairs_null_and_rejects_future_writes(tmp_path, table, default):
    path = tmp_path / "legacy.sqlite"
    migrate_main_database(str(path))
    with sqlite3.connect(path) as conn:
        # Reproduce a v27 table that has always allowed NULL, with old triggers.
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"CREATE TABLE {table}(identity TEXT PRIMARY KEY,status TEXT)")
        conn.execute(f"CREATE TRIGGER trg_{table}_status_insert BEFORE INSERT ON {table} WHEN NEW.status NOT IN ('{default}') BEGIN SELECT RAISE(ABORT,'invalid'); END")
        conn.execute(f"INSERT INTO {table} VALUES ('null',NULL)")
        conn.execute(f"INSERT INTO {table} VALUES ('valid','{default}')")
        conn.execute("DELETE FROM schema_migrations WHERE version=28")
    assert migrate_main_database(str(path)) == MAIN_DB_TARGET_VERSION == 29
    assert migrate_main_database(str(path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT status FROM {table} WHERE identity='null'").fetchone()[0] == default
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"INSERT INTO {table} VALUES ('new',NULL)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE {table} SET status=NULL WHERE identity='valid'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE {table} SET status='mystery' WHERE identity='valid'")
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=28").fetchone()[0] == 1


def test_status_migration_recovers_commit_before_ledger_write(tmp_path):
    path = tmp_path / "crash.sqlite"
    def crash(version, _name):
        if version == 28:
            raise RuntimeError("after DDL commit")
    with pytest.raises(RuntimeError, match="DDL commit"):
        migrate_main_database(str(path), after_migration=crash)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=28").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_%_status_%'").fetchone()[0] == 6
    assert migrate_main_database(str(path)) == MAIN_DB_TARGET_VERSION
    assert migrate_main_database(str(path)) == MAIN_DB_TARGET_VERSION


def test_status_migration_failure_rolls_back_data_and_trigger_replacement(tmp_path):
    from scripts.core.status_contract_migration import enforce_nonnull_status_contracts
    path = tmp_path / "rollback.sqlite"
    with sqlite3.connect(path) as conn:
        for table in ("projects", "project_files", "project_watches"):
            conn.execute(f"CREATE TABLE {table}(status TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES(NULL)")
        conn.execute("CREATE TRIGGER trg_projects_status_insert BEFORE INSERT ON projects WHEN NEW.status='mystery' BEGIN SELECT RAISE(ABORT,'legacy'); END")
        conn.execute("CREATE TRIGGER reject_watch_update BEFORE UPDATE ON project_watches BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        enforce_nonnull_status_contracts(str(path))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT status FROM projects").fetchone()[0] is None
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='trg_projects_status_insert'").fetchone()[0]
        assert "legacy" in sql
        assert "IS NULL" not in sql
