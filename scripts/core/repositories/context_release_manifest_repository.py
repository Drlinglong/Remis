"""Persistence helpers for immutable Context Release source/unit manifests."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from scripts.schemas.context import (
    ContextReleaseFile,
    ContextReleaseLocalUnit,
    ContextReleaseManifest,
    ContextReleaseSourceItem,
    ContextSourceItem,
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def upsert_source_item(
    connection: sqlite3.Connection, item: ContextSourceItem,
) -> None:
    """Persist the latest project view; release rows retain historical content."""

    connection.execute(
        """
        INSERT INTO context_source_items (
            source_item_id, project_id, source_type, source_ref, content,
            content_hash, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_item_id) DO UPDATE SET
            project_id = excluded.project_id,
            source_type = excluded.source_type,
            source_ref = excluded.source_ref,
            content = excluded.content,
            content_hash = excluded.content_hash,
            metadata_json = excluded.metadata_json
        """,
        (
            item.source_item_id,
            item.project_id,
            item.source_type,
            item.source_ref,
            item.content,
            item.content_hash,
            _json(item.metadata),
            item.created_at,
        ),
    )


def insert_release_manifest(
    connection: sqlite3.Connection,
    release_id: str,
    manifest: ContextReleaseManifest,
) -> None:
    """Insert the complete immutable manifest inside the release transaction."""

    source_items = list(manifest.source_items)
    source_ids = [item.source_item_id for item in source_items]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Release source item identities must be unique")
    unit_ids = [unit.local_unit_id for unit in manifest.local_units]
    if len(unit_ids) != len(set(unit_ids)):
        raise ValueError("Release local unit identities must be unique")
    source_id_set = set(source_ids)
    for unit in manifest.local_units:
        if not set(unit.source_item_ids).issubset(source_id_set):
            raise ValueError("Release local unit references an unknown source item")

    connection.executemany(
        """
        INSERT INTO context_release_files
            (release_id, relative_path, source_sha256, size)
        VALUES (?, ?, ?, ?)
        """,
        [
            (release_id, item.relative_path, item.source_sha256, item.size)
            for item in manifest.files
        ],
    )
    connection.executemany(
        """
        INSERT INTO context_release_source_items (
            release_id, source_item_id, source_revision_id, relative_path, item_key,
            duplicate_key_ordinal, source_order, source_ref, content, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                release_id,
                item.source_item_id,
                item.source_revision_id,
                item.relative_path,
                item.item_key,
                item.duplicate_key_ordinal,
                item.source_order,
                item.source_ref,
                item.content,
                item.content_hash,
            )
            for item in source_items
        ],
    )
    connection.executemany(
        """
        INSERT INTO context_release_local_units
            (release_id, local_unit_id, unit_key, unit_order)
        VALUES (?, ?, ?, ?)
        """,
        [
            (release_id, unit.local_unit_id, unit.unit_key, unit.unit_order)
            for unit in manifest.local_units
        ],
    )
    connection.executemany(
        """
        INSERT INTO context_release_local_unit_members
            (release_id, local_unit_id, source_item_id, member_order)
        VALUES (?, ?, ?, ?)
        """,
        [
            (release_id, unit.local_unit_id, source_item_id, member_order)
            for unit in manifest.local_units
            for member_order, source_item_id in enumerate(unit.source_item_ids)
        ],
    )


def validate_release_manifest(
    connection: sqlite3.Connection,
    manifest: ContextReleaseManifest,
    project_id: str,
) -> None:
    """Ensure source identities in a manifest belong to the publishing project."""

    source_ids = [item.source_item_id for item in manifest.source_items]
    if not source_ids:
        return
    placeholders = ", ".join("?" for _ in source_ids)
    rows = connection.execute(
        f"SELECT source_item_id, project_id FROM context_source_items "
        f"WHERE source_item_id IN ({placeholders})",
        source_ids,
    ).fetchall()
    if len(rows) != len(source_ids) or any(row["project_id"] != project_id for row in rows):
        raise ValueError("Release manifest references source items outside the project")


