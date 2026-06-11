import datetime
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
    ProjectHistory,
    ProjectWatch,
    ProjectWatchFileSnapshot,
)

logger = logging.getLogger("remis_init")

MAIN_DB_TARGET_VERSION = 2


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
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


MAIN_DB_MIGRATIONS: list[tuple[int, str, Callable[[str], None]]] = [
    (1, "establish_managed_main_schema", _migration_001_establish_managed_main_schema),
    (2, "add_project_watches", _migration_002_add_project_watches),
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
