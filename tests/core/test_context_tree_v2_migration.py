import sqlite3

import pytest

from scripts.core.context_tree_v2_migration import (
    CONTEXT_TREE_V2_SCHEMA_VERSION,
    migrate_context_tree_v2_storage,
)
from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database


V2_TABLES = {
    "context_tree_v2_trees",
    "context_tree_v2_fragments",
    "context_tree_v2_unit_routes",
    "context_tree_v2_stories",
    "context_tree_v2_groups",
    "context_tree_v2_fragment_edges",
    "context_tree_v2_unresolved_references",
    "context_tree_v2_drafts",
    "context_tree_v2_draft_overrides",
    "context_tree_v2_releases",
}


def _objects(connection: sqlite3.Connection, object_type: str) -> dict[str, str]:
    return dict(
        connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = ? AND name LIKE 'context_tree_v2_%'",
            (object_type,),
        ).fetchall()
    )


def _insert_tree(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO context_tree_v2_trees (
            tree_id, project_id, source_snapshot_hash, schema_version, prompt_version
        ) VALUES ('tree-1', 'project-1', 'snapshot-1', 'context-tree-v2', 'prompt-v2')
        """
    )


def test_migration_creates_v2_schema_and_is_idempotent(tmp_path):
    db_path = tmp_path / "context-tree-v2.sqlite"

    migrate_context_tree_v2_storage(str(db_path))
    with sqlite3.connect(db_path) as connection:
        tables_before = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes_before = _objects(connection, "index")
        triggers_before = _objects(connection, "trigger")
        assert V2_TABLES <= tables_before
        assert CONTEXT_TREE_V2_SCHEMA_VERSION == 1

        _insert_tree(connection)
        connection.execute(
            "INSERT INTO context_tree_v2_fragments (tree_id, fragment_id, summary) "
            "VALUES ('tree-1', 'fragment-1', 'A local event')"
        )

    migrate_context_tree_v2_storage(str(db_path))
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT summary FROM context_tree_v2_fragments WHERE tree_id = 'tree-1'"
        ).fetchone() == ("A local event",)
        assert _objects(connection, "index") == indexes_before
        assert _objects(connection, "trigger") == triggers_before


def test_global_migration_22_extends_a_database_that_already_recorded_v21(tmp_path):
    db_path = tmp_path / "context-tree-v2-old-v21.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations "
            "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (21, 'add_context_tree_v2_storage', 'earlier')"
        )
        connection.execute(
            """CREATE TABLE context_tree_v2_trees (
                tree_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                source_snapshot_hash TEXT NOT NULL, schema_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL, project_title TEXT,
                project_summary TEXT, entity_evidence_json JSON NOT NULL DEFAULT '[]',
                entity_digests_json JSON NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
            )"""
        )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(context_tree_v2_trees)"
            )
        }
        versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }
    assert {"candidates_json", "term_variants_json"} <= columns
    assert {21, 22} <= versions


def test_v2_schema_does_not_touch_existing_v10_release_objects(tmp_path):
    db_path = tmp_path / "context-tree-v2-v10.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE context_releases (release_id TEXT PRIMARY KEY, marker TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO context_releases VALUES ('release-1', 'v10-preserved')"
        )
        before_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'context_releases'"
        ).fetchone()[0]

    migrate_context_tree_v2_storage(str(db_path))

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'context_releases'"
        ).fetchone()[0] == before_sql
        assert connection.execute(
            "SELECT marker FROM context_releases WHERE release_id = 'release-1'"
        ).fetchone() == ("v10-preserved",)


def test_v2_relationships_keep_sibling_groups_unordered_and_edges_ordered(tmp_path):
    db_path = tmp_path / "context-tree-v2-relations.sqlite"
    migrate_context_tree_v2_storage(str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_tree(connection)
        connection.execute(
            """
            INSERT INTO context_tree_v2_unit_routes
                (tree_id, unit_id, route)
            VALUES ('tree-1', 'unit-1', 'narrative')
            """
        )
        connection.execute(
            """
            INSERT INTO context_tree_v2_fragments
                (tree_id, fragment_id, summary, unit_ids_json)
            VALUES ('tree-1', 'fragment-1', 'First', '["unit-1"]')
            """
        )
        connection.execute(
            """
            INSERT INTO context_tree_v2_fragments
                (tree_id, fragment_id, summary)
            VALUES ('tree-1', 'fragment-2', 'Second')
            """
        )
        connection.execute(
            """
            INSERT INTO context_tree_v2_stories (tree_id, story_id, title)
            VALUES ('tree-1', 'story-1', 'The story')
            """
        )
        connection.executemany(
            """
            INSERT INTO context_tree_v2_groups
                (tree_id, group_id, story_id, title)
            VALUES ('tree-1', ?, 'story-1', ?)
            """,
            [("group-a", "Branch A"), ("group-b", "Branch B")],
        )
        connection.executemany(
            """
            INSERT INTO context_tree_v2_fragment_edges
                (tree_id, group_id, fragment_id, position)
            VALUES ('tree-1', 'group-a', ?, ?)
            """,
            [("fragment-1", 0), ("fragment-2", 1)],
        )

        assert connection.execute(
            """
            SELECT fragment_id FROM context_tree_v2_fragment_edges
            WHERE tree_id = 'tree-1' AND group_id = 'group-a'
            ORDER BY position
            """
        ).fetchall() == [("fragment-1",), ("fragment-2",)]
        group_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(context_tree_v2_groups)"
            )
        }
        assert "position" not in group_columns
        assert "fragment_order" not in group_columns

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO context_tree_v2_fragment_edges
                    (tree_id, group_id, fragment_id, position)
                VALUES ('tree-1', 'group-a', 'fragment-1', 2)
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO context_tree_v2_fragment_edges
                    (tree_id, group_id, fragment_id, position)
                VALUES ('tree-1', 'group-b', 'fragment-2', 0)
                """
            )


def test_unresolved_references_and_draft_overrides_are_append_only(tmp_path):
    db_path = tmp_path / "context-tree-v2-drafts.sqlite"
    migrate_context_tree_v2_storage(str(db_path))

    with sqlite3.connect(db_path) as connection:
        _insert_tree(connection)
        connection.execute(
            """
            INSERT INTO context_tree_v2_unresolved_references
                (tree_id, unresolved_id, source_kind, source_id, reference_type,
                 reference_id, reason)
            VALUES ('tree-1', 'unresolved-1', 'unit', 'unit-2', 'fragment',
                    'fragment-missing', 'repair_failed')
            """
        )
        connection.execute(
            """
            INSERT INTO context_tree_v2_drafts
                (draft_id, tree_id, project_id)
            VALUES ('draft-1', 'tree-1', 'project-1')
            """
        )
        connection.execute(
            """
            INSERT INTO context_tree_v2_draft_overrides
                (draft_id, sequence, target_type, target_id, operation, value_json)
            VALUES ('draft-1', 0, 'group', 'group-a', 'reorder',
                    '{"fragment_order":["fragment-2","fragment-1"]}')
            """
        )
        assert connection.execute(
            "SELECT sequence FROM context_tree_v2_draft_overrides WHERE draft_id = 'draft-1'"
        ).fetchone() == (0,)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE context_tree_v2_draft_overrides SET note = 'rewritten'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM context_tree_v2_draft_overrides WHERE draft_id = 'draft-1'"
            )
