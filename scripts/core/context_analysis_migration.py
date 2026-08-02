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
    phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review', 'publishing', 'complete')),
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
    phase TEXT NOT NULL CHECK(phase IN ('extraction', 'review')),
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
