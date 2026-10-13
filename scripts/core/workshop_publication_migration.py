"""Persist immutable publication plans and globally serialized attempts."""
import sqlite3


def add_workshop_publication(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workshop_publication_plans (
                plan_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES steam_workshop_workspaces(workspace_id),
                fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workshop_publication_attempts (
                plan_id TEXT PRIMARY KEY REFERENCES workshop_publication_plans(plan_id),
                task_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN
                    ('running', 'succeeded', 'failed', 'unknown', 'legal_agreement_required', 'resolved')),
                result_json TEXT NOT NULL DEFAULT '{}',
                progress_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_workshop_publication_active
                ON workshop_publication_attempts(status) WHERE status = 'running';
            CREATE INDEX IF NOT EXISTS ix_workshop_publication_workspace
                ON workshop_publication_plans(workspace_id, created_at DESC);
        """)
