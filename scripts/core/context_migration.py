"""SQLite DDL for the traceable Mod Context persistence foundation."""

from __future__ import annotations

import sqlite3


CONTEXT_RELEASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS context_source_items (
    source_item_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    UNIQUE(project_id, source_type, source_ref, content_hash)
);

CREATE TABLE IF NOT EXISTS context_contributions (
    contribution_id TEXT PRIMARY KEY,
    source_item_id TEXT NOT NULL,
    contribution_type TEXT NOT NULL
        CHECK(contribution_type IN ('mention', 'fact', 'event', 'relationship')),
    subject_key TEXT NOT NULL,
    payload_json JSON NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL
        CHECK(provenance IN ('text_inferred', 'script_derived', 'user_confirmed')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(source_item_id) REFERENCES context_source_items(source_item_id)
);

CREATE TABLE IF NOT EXISTS context_aggregates (
    aggregate_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL CHECK(aggregate_type IN ('entity', 'event', 'project')),
    aggregate_key TEXT NOT NULL,
    payload_json JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    UNIQUE(project_id, aggregate_type, aggregate_key)
);

CREATE TABLE IF NOT EXISTS context_aggregate_contributions (
    aggregate_id TEXT NOT NULL,
    contribution_id TEXT NOT NULL,
    PRIMARY KEY(aggregate_id, contribution_id),
    FOREIGN KEY(aggregate_id) REFERENCES context_aggregates(aggregate_id),
    FOREIGN KEY(contribution_id) REFERENCES context_contributions(contribution_id)
);

CREATE TABLE IF NOT EXISTS context_releases (
    release_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_snapshot_hash TEXT NOT NULL,
    analysis_scope_json JSON NOT NULL DEFAULT '{}',
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    analysis_config_json JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    parent_release_id TEXT,
    upstream_version TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(parent_release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_aggregates (
    release_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL CHECK(aggregate_type IN ('entity', 'event', 'project')),
    aggregate_key TEXT NOT NULL,
    payload_json JSON NOT NULL DEFAULT '{}',
    contribution_ids_json JSON NOT NULL DEFAULT '[]',
    PRIMARY KEY(release_id, aggregate_id),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_syntheses (
    synthesis_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    context_key TEXT NOT NULL,
    content_json JSON NOT NULL DEFAULT '{}',
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id),
    UNIQUE(release_id, context_key)
);

CREATE TABLE IF NOT EXISTS context_release_delivery_memberships (
    release_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK(role IN ('primary_member', 'supporting_context', 'theme_related')),
    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    provenance TEXT NOT NULL
        CHECK(provenance IN ('text_inferred', 'script_derived', 'user_confirmed')),
    reasoning TEXT,
    PRIMARY KEY(release_id, aggregate_id, source_item_id),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id),
    FOREIGN KEY(source_item_id) REFERENCES context_source_items(source_item_id)
);

CREATE TABLE IF NOT EXISTS context_drafts (
    draft_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    base_release_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'published')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(base_release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_draft_overrides (
    draft_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    value_json JSON NOT NULL DEFAULT '{}',
    note TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(draft_id, target_key),
    FOREIGN KEY(draft_id) REFERENCES context_drafts(draft_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_release_overrides (
    release_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    value_json JSON NOT NULL DEFAULT '{}',
    note TEXT,
    PRIMARY KEY(release_id, target_key),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_seals (
    release_id TEXT PRIMARY KEY,
    sealed_at TEXT NOT NULL,
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE INDEX IF NOT EXISTS ix_context_source_items_project
    ON context_source_items(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_contributions_source
    ON context_contributions(source_item_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_aggregates_project
    ON context_aggregates(project_id, aggregate_type, aggregate_key);
CREATE INDEX IF NOT EXISTS ix_context_releases_project
    ON context_releases(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_release_delivery_source
    ON context_release_delivery_memberships(release_id, source_item_id);
CREATE INDEX IF NOT EXISTS ix_context_drafts_project_status
    ON context_drafts(project_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_release_seals_release
    ON context_release_seals(release_id);

CREATE TRIGGER IF NOT EXISTS trg_context_releases_no_update
BEFORE UPDATE ON context_releases
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_releases_no_delete
BEFORE DELETE ON context_releases
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_aggregates_no_insert_after_seal
BEFORE INSERT ON context_release_aggregates
WHEN EXISTS (
    SELECT 1 FROM context_release_seals
    WHERE release_id = NEW.release_id
)
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_aggregates_no_update
BEFORE UPDATE ON context_release_aggregates
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_aggregates_no_delete
BEFORE DELETE ON context_release_aggregates
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_syntheses_no_update
BEFORE UPDATE ON context_release_syntheses
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_syntheses_no_delete
BEFORE DELETE ON context_release_syntheses
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_syntheses_no_insert_after_seal
BEFORE INSERT ON context_release_syntheses
WHEN EXISTS (
    SELECT 1 FROM context_release_seals
    WHERE release_id = NEW.release_id
)
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_delivery_no_insert_after_seal
BEFORE INSERT ON context_release_delivery_memberships
WHEN EXISTS (
    SELECT 1 FROM context_release_seals
    WHERE release_id = NEW.release_id
)
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_delivery_no_update
BEFORE UPDATE ON context_release_delivery_memberships
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_delivery_no_delete
BEFORE DELETE ON context_release_delivery_memberships
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_overrides_no_update
BEFORE UPDATE ON context_release_overrides
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_overrides_no_delete
BEFORE DELETE ON context_release_overrides
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_overrides_no_insert_after_seal
BEFORE INSERT ON context_release_overrides
WHEN EXISTS (
    SELECT 1 FROM context_release_seals
    WHERE release_id = NEW.release_id
)
BEGIN
    SELECT RAISE(ABORT, 'published context releases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_seals_no_update
BEFORE UPDATE ON context_release_seals
BEGIN
    SELECT RAISE(ABORT, 'published context release seals are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_seals_no_delete
BEFORE DELETE ON context_release_seals
BEGIN
    SELECT RAISE(ABORT, 'published context release seals are immutable');
END;
"""


def migrate_context_release_storage(db_path: str) -> None:
    """Create the context storage schema and its immutability guards."""
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(CONTEXT_RELEASE_SCHEMA)
        connection.commit()
    finally:
        connection.close()
