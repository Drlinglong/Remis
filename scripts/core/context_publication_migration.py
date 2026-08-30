"""SQLite migration for atomic context publication and immutable release seals."""

from __future__ import annotations

import sqlite3


_TRIGGER_NAMES = (
    "trg_context_releases_no_update",
    "trg_context_releases_no_delete",
    "trg_context_release_aggregates_no_insert_after_seal",
    "trg_context_release_aggregates_no_update",
    "trg_context_release_aggregates_no_delete",
    "trg_context_release_syntheses_no_insert_after_seal",
    "trg_context_release_syntheses_no_update",
    "trg_context_release_syntheses_no_delete",
    "trg_context_release_delivery_no_insert_after_seal",
    "trg_context_release_delivery_no_update",
    "trg_context_release_delivery_no_delete",
    "trg_context_release_overrides_no_insert_after_seal",
    "trg_context_release_overrides_no_update",
    "trg_context_release_overrides_no_delete",
    "trg_context_release_files_no_insert_after_seal",
    "trg_context_release_source_items_no_insert_after_seal",
    "trg_context_release_local_units_no_insert_after_seal",
    "trg_context_release_unit_members_no_insert_after_seal",
    "trg_context_release_seals_no_update",
    "trg_context_release_seals_no_delete",
)


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _drop_guards(connection: sqlite3.Connection) -> None:
    for trigger_name in _TRIGGER_NAMES:
        connection.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}"')


