import datetime
import json
import logging
import sqlite3
from typing import Callable

from sqlmodel import SQLModel, create_engine

from scripts.core.db_models import (
    ActivityLog,
    Glossary,
    GlossaryEntry,
    Project,
    ProjectFile,
    ProjectGlossaryBinding,
    ProjectHistory,
    ProjectWatch,
    ProjectWatchFileSnapshot,
)

logger = logging.getLogger("remis_init")

MAIN_DB_TARGET_VERSION = 4


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    ddl: str,
) -> None:
    if column_name in _column_names(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def _ensure_index(conn: sqlite3.Connection, ddl: str) -> None:
    conn.execute(ddl)


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    _ensure_migrations_table(conn)
    cursor = conn.execute("SELECT version FROM schema_migrations")
    return {row["version"] for row in cursor.fetchall()}


def _record_migration(conn: sqlite3.Connection, version: int, name: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO schema_migrations (version, name, applied_at)
        VALUES (?, ?, ?)
        """,
        (version, name, datetime.datetime.now().isoformat()),
    )


def _migration_001_establish_managed_main_schema(db_path: str) -> None:
    path = db_path.replace("\\", "/")
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)

    with _connect(db_path) as conn:
        _ensure_column(conn, "glossaries", "version", "version TEXT")
        _ensure_column(conn, "glossaries", "sources", "sources JSON")
        _ensure_column(conn, "glossaries", "raw_metadata", "raw_metadata JSON")

        _ensure_column(conn, "entries", "abbreviations", "abbreviations JSON")
        _ensure_column(conn, "entries", "variants", "variants JSON")
        _ensure_column(conn, "entries", "raw_metadata", "raw_metadata JSON")

        _ensure_column(conn, "projects", "target_path", "target_path TEXT")
        _ensure_column(conn, "projects", "source_language", "source_language TEXT NOT NULL DEFAULT 'english'")
        _ensure_column(conn, "projects", "last_modified", "last_modified TEXT")
        _ensure_column(conn, "projects", "last_activity_type", "last_activity_type TEXT")
        _ensure_column(conn, "projects", "last_activity_desc", "last_activity_desc TEXT")
        _ensure_column(conn, "projects", "notes", "notes TEXT")

        _ensure_column(conn, "project_files", "line_count", "line_count INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "project_files", "file_type", "file_type TEXT NOT NULL DEFAULT 'source'")

        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_projects_game_id ON projects (game_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_projects_status ON projects (status)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_files_project_id ON project_files (project_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_glossaries_game_id ON glossaries (game_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_entries_glossary_id ON entries (glossary_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_activity_log_project_id ON activity_log (project_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_history_project_id ON project_history (project_id)")
        conn.commit()

def _migration_002_add_project_watches(db_path: str) -> None:
    path = db_path.replace("\\", "/")
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)

    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_watches (
                watch_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                project_id TEXT,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                scan_interval_minutes INTEGER,
                last_scan_at TEXT,
                last_change_at TEXT,
                status TEXT NOT NULL DEFAULT 'never_scanned',
                last_scan_summary JSON,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_watch_file_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                watch_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY(watch_id) REFERENCES project_watches(watch_id)
            )
            """
        )
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_watches_project_id ON project_watches (project_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_watches_status ON project_watches (status)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_watch_file_snapshots_watch_id ON project_watch_file_snapshots (watch_id)")
        _ensure_index(conn, "CREATE UNIQUE INDEX IF NOT EXISTS ux_project_watch_snapshot_path ON project_watch_file_snapshots (watch_id, relative_path)")
        conn.commit()

def _migration_003_add_project_glossary_bindings(db_path: str) -> None:
    path = db_path.replace("\\", "/")
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)

    now = datetime.datetime.now().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_glossary_bindings (
                project_id TEXT PRIMARY KEY,
                glossary_id INTEGER NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(project_id),
                FOREIGN KEY(glossary_id) REFERENCES glossaries(glossary_id)
            )
            """
        )
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_project_glossary_bindings_glossary_id ON project_glossary_bindings (glossary_id)")

        rows = conn.execute("SELECT glossary_id, raw_metadata FROM glossaries").fetchall()
        for row in rows:
            try:
                metadata = json.loads(row["raw_metadata"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            project_id = metadata.get("project_id")
            if not project_id:
                continue
            project_exists = conn.execute(
                "SELECT 1 FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not project_exists:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO project_glossary_bindings
                    (project_id, glossary_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, row["glossary_id"], now, now),
            )
        conn.commit()


def _migration_004_add_background_task_ledger(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS background_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'task',
                project_id TEXT,
                parent_task_id TEXT,
                created_by JSON NOT NULL DEFAULT '{}',
                title TEXT NOT NULL DEFAULT 'Background task',
                status TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT '',
                progress JSON NOT NULL DEFAULT '{}',
                created_at TEXT,
                started_at TEXT,
                updated_at TEXT,
                finished_at TEXT,
                message TEXT,
                attention_reason TEXT,
                checkpoint JSON NOT NULL DEFAULT '{}',
                result JSON NOT NULL DEFAULT '{}',
                blocking BOOLEAN NOT NULL DEFAULT 0,
                dedupe_key TEXT,
                idempotency_key TEXT,
                source_route TEXT NOT NULL DEFAULT '/',
                archived_at TEXT,
                payload JSON NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'info',
                event_type TEXT NOT NULL DEFAULT 'log',
                message TEXT NOT NULL,
                metadata JSON NOT NULL DEFAULT '{}',
                FOREIGN KEY(task_id) REFERENCES background_tasks(task_id) ON DELETE CASCADE,
                UNIQUE(task_id, sequence)
            )
            """
        )
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_background_tasks_status ON background_tasks (status)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_background_tasks_project_id ON background_tasks (project_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_background_tasks_parent_task_id ON background_tasks (parent_task_id)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_background_tasks_archived_at ON background_tasks (archived_at)")
        _ensure_index(conn, "CREATE INDEX IF NOT EXISTS ix_task_events_task_id_sequence ON task_events (task_id, sequence)")
        conn.commit()


MAIN_DB_MIGRATIONS: list[tuple[int, str, Callable[[str], None]]] = [
    (1, "establish_managed_main_schema", _migration_001_establish_managed_main_schema),
    (2, "add_project_watches", _migration_002_add_project_watches),
    (3, "add_project_glossary_bindings", _migration_003_add_project_glossary_bindings),
    (4, "add_background_task_ledger", _migration_004_add_background_task_ledger),
]


def migrate_main_database(db_path: str) -> int:
    with _connect(db_path) as conn:
        _ensure_migrations_table(conn)
        applied_versions = _applied_versions(conn)

    for version, name, migration in MAIN_DB_MIGRATIONS:
        if version in applied_versions:
            continue

        logger.info("[DB] Applying main DB migration %s: %s", version, name)
        migration(db_path)

        with _connect(db_path) as conn:
            _record_migration(conn, version, name)
            conn.commit()

    return MAIN_DB_TARGET_VERSION
