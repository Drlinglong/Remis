"""SQLite DDL for resumable Mod Context analysis batches."""

from __future__ import annotations

import sqlite3


CONTEXT_ANALYSIS_BATCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS context_analysis_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    project_id TEXT NOT NULL,
    source_snapshot_hash TEXT NOT NULL,
    analysis_scope_json JSON NOT NULL DEFAULT '{}',
    config_fingerprint TEXT NOT NULL,
    config_json JSON NOT NULL DEFAULT '{}',
    phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'aggregation', 'synthesis', 'publishing', 'complete')),
    status TEXT NOT NULL CHECK(status IN ('running', 'failed', 'complete')),
    publication_status TEXT NOT NULL DEFAULT 'not_published'
        CHECK(publication_status IN ('not_published', 'published')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS context_analysis_batches (
    batch_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'aggregation', 'synthesis')),
    batch_index INTEGER NOT NULL CHECK(batch_index >= 0),
    source_item_ids_json JSON NOT NULL DEFAULT '[]',
    payload_json JSON NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('succeeded', 'failed')),
    error_json JSON,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES context_analysis_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, phase, batch_index)
);

CREATE INDEX IF NOT EXISTS ix_context_analysis_runs_project
    ON context_analysis_runs(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_analysis_runs_resume
    ON context_analysis_runs(project_id, source_snapshot_hash, config_fingerprint, status);
CREATE INDEX IF NOT EXISTS ix_context_analysis_batches_run
    ON context_analysis_batches(run_id, phase, batch_index);
"""


def migrate_context_analysis_batch_storage(db_path: str) -> None:
    """Create formal SQLite storage for resumable extraction/review batches."""
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(CONTEXT_ANALYSIS_BATCH_SCHEMA)
        connection.commit()
    finally:
        connection.close()


def migrate_context_analysis_aggregation_phase(db_path: str) -> None:
    """Rebuild constrained tables so aggregation is a durable workflow phase."""

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript("""
        BEGIN IMMEDIATE;
        ALTER TABLE context_analysis_batches RENAME TO context_analysis_batches_v15;
        ALTER TABLE context_analysis_runs RENAME TO context_analysis_runs_v15;

        CREATE TABLE context_analysis_runs (
            run_id TEXT PRIMARY KEY, task_id TEXT, project_id TEXT NOT NULL,
            source_snapshot_hash TEXT NOT NULL, analysis_scope_json JSON NOT NULL DEFAULT '{}',
            config_fingerprint TEXT NOT NULL, config_json JSON NOT NULL DEFAULT '{}',
            phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'aggregation', 'publishing', 'complete')),
            status TEXT NOT NULL CHECK(status IN ('running', 'failed', 'complete')),
            publication_status TEXT NOT NULL DEFAULT 'not_published'
                CHECK(publication_status IN ('not_published', 'published')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(project_id)
        );
        INSERT INTO context_analysis_runs SELECT * FROM context_analysis_runs_v15;

        CREATE TABLE context_analysis_batches (
            batch_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
            phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'aggregation')),
            batch_index INTEGER NOT NULL CHECK(batch_index >= 0),
            source_item_ids_json JSON NOT NULL DEFAULT '[]',
            payload_json JSON NOT NULL DEFAULT '{}',
            status TEXT NOT NULL CHECK(status IN ('succeeded', 'failed')),
            error_json JSON, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES context_analysis_runs(run_id) ON DELETE CASCADE,
            UNIQUE(run_id, phase, batch_index)
        );
        INSERT INTO context_analysis_batches SELECT * FROM context_analysis_batches_v15;

        DROP TABLE context_analysis_batches_v15;
        DROP TABLE context_analysis_runs_v15;
        CREATE INDEX ix_context_analysis_runs_project
            ON context_analysis_runs(project_id, updated_at DESC);
        CREATE INDEX ix_context_analysis_runs_resume
            ON context_analysis_runs(project_id, source_snapshot_hash, config_fingerprint, status);
        CREATE INDEX ix_context_analysis_batches_run
            ON context_analysis_batches(run_id, phase, batch_index);
        """)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()


def migrate_context_analysis_synthesis_phase(db_path: str) -> None:
    """Add durable synthesis checkpoints without touching unrelated FK debt."""

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE context_analysis_runs_v20 (
            run_id TEXT PRIMARY KEY, task_id TEXT, project_id TEXT NOT NULL,
            source_snapshot_hash TEXT NOT NULL, analysis_scope_json JSON NOT NULL DEFAULT '{}',
            config_fingerprint TEXT NOT NULL, config_json JSON NOT NULL DEFAULT '{}',
            phase TEXT NOT NULL CHECK(phase IN (
                'extraction', 'review', 'aggregation', 'synthesis', 'publishing', 'complete'
            )),
            status TEXT NOT NULL CHECK(status IN ('running', 'failed', 'complete')),
            publication_status TEXT NOT NULL DEFAULT 'not_published'
                CHECK(publication_status IN ('not_published', 'published')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(project_id)
        );
        INSERT INTO context_analysis_runs_v20 SELECT * FROM context_analysis_runs;

        CREATE TABLE context_analysis_batches_v20 (
            batch_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
            phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'aggregation', 'synthesis')),
            batch_index INTEGER NOT NULL CHECK(batch_index >= 0),
            source_item_ids_json JSON NOT NULL DEFAULT '[]',
            payload_json JSON NOT NULL DEFAULT '{}',
            status TEXT NOT NULL CHECK(status IN ('succeeded', 'failed')),
            error_json JSON, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES context_analysis_runs_v20(run_id) ON DELETE CASCADE,
            UNIQUE(run_id, phase, batch_index)
        );
        INSERT INTO context_analysis_batches_v20 SELECT * FROM context_analysis_batches;

        DROP TABLE context_analysis_batches;
        DROP TABLE context_analysis_runs;
        ALTER TABLE context_analysis_runs_v20 RENAME TO context_analysis_runs;
        ALTER TABLE context_analysis_batches_v20 RENAME TO context_analysis_batches;
        CREATE INDEX ix_context_analysis_runs_project
            ON context_analysis_runs(project_id, updated_at DESC);
        CREATE INDEX ix_context_analysis_runs_resume
            ON context_analysis_runs(project_id, source_snapshot_hash, config_fingerprint, status);
        CREATE INDEX ix_context_analysis_batches_run
            ON context_analysis_batches(run_id, phase, batch_index);
        COMMIT;
        """)
        violations = [
            row for row in connection.execute("PRAGMA foreign_key_check").fetchall()
            if str(row[0]).startswith(("context_analysis", "context_release"))
        ]
        if violations:
            raise sqlite3.IntegrityError(
                f"context analysis synthesis migration found invalid foreign keys: {violations[:5]}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()