def _create_seal_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS context_release_seals (
            release_id TEXT PRIMARY KEY,
            sealed_at TEXT NOT NULL,
            FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
        )
        """
    )


def _create_immutable_trigger(
    connection: sqlite3.Connection,
    trigger_name: str,
    event: str,
    table_name: str,
    *,
    when: str | None = None,
    message: str = "published context releases are immutable",
) -> None:
    when_clause = f"WHEN {when}" if when else ""
    connection.execute(
        f"""
        CREATE TRIGGER {trigger_name}
        BEFORE {event} ON {table_name}
        {when_clause}
        BEGIN
            SELECT RAISE(ABORT, '{message}');
        END
        """
    )


def _create_guards(connection: sqlite3.Connection) -> None:
    _create_immutable_trigger(connection, "trg_context_releases_no_update", "UPDATE", "context_releases")
    _create_immutable_trigger(connection, "trg_context_releases_no_delete", "DELETE", "context_releases")
    for table_name, prefix in (
        ("context_release_aggregates", "aggregates"),
        ("context_release_syntheses", "syntheses"),
        ("context_release_delivery_memberships", "delivery"),
        ("context_release_overrides", "overrides"),
    ):
        _create_immutable_trigger(
            connection,
            f"trg_context_release_{prefix}_no_insert_after_seal",
            "INSERT",
            table_name,
            when=(
                "EXISTS (SELECT 1 FROM context_release_seals "
                "WHERE release_id = NEW.release_id)"
            ),
        )
        _create_immutable_trigger(
            connection,
            f"trg_context_release_{prefix}_no_update",
            "UPDATE",
            table_name,
        )
        _create_immutable_trigger(
            connection,
            f"trg_context_release_{prefix}_no_delete",
            "DELETE",
            table_name,
        )
    for table_name, prefix in (
        ("context_release_files", "files"),
        ("context_release_source_items", "source_items"),
        ("context_release_local_units", "local_units"),
        ("context_release_local_unit_members", "unit_members"),
    ):
        _create_immutable_trigger(
            connection,
            f"trg_context_release_{prefix}_no_insert_after_seal",
            "INSERT",
            table_name,
            when=(
                "EXISTS (SELECT 1 FROM context_release_seals "
                "WHERE release_id = NEW.release_id)"
            ),
        )
    for event in ("UPDATE", "DELETE"):
        _create_immutable_trigger(
            connection,
            f"trg_context_release_seals_no_{event.lower()}",
            event,
            "context_release_seals",
            message="published context release seals are immutable",
        )


def _rebuild_release_children(connection: sqlite3.Connection) -> None:
    connection.execute("DROP INDEX IF EXISTS ix_context_release_delivery_source")
    old_tables = (
        "context_release_syntheses",
        "context_release_delivery_memberships",
        "context_release_aggregates",
    )
    for table_name in old_tables:
        connection.execute(
            f"ALTER TABLE {table_name} RENAME TO {table_name}_v17"
        )

    connection.execute(
        """
        CREATE TABLE context_release_aggregates (
            release_id TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            aggregate_type TEXT NOT NULL CHECK(aggregate_type IN ('entity', 'event', 'project')),
            aggregate_key TEXT NOT NULL,
            payload_json JSON NOT NULL DEFAULT '{}',
            contribution_ids_json JSON NOT NULL DEFAULT '[]',
            PRIMARY KEY(release_id, aggregate_id),
            FOREIGN KEY(release_id) REFERENCES context_releases(release_id),
            FOREIGN KEY(aggregate_id) REFERENCES context_aggregates(aggregate_id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO context_release_aggregates (
            release_id, aggregate_id, aggregate_type, aggregate_key,
            payload_json, contribution_ids_json
        )
        SELECT release_id, aggregate_id, aggregate_type, aggregate_key,
               payload_json, contribution_ids_json
        FROM context_release_aggregates_v17
        """
    )
    connection.execute(
        """
        CREATE TABLE context_release_syntheses (
            synthesis_id TEXT PRIMARY KEY,
            release_id TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            context_key TEXT NOT NULL,
            content_json JSON NOT NULL DEFAULT '{}',
            FOREIGN KEY(release_id) REFERENCES context_releases(release_id),
            FOREIGN KEY(release_id, aggregate_id)
                REFERENCES context_release_aggregates(release_id, aggregate_id),
            UNIQUE(release_id, context_key)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO context_release_syntheses (
            synthesis_id, release_id, aggregate_id, context_key, content_json
        )
        SELECT synthesis_id, release_id, aggregate_id, context_key, content_json
        FROM context_release_syntheses_v17
        """
    )
    connection.execute(
        """
        CREATE TABLE context_release_delivery_memberships (
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
            FOREIGN KEY(release_id, aggregate_id)
                REFERENCES context_release_aggregates(release_id, aggregate_id),
            FOREIGN KEY(source_item_id) REFERENCES context_source_items(source_item_id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO context_release_delivery_memberships (
            release_id, aggregate_id, source_item_id, role,
            confidence, provenance, reasoning
        )
        SELECT release_id, aggregate_id, source_item_id, role,
               confidence, provenance, reasoning
        FROM context_release_delivery_memberships_v17
        """
    )
    connection.execute(
        "CREATE INDEX ix_context_release_delivery_source "
        "ON context_release_delivery_memberships(release_id, source_item_id)"
    )
    for table_name in old_tables:
        connection.execute(f"DROP TABLE {table_name}_v17")


def migrate_context_publication_storage(db_path: str) -> None:
    """Add run binding, composite child references, and immutable seals."""
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        _create_seal_table(connection)
        if "analysis_run_id" not in _column_names(connection, "context_releases"):
            connection.execute(
                "ALTER TABLE context_releases ADD COLUMN "
                "analysis_run_id TEXT REFERENCES context_analysis_runs(run_id)"
            )
        _drop_guards(connection)
        _rebuild_release_children(connection)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_context_releases_analysis_run_id "
            "ON context_releases(analysis_run_id) WHERE analysis_run_id IS NOT NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_context_release_seals_release "
            "ON context_release_seals(release_id)"
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO context_release_seals (release_id, sealed_at)
            SELECT release_id, created_at FROM context_releases
            """
        )
        _create_guards(connection)
        foreign_key_errors = [
            row
            for row in connection.execute("PRAGMA foreign_key_check").fetchall()
            if str(row[0]).startswith("context_release")
        ]
        if foreign_key_errors:
            raise sqlite3.IntegrityError(
                "context publication migration found invalid context foreign keys: "
                f"{foreign_key_errors}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()