def load_release_manifest(
    connection: sqlite3.Connection,
    release_id: str,
) -> ContextReleaseManifest | None:
    """Load an immutable manifest without consulting project-level source rows."""

    file_rows = connection.execute(
        """
        SELECT relative_path, source_sha256, size
        FROM context_release_files
        WHERE release_id = ? ORDER BY relative_path
        """,
        (release_id,),
    ).fetchall()
    source_rows = connection.execute(
        """
        SELECT source_item_id, source_revision_id, relative_path, item_key,
               duplicate_key_ordinal, source_order, source_ref, content, content_hash
        FROM context_release_source_items
        WHERE release_id = ?
        ORDER BY relative_path, source_order, source_item_id
        """,
        (release_id,),
    ).fetchall()
    unit_rows = connection.execute(
        """
        SELECT local_unit_id, unit_key, unit_order
        FROM context_release_local_units
        WHERE release_id = ? ORDER BY unit_order, local_unit_id
        """,
        (release_id,),
    ).fetchall()
    member_rows = connection.execute(
        """
        SELECT local_unit_id, source_item_id
        FROM context_release_local_unit_members
        WHERE release_id = ? ORDER BY local_unit_id, member_order
        """,
        (release_id,),
    ).fetchall()
    if not file_rows and not source_rows and not unit_rows:
        return None
    members: dict[str, list[str]] = defaultdict(list)
    for row in member_rows:
        members[row["local_unit_id"]].append(row["source_item_id"])
    return ContextReleaseManifest(
        files=[ContextReleaseFile(**dict(row)) for row in file_rows],
        source_items=[ContextReleaseSourceItem(**dict(row)) for row in source_rows],
        local_units=[
            ContextReleaseLocalUnit(
                **dict(row),
                source_item_ids=members.get(row["local_unit_id"], []),
            )
            for row in unit_rows
        ],
    )


def load_release_source_item(
    connection: sqlite3.Connection,
    release_id: str,
    source_item_id: str,
) -> sqlite3.Row | None:
    """Return one release-owned source row for traceability joins."""

    return connection.execute(
        """
        SELECT source_item_id, relative_path, item_key, duplicate_key_ordinal,
               source_order, source_ref, content, content_hash, source_revision_id
        FROM context_release_source_items
        WHERE release_id = ? AND source_item_id = ?
        """,
        (release_id, source_item_id),
    ).fetchone()


def release_source_item_as_context_source(
    row: sqlite3.Row, project_id: str, created_at: str,
) -> ContextSourceItem:
    """Adapt a release-owned row for existing traceability contracts."""

    return ContextSourceItem(
        source_item_id=row["source_item_id"],
        project_id=project_id,
        source_type="localization",
        source_ref=row["source_ref"],
        content=row["content"],
        content_hash=row["content_hash"],
        metadata={
            "relative_path": row["relative_path"],
            "item_key": row["item_key"],
            "source_order": row["source_order"],
            "duplicate_key_ordinal": row["duplicate_key_ordinal"],
            "source_revision_id": row["source_revision_id"],
        },
        created_at=created_at,
    )


def load_release_traceability_source(
    connection: sqlite3.Connection,
    release_id: str,
    source_item_id: str,
) -> ContextSourceItem | None:
    """Resolve release-owned evidence before falling back to the project view."""

    release = connection.execute(
        "SELECT project_id, created_at FROM context_releases WHERE release_id = ?",
        (release_id,),
    ).fetchone()
    release_source = load_release_source_item(connection, release_id, source_item_id)
    if release_source is not None and release is not None:
        return release_source_item_as_context_source(
            release_source, release["project_id"], release["created_at"]
        )
    source = connection.execute(
        "SELECT * FROM context_source_items WHERE source_item_id = ?",
        (source_item_id,),
    ).fetchone()
    if source is None:
        return None
    metadata = json.loads(source["metadata_json"] or "{}")
    return ContextSourceItem(
        source_item_id=source["source_item_id"],
        project_id=source["project_id"],
        source_type=source["source_type"],
        source_ref=source["source_ref"],
        content=source["content"],
        content_hash=source["content_hash"],
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=source["created_at"],
    )
