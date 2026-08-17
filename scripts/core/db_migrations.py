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
    SteamWorkshopAssetVersion,
    SteamWorkshopWorkspace,
)

logger = logging.getLogger("remis_init")

MAIN_DB_TARGET_VERSION = 13


class UnsupportedDatabaseVersionError(RuntimeError):
    """Raised when this Remis build encounters a newer managed schema."""


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
                paused_by_project_archive BOOLEAN NOT NULL DEFAULT 0,
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


def _migration_005_make_glossary_bindings_many_to_many(db_path: str) -> None:
    """Allow every project and glossary to participate in multiple bindings."""
    with _connect(db_path) as conn:
        # Migration DDL is committed before the version row is written by the
        # runner.  A restart after that boundary must therefore be safe.  In
        # particular, a process can leave the staging table behind while the
        # old table is still present.
        legacy_exists = _table_exists(conn, "project_glossary_bindings")
        staging_exists = _table_exists(conn, "project_glossary_bindings_v2")
        if not legacy_exists and not staging_exists:
            raise RuntimeError(
                "Migration 5 cannot find project_glossary_bindings or its staging table"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_glossary_bindings_v2 (
                project_id TEXT NOT NULL,
                glossary_id INTEGER NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY(project_id, glossary_id),
                FOREIGN KEY(project_id) REFERENCES projects(project_id),
                FOREIGN KEY(glossary_id) REFERENCES glossaries(glossary_id)
            )
            """
        )
        if legacy_exists:
            conn.execute(
                """
                INSERT OR IGNORE INTO project_glossary_bindings_v2
                    (project_id, glossary_id, created_at, updated_at)
                SELECT project_id, glossary_id, created_at, updated_at
                FROM project_glossary_bindings
                """
            )
            conn.execute("DROP TABLE project_glossary_bindings")
        conn.execute(
            "ALTER TABLE project_glossary_bindings_v2 RENAME TO project_glossary_bindings"
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_project_glossary_bindings_project_id "
            "ON project_glossary_bindings (project_id)",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_project_glossary_bindings_glossary_id "
            "ON project_glossary_bindings (glossary_id)",
        )
        conn.commit()


def _migration_006_index_task_summary_queries(db_path: str) -> None:
    """Keep task-center pagination and queue polling indexed as history grows."""
    with _connect(db_path) as conn:
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_background_tasks_archived_updated "
            "ON background_tasks (archived_at, updated_at DESC)",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_background_tasks_status_updated "
            "ON background_tasks (status, updated_at DESC)",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_background_tasks_created_at "
            "ON background_tasks (created_at DESC)",
        )
        conn.commit()


def _migration_007_govern_task_events_and_retention(db_path: str) -> None:
    """Add event visibility and indexes used by diagnostic and retention queries."""
    with _connect(db_path) as conn:
        _ensure_column(
            conn,
            "task_events",
            "audience",
            "audience TEXT NOT NULL DEFAULT 'user'",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_task_events_task_audience_sequence "
            "ON task_events (task_id, audience, sequence)",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_background_tasks_status_finished "
            "ON background_tasks (status, finished_at DESC)",
        )
        _ensure_index(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_background_tasks_idempotency_key "
            "ON background_tasks (idempotency_key)",
        )
        conn.commit()


def _migration_008_pause_archived_project_watches(db_path: str) -> None:
    """Remember which scheduled watches were paused by project archiving."""
    with _connect(db_path) as conn:
        _ensure_column(
            conn,
            "project_watches",
            "paused_by_project_archive",
            "paused_by_project_archive BOOLEAN NOT NULL DEFAULT 0",
        )
        conn.commit()


def _migration_009_add_model_arena_history(db_path: str) -> None:
    """Persist model-arena evidence independently from background task retention."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_arena_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT,
                project_name_snapshot TEXT NOT NULL,
                game_id TEXT NOT NULL,
                source_lang_code TEXT NOT NULL,
                target_lang_code TEXT NOT NULL,
                sample_seed TEXT NOT NULL,
                sampler_version TEXT NOT NULL,
                sample_size INTEGER NOT NULL CHECK(sample_size BETWEEN 3 AND 12),
                eligible_count INTEGER NOT NULL CHECK(eligible_count >= sample_size),
                status TEXT NOT NULL CHECK(status IN (
                    'draft', 'queued', 'running', 'voting', 'completed',
                    'partial_failed', 'failed', 'abandoned'
                )),
                settings_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS model_arena_contestants (
                contestant_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                execution_order INTEGER NOT NULL,
                config_snapshot_json TEXT NOT NULL,
                config_fingerprint TEXT NOT NULL,
                prompt_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0 CHECK(request_count >= 0),
                elapsed_ms INTEGER,
                failure_code TEXT,
                FOREIGN KEY(run_id) REFERENCES model_arena_runs(run_id) ON DELETE CASCADE,
                UNIQUE(run_id, provider_id, model_id),
                UNIQUE(run_id, execution_order)
            );

            CREATE TABLE IF NOT EXISTS model_arena_requests (
                request_id TEXT PRIMARY KEY,
                contestant_id TEXT NOT NULL,
                batch_ordinal INTEGER NOT NULL CHECK(batch_ordinal >= 0),
                system_instruction TEXT,
                prompt_text TEXT NOT NULL,
                effective_parameters_json TEXT NOT NULL,
                prompt_sha256 TEXT NOT NULL,
                completion_text_before_parse TEXT,
                completion_source TEXT NOT NULL,
                completion_sha256 TEXT,
                usage_json TEXT NOT NULL,
                parse_status TEXT NOT NULL,
                failure_code TEXT,
                elapsed_ms INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(contestant_id) REFERENCES model_arena_contestants(contestant_id) ON DELETE CASCADE,
                UNIQUE(contestant_id, batch_ordinal)
            );

            CREATE TABLE IF NOT EXISTS model_arena_samples (
                sample_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                entry_key TEXT NOT NULL,
                relative_file_path TEXT NOT NULL,
                line_number INTEGER,
                source_text TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                feature_tags_json TEXT NOT NULL,
                display_permutation_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES model_arena_runs(run_id) ON DELETE CASCADE,
                UNIQUE(run_id, ordinal)
            );

            CREATE TABLE IF NOT EXISTS model_arena_outputs (
                output_id TEXT PRIMARY KEY,
                sample_id TEXT NOT NULL,
                contestant_id TEXT NOT NULL,
                translated_text TEXT,
                response_sha256 TEXT,
                parse_status TEXT NOT NULL,
                hard_error_count INTEGER NOT NULL DEFAULT 0 CHECK(hard_error_count >= 0),
                validation_json TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES model_arena_samples(sample_id) ON DELETE CASCADE,
                FOREIGN KEY(contestant_id) REFERENCES model_arena_contestants(contestant_id) ON DELETE CASCADE,
                UNIQUE(sample_id, contestant_id)
            );

            CREATE TABLE IF NOT EXISTS model_arena_votes (
                vote_id TEXT PRIMARY KEY,
                sample_id TEXT NOT NULL UNIQUE,
                verdict TEXT NOT NULL CHECK(verdict IN (
                    'winner', 'tie', 'reject_all', 'unjudgeable'
                )),
                winner_output_id TEXT,
                reason_codes_json TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES model_arena_samples(sample_id) ON DELETE CASCADE,
                FOREIGN KEY(winner_output_id) REFERENCES model_arena_outputs(output_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS model_arena_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence > 0),
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                failure_code TEXT,
                metrics_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES model_arena_runs(run_id) ON DELETE CASCADE,
                UNIQUE(run_id, sequence)
            );

            CREATE INDEX IF NOT EXISTS ix_model_arena_runs_created_at
                ON model_arena_runs (created_at DESC);
            CREATE INDEX IF NOT EXISTS ix_model_arena_runs_project_created
                ON model_arena_runs (project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS ix_model_arena_runs_status_created
                ON model_arena_runs (status, created_at DESC);
            CREATE INDEX IF NOT EXISTS ix_model_arena_runs_language_pair
                ON model_arena_runs (source_lang_code, target_lang_code, created_at DESC);
            CREATE INDEX IF NOT EXISTS ix_model_arena_contestants_run
                ON model_arena_contestants (run_id, execution_order);
            CREATE INDEX IF NOT EXISTS ix_model_arena_requests_contestant
                ON model_arena_requests (contestant_id, batch_ordinal);
            CREATE INDEX IF NOT EXISTS ix_model_arena_samples_run
                ON model_arena_samples (run_id, ordinal);
            CREATE INDEX IF NOT EXISTS ix_model_arena_outputs_sample
                ON model_arena_outputs (sample_id);
            CREATE INDEX IF NOT EXISTS ix_model_arena_outputs_contestant
                ON model_arena_outputs (contestant_id);
            CREATE INDEX IF NOT EXISTS ix_model_arena_events_run_sequence
                ON model_arena_events (run_id, sequence);
            """
        )
def _migration_010_enforce_status_contracts(db_path: str) -> None:
    """Reject invalid workflow states at the SQLite boundary."""
    triggers = [
        (
            "trg_projects_status_insert",
            "projects",
            "INSERT",
            "NEW.status NOT IN ('active', 'archived', 'deleted')",
        ),
        (
            "trg_projects_status_update",
            "projects",
            "UPDATE OF status",
            "NEW.status NOT IN ('active', 'archived', 'deleted')",
        ),
        (
            "trg_project_files_status_insert",
            "project_files",
            "INSERT",
            "NEW.status NOT IN ('todo', 'in_progress', 'proofreading', 'paused', 'done')",
        ),
        (
            "trg_project_files_status_update",
            "project_files",
            "UPDATE OF status",
            "NEW.status NOT IN ('todo', 'in_progress', 'proofreading', 'paused', 'done')",
        ),
        (
            "trg_project_watches_status_insert",
            "project_watches",
            "INSERT",
            "NEW.status NOT IN ('never_scanned', 'baseline', 'clean', 'changed', 'no_localization', 'error')",
        ),
        (
            "trg_project_watches_status_update",
            "project_watches",
            "UPDATE OF status",
            "NEW.status NOT IN ('never_scanned', 'baseline', 'clean', 'changed', 'no_localization', 'error')",
        ),
    ]
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE project_files SET status = 'done' WHERE status = 'translated'"
        )
        for trigger_name, table_name, operation, predicate in triggers:
            conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {trigger_name}
                BEFORE {operation} ON {table_name}
                FOR EACH ROW WHEN {predicate}
                BEGIN
                    SELECT RAISE(ABORT, 'invalid {table_name}.status');
                END
                """
            )
        conn.commit()


def _migration_011_add_steam_workshop_assets(db_path: str) -> None:
    """Create project-optional Steam Workshop publication asset storage."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS steam_workshop_workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                game_id TEXT,
                project_id TEXT,
                workshop_item_id TEXT,
                current_cover_version_id TEXT,
                current_description_version_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );
            CREATE TABLE IF NOT EXISTS steam_workshop_asset_versions (
                version_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence > 0),
                asset_type TEXT NOT NULL CHECK(asset_type IN ('cover', 'description')),
                status TEXT NOT NULL DEFAULT 'candidate'
                    CHECK(status IN ('candidate', 'selected')),
                parent_version_id TEXT,
                sha256 TEXT NOT NULL,
                metadata_json JSON NOT NULL DEFAULT '{}',
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                description_bbcode TEXT,
                description_language TEXT,
                source_description TEXT,
                source_description_sha256 TEXT,
                cover_file_ref TEXT,
                cover_mime_type TEXT,
                cover_width INTEGER,
                cover_height INTEGER,
                cover_canvas_json JSON,
                FOREIGN KEY(workspace_id)
                    REFERENCES steam_workshop_workspaces(workspace_id),
                FOREIGN KEY(parent_version_id)
                    REFERENCES steam_workshop_asset_versions(version_id),
                UNIQUE(workspace_id, asset_type, sequence)
            );
            CREATE INDEX IF NOT EXISTS ix_steam_workshop_workspaces_project
                ON steam_workshop_workspaces (project_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS ix_steam_workshop_workspaces_game
                ON steam_workshop_workspaces (game_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS ix_steam_workshop_workspaces_item
                ON steam_workshop_workspaces (workshop_item_id);
            CREATE INDEX IF NOT EXISTS ix_steam_workshop_versions_workspace_type
                ON steam_workshop_asset_versions
                    (workspace_id, asset_type, sequence DESC);
            CREATE INDEX IF NOT EXISTS ix_steam_workshop_versions_status
                ON steam_workshop_asset_versions (status, created_at DESC);
            """
        )
        conn.commit()


