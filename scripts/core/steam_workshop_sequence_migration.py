"""SQLite migration for the Steam Workshop asset sequence invariant."""

from __future__ import annotations

import sqlite3


_TABLE_NAME = "steam_workshop_asset_versions"
_REBUILT_TABLE_NAME = "steam_workshop_asset_versions_v25"
_COLUMNS = (
    "version_id, workspace_id, sequence, asset_type, status, parent_version_id, "
    "sha256, metadata_json, source, created_at, description_bbcode, "
    "description_language, source_description, source_description_sha256, "
    "cover_file_ref, cover_mime_type, cover_width, cover_height, cover_canvas_json"
)


class InvalidSteamWorkshopSequenceError(RuntimeError):
    """Raised when legacy rows violate the positive sequence contract."""


def _has_positive_sequence_constraint(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_TABLE_NAME,),
    ).fetchone()
    if row is None:
        return False
    normalized = "".join(str(row[0] or "").lower().split())
    return "check(sequence>0)" in normalized


def enforce_steam_workshop_sequence_constraint(db_path: str) -> None:
    """Rebuild the version table so every managed DB enforces sequence > 0."""

    connection = sqlite3.connect(db_path)
    try:
        if _has_positive_sequence_constraint(connection):
            return
        invalid = connection.execute(
            f"SELECT version_id, sequence FROM {_TABLE_NAME} WHERE sequence <= 0 LIMIT 1"
        ).fetchone()
        if invalid is not None:
            raise InvalidSteamWorkshopSequenceError(
                "Cannot enforce positive Steam Workshop asset sequences: "
                f"version {invalid[0]!r} has sequence {invalid[1]!r}."
            )

        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            f"""
            CREATE TABLE {_REBUILT_TABLE_NAME} (
                version_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                sequence INTEGER NOT NULL
                    CONSTRAINT ck_steam_workshop_sequence_positive CHECK(sequence > 0),
                asset_type TEXT NOT NULL
                    CONSTRAINT ck_steam_workshop_asset_type
                    CHECK(asset_type IN ('cover', 'description')),
                status TEXT NOT NULL DEFAULT 'candidate'
                    CONSTRAINT ck_steam_workshop_asset_status
                    CHECK(status IN ('candidate', 'selected')),
                parent_version_id TEXT,
                sha256 TEXT NOT NULL,
                metadata_json JSON NOT NULL DEFAULT '{{}}',
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
            )
            """
        )
        connection.execute(
            f"INSERT INTO {_REBUILT_TABLE_NAME} ({_COLUMNS}) "
            f"SELECT {_COLUMNS} FROM {_TABLE_NAME}"
        )
        connection.execute(f"DROP TABLE {_TABLE_NAME}")
        connection.execute(
            f"ALTER TABLE {_REBUILT_TABLE_NAME} RENAME TO {_TABLE_NAME}"
        )
        connection.execute(
            """
            CREATE INDEX ix_steam_workshop_versions_workspace_type
            ON steam_workshop_asset_versions (workspace_id, asset_type, sequence DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX ix_steam_workshop_versions_status
            ON steam_workshop_asset_versions (status, created_at DESC)
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
