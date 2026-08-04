"""SQLite storage for the independent context archive tree v2 workflow.

The v2 tables deliberately live beside, rather than inside, the frozen v10
release schema.  This migration only creates v2 objects; it does not copy,
alter, or otherwise inspect historical ``context_*`` release rows.
"""

from __future__ import annotations

import sqlite3


CONTEXT_TREE_V2_SCHEMA_VERSION = 1
"""Version of the standalone context tree v2 storage schema."""

CONTEXT_TREE_V2_STORAGE_VERSION = CONTEXT_TREE_V2_SCHEMA_VERSION
"""Alias suitable for callers that register storage versions by name."""

CONTEXT_TREE_V2_MIGRATION_NAME = "context_tree_v2_storage"


CONTEXT_TREE_V2_SCHEMA = """
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS context_tree_v2_trees (
    tree_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_snapshot_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    project_title TEXT,
    project_summary TEXT,
    entity_evidence_json JSON NOT NULL DEFAULT '[]',
    entity_digests_json JSON NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tree_id, project_id)
);

CREATE TABLE IF NOT EXISTS context_tree_v2_fragments (
    tree_id TEXT NOT NULL,
    fragment_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    unit_ids_json JSON NOT NULL DEFAULT '[]',
    continuation_clues_json JSON NOT NULL DEFAULT '[]',
    boundary_json JSON NOT NULL DEFAULT '{}',
    source_evidence_json JSON NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, fragment_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_unit_routes (
    tree_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    route TEXT NOT NULL
        CHECK(route IN ('narrative', 'reference_asset', 'no_context')),
    route_reason TEXT,
    entity_summary_json JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, unit_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_stories (
    tree_id TEXT NOT NULL,
    story_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, story_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_groups (
    tree_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    story_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    -- Presentation-only ordering is not event chronology; sibling groups
    -- remain semantically unordered.  Fragment position is the only order.
    display_order INTEGER CHECK(display_order IS NULL OR display_order >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, group_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE,
    FOREIGN KEY(tree_id, story_id)
        REFERENCES context_tree_v2_stories(tree_id, story_id)
);

CREATE TABLE IF NOT EXISTS context_tree_v2_fragment_edges (
    tree_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    fragment_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    -- Optional public-contract identity; the scoped composite key is the
    -- storage identity used by the repository.
    edge_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, group_id, fragment_id),
    UNIQUE(tree_id, group_id, position),
    UNIQUE(tree_id, fragment_id),
    FOREIGN KEY(tree_id, group_id)
        REFERENCES context_tree_v2_groups(tree_id, group_id) ON DELETE CASCADE,
    FOREIGN KEY(tree_id, fragment_id)
        REFERENCES context_tree_v2_fragments(tree_id, fragment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_unresolved_references (
    tree_id TEXT NOT NULL,
    unresolved_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    reference_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    original_reference_json JSON NOT NULL DEFAULT '{}',
    repair_attempts INTEGER NOT NULL DEFAULT 0
        CHECK(repair_attempts >= 0 AND repair_attempts <= 1),
    repair_detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tree_id, unresolved_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_drafts (
    draft_id TEXT PRIMARY KEY,
    tree_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft', 'published')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(draft_id, tree_id, project_id),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_draft_overrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence >= 0),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    value_json JSON NOT NULL DEFAULT '{}',
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(draft_id, sequence),
    FOREIGN KEY(draft_id)
        REFERENCES context_tree_v2_drafts(draft_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_tree_v2_releases (
    release_id TEXT PRIMARY KEY,
    tree_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    idempotency_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(draft_id),
    UNIQUE(idempotency_key),
    FOREIGN KEY(tree_id)
        REFERENCES context_tree_v2_trees(tree_id),
    FOREIGN KEY(draft_id)
        REFERENCES context_tree_v2_drafts(draft_id)
);

CREATE INDEX IF NOT EXISTS ix_context_tree_v2_trees_project
    ON context_tree_v2_trees(project_id, source_snapshot_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_fragments_tree
    ON context_tree_v2_fragments(tree_id, fragment_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_unit_routes_tree
    ON context_tree_v2_unit_routes(tree_id, unit_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_stories_tree
    ON context_tree_v2_stories(tree_id, story_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_groups_story
    ON context_tree_v2_groups(tree_id, story_id, group_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_fragment_edges_order
    ON context_tree_v2_fragment_edges(tree_id, group_id, position, fragment_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_unresolved_tree
    ON context_tree_v2_unresolved_references(tree_id, reference_type, reference_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_drafts_project
    ON context_tree_v2_drafts(project_id, tree_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_draft_overrides_order
    ON context_tree_v2_draft_overrides(draft_id, sequence, override_id);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_releases_project
    ON context_tree_v2_releases(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_tree_v2_releases_idempotency
    ON context_tree_v2_releases(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Overrides are the draft's append-only audit log.  A new operation records
-- a correction; existing relationship history is never rewritten.
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_draft_overrides_no_update
BEFORE UPDATE ON context_tree_v2_draft_overrides
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 draft overrides are append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_draft_overrides_no_delete
BEFORE DELETE ON context_tree_v2_draft_overrides
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 draft overrides are append-only');
END;

-- Source and model-analysis rows are immutable.  Relationship edits are
-- represented only by draft overrides, so a tree read can always recover the
-- original evidence snapshot.
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_trees_no_update
BEFORE UPDATE ON context_tree_v2_trees
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 trees are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_fragments_no_update
BEFORE UPDATE ON context_tree_v2_fragments
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 fragments are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_routes_no_update
BEFORE UPDATE ON context_tree_v2_unit_routes
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 routes are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_stories_no_update
BEFORE UPDATE ON context_tree_v2_stories
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 stories are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_groups_no_update
BEFORE UPDATE ON context_tree_v2_groups
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 groups are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_edges_no_update
BEFORE UPDATE ON context_tree_v2_fragment_edges
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 fragment edges are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_unresolved_no_update
BEFORE UPDATE ON context_tree_v2_unresolved_references
BEGIN
    SELECT RAISE(ABORT, 'context tree v2 unresolved references are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_trees_no_delete
BEFORE DELETE ON context_tree_v2_trees
BEGIN SELECT RAISE(ABORT, 'context tree v2 trees are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_fragments_no_delete
BEFORE DELETE ON context_tree_v2_fragments
BEGIN SELECT RAISE(ABORT, 'context tree v2 fragments are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_routes_no_delete
BEFORE DELETE ON context_tree_v2_unit_routes
BEGIN SELECT RAISE(ABORT, 'context tree v2 routes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_stories_no_delete
BEFORE DELETE ON context_tree_v2_stories
BEGIN SELECT RAISE(ABORT, 'context tree v2 stories are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_groups_no_delete
BEFORE DELETE ON context_tree_v2_groups
BEGIN SELECT RAISE(ABORT, 'context tree v2 groups are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_edges_no_delete
BEFORE DELETE ON context_tree_v2_fragment_edges
BEGIN SELECT RAISE(ABORT, 'context tree v2 fragment edges are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_context_tree_v2_unresolved_no_delete
BEFORE DELETE ON context_tree_v2_unresolved_references
BEGIN SELECT RAISE(ABORT, 'context tree v2 unresolved references are immutable'); END;

COMMIT;
"""


def migrate_context_tree_v2_storage(db_path: str) -> None:
    """Create the restart-safe, standalone context tree v2 schema."""

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(CONTEXT_TREE_V2_SCHEMA)
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(context_tree_v2_trees)")
        }
        if "entity_evidence_json" not in columns:
            connection.execute(
                "ALTER TABLE context_tree_v2_trees ADD COLUMN "
                "entity_evidence_json JSON NOT NULL DEFAULT '[]'"
            )
        if "project_summary" not in columns:
            connection.execute(
                "ALTER TABLE context_tree_v2_trees ADD COLUMN project_summary TEXT"
            )
        if "entity_digests_json" not in columns:
            connection.execute(
                "ALTER TABLE context_tree_v2_trees ADD COLUMN "
                "entity_digests_json JSON NOT NULL DEFAULT '[]'"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


__all__ = [
    "CONTEXT_TREE_V2_MIGRATION_NAME",
    "CONTEXT_TREE_V2_SCHEMA",
    "CONTEXT_TREE_V2_SCHEMA_VERSION",
    "CONTEXT_TREE_V2_STORAGE_VERSION",
    "migrate_context_tree_v2_storage",
]