def _migration_012_track_bundled_seed_state(db_path: str) -> None:
    """Record one-time bundled data hydration without overwriting later edits."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bundled_seed_state (
                seed_key TEXT PRIMARY KEY,
                seed_version INTEGER NOT NULL,
                applied_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied',
                last_error TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT
            )
            """
        )
        conn.commit()


def _migration_013_harden_bundled_seed_state(db_path: str) -> None:
    """Make bundled seed attempts observable and retryable on older DBs."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bundled_seed_state (
                seed_key TEXT PRIMARY KEY,
                seed_version INTEGER NOT NULL,
                applied_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied',
                last_error TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT
            )
            """
        )
        _ensure_column(
            conn,
            "bundled_seed_state",
            "status",
            "status TEXT NOT NULL DEFAULT 'applied'",
        )
        _ensure_column(
            conn,
            "bundled_seed_state",
            "last_error",
            "last_error TEXT",
        )
        _ensure_column(
            conn,
            "bundled_seed_state",
            "attempt_count",
            "attempt_count INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            conn,
            "bundled_seed_state",
            "last_attempt_at",
            "last_attempt_at TEXT",
        )
        conn.commit()


MAIN_DB_MIGRATIONS: list[tuple[int, str, Callable[[str], None]]] = [
    (1, "establish_managed_main_schema", _migration_001_establish_managed_main_schema),
    (2, "add_project_watches", _migration_002_add_project_watches),
    (3, "add_project_glossary_bindings", _migration_003_add_project_glossary_bindings),
    (4, "add_background_task_ledger", _migration_004_add_background_task_ledger),
    (5, "make_glossary_bindings_many_to_many", _migration_005_make_glossary_bindings_many_to_many),
    (6, "index_task_summary_queries", _migration_006_index_task_summary_queries),
    (7, "govern_task_events_and_retention", _migration_007_govern_task_events_and_retention),
    (8, "pause_archived_project_watches", _migration_008_pause_archived_project_watches),
    (9, "add_model_arena_history", _migration_009_add_model_arena_history),
    (10, "enforce_status_contracts", _migration_010_enforce_status_contracts),
    (11, "add_steam_workshop_assets", _migration_011_add_steam_workshop_assets),
    (12, "track_bundled_seed_state", _migration_012_track_bundled_seed_state),
    (13, "harden_bundled_seed_state", _migration_013_harden_bundled_seed_state),
]


def migrate_main_database(
    db_path: str,
    *,
    after_migration: Callable[[int, str], None] | None = None,
) -> int:
    """Apply managed migrations, with restart-safe per-migration commits.

    The legacy SQLModel migrations open their own SQLAlchemy connections, so a
    single transaction cannot cover both their DDL and the ledger write.  The
    runner consequently requires each migration to be restart-safe and offers
    a narrow post-DDL hook for crash-window regression tests.
    """
    with _connect(db_path) as conn:
        _ensure_migrations_table(conn)
        applied_versions = _applied_versions(conn)
        future_versions = sorted(
            version
            for version in applied_versions
            if version > MAIN_DB_TARGET_VERSION
        )
        if future_versions:
            raise UnsupportedDatabaseVersionError(
                "Database schema is newer than this Remis build "
                f"(found {future_versions[-1]}, supports {MAIN_DB_TARGET_VERSION})."
            )

    for version, name, migration in MAIN_DB_MIGRATIONS:
        if version in applied_versions:
            continue

        logger.info("[DB] Applying main DB migration %s: %s", version, name)
        migration(db_path)
        if after_migration is not None:
            after_migration(version, name)

        with _connect(db_path) as conn:
            _record_migration(conn, version, name)
            conn.commit()
        applied_versions.add(version)

    return MAIN_DB_TARGET_VERSION
