"""Schema and compatibility backfill for immutable release manifests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace
from typing import Any

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.repositories.context_release_manifest_repository import (
    insert_release_manifest,
)
from scripts.schemas.context import (
    ContextReleaseFile,
    ContextReleaseLocalUnit,
    ContextReleaseManifest,
    ContextReleaseSourceItem,
)


RELEASE_MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS context_release_files (
    release_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    size INTEGER NOT NULL CHECK(size >= 0),
    PRIMARY KEY(release_id, relative_path),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_source_items (
    release_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    item_key TEXT,
    duplicate_key_ordinal INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_key_ordinal >= 0),
    source_order INTEGER CHECK(source_order IS NULL OR source_order >= 0),
    source_ref TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY(release_id, source_item_id),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_local_units (
    release_id TEXT NOT NULL,
    local_unit_id TEXT NOT NULL,
    unit_key TEXT NOT NULL,
    unit_order INTEGER NOT NULL CHECK(unit_order >= 0),
    PRIMARY KEY(release_id, local_unit_id),
    FOREIGN KEY(release_id) REFERENCES context_releases(release_id)
);

CREATE TABLE IF NOT EXISTS context_release_local_unit_members (
    release_id TEXT NOT NULL,
    local_unit_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    member_order INTEGER NOT NULL CHECK(member_order >= 0),
    PRIMARY KEY(release_id, local_unit_id, source_item_id),
    FOREIGN KEY(release_id, local_unit_id)
        REFERENCES context_release_local_units(release_id, local_unit_id),
    FOREIGN KEY(release_id, source_item_id)
        REFERENCES context_release_source_items(release_id, source_item_id)
);

CREATE INDEX IF NOT EXISTS ix_context_release_files_path
    ON context_release_files(release_id, relative_path);
CREATE INDEX IF NOT EXISTS ix_context_release_source_items_order
    ON context_release_source_items(release_id, relative_path, source_order);
CREATE INDEX IF NOT EXISTS ix_context_release_units_order
    ON context_release_local_units(release_id, unit_order);
CREATE INDEX IF NOT EXISTS ix_context_release_unit_members_source
    ON context_release_local_unit_members(release_id, source_item_id);

CREATE TRIGGER IF NOT EXISTS trg_context_release_files_no_update
BEFORE UPDATE ON context_release_files
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_files_no_delete
BEFORE DELETE ON context_release_files
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_source_items_no_update
BEFORE UPDATE ON context_release_source_items
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_source_items_no_delete
BEFORE DELETE ON context_release_source_items
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_local_units_no_update
BEFORE UPDATE ON context_release_local_units
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_local_units_no_delete
BEFORE DELETE ON context_release_local_units
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_unit_members_no_update
BEFORE UPDATE ON context_release_local_unit_members
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_context_release_unit_members_no_delete
BEFORE DELETE ON context_release_local_unit_members
BEGIN
    SELECT RAISE(ABORT, 'published context release manifests are immutable');
END;
"""


def _decode(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value) if value is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _revision_id(source_item_id: str, content_hash: str) -> str:
    material = f"{source_item_id}\x00{content_hash}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _source_candidates(connection: sqlite3.Connection, project_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT source_item_id, source_ref, content, content_hash, metadata_json, created_at
        FROM context_source_items
        WHERE project_id = ? ORDER BY created_at, source_item_id
        """,
        (project_id,),
    ).fetchall()


def _metadata(row: sqlite3.Row) -> dict[str, Any]:
    value = _decode(row["metadata_json"], {})
    return value if isinstance(value, dict) else {}


def _match_legacy_source(
    row: dict[str, Any], candidates: list[sqlite3.Row], release_hash: str,
) -> sqlite3.Row | None:
    expected_hash = str(row.get("source_sha256") or "")
    source_item_id = row.get("source_item_id")
    if source_item_id:
        by_id = [item for item in candidates if item["source_item_id"] == source_item_id]
        if by_id and (not expected_hash or by_id[0]["content_hash"] == expected_hash):
            return by_id[0]
    path = str(row.get("relative_path") or "")
    key = row.get("item_key")
    order = row.get("source_order")
    matches = []
    for candidate in candidates:
        metadata = _metadata(candidate)
        if metadata.get("relative_path") != path or metadata.get("item_key") != key:
            continue
        if order is not None and metadata.get("source_order") != order:
            continue
        matches.append(candidate)
    exact = [item for item in matches if expected_hash and item["content_hash"] == expected_hash]
    if exact:
        return exact[0]
    snapshot = [item for item in matches if _metadata(item).get("source_snapshot_hash") == release_hash]
    return snapshot[0] if snapshot else None


def _legacy_manifest(
    connection: sqlite3.Connection, release: sqlite3.Row,
) -> ContextReleaseManifest | None:
    config = _decode(release["analysis_config_json"], {})
    if not isinstance(config, dict) or not isinstance(config.get("source_items"), list):
        return None
    candidates = _source_candidates(connection, release["project_id"])
    source_items: list[ContextReleaseSourceItem] = []
    ordinals: dict[str | None, int] = {}
    for raw in config["source_items"]:
        if not isinstance(raw, dict):
            return None
        key = raw.get("item_key")
        ordinal = int(raw.get("duplicate_key_ordinal", ordinals.get(key, 0)))
        ordinals[key] = max(ordinals.get(key, 0), ordinal + 1)
        candidate = _match_legacy_source(raw, candidates, release["source_snapshot_hash"])
        if candidate is None:
            return None
        content_hash = str(candidate["content_hash"] or raw.get("source_sha256") or "legacy-unknown")
        source_items.append(
            ContextReleaseSourceItem(
                source_item_id=candidate["source_item_id"],
                source_revision_id=_revision_id(candidate["source_item_id"], content_hash),
                relative_path=str(raw.get("relative_path") or ""),
                item_key=key,
                duplicate_key_ordinal=ordinal,
                source_order=raw.get("source_order"),
                source_ref=candidate["source_ref"],
                content=candidate["content"],
                content_hash=content_hash,
            )
        )
    if not source_items:
        return None
    files_by_path = {
        item.relative_path: ContextReleaseFile(
            relative_path=item.relative_path,
            source_sha256="legacy-unknown",
            size=0,
        )
        for item in source_items
    }
    analysis_scope = _decode(release["analysis_scope_json"], {})
    if isinstance(analysis_scope, dict):
        for path in analysis_scope.get("files", []):
            if isinstance(path, str) and path:
                files_by_path.setdefault(
                    path,
                    ContextReleaseFile(
                        relative_path=path,
                        source_sha256="legacy-unknown",
                        size=0,
                    ),
                )
    unit_items = [
        SimpleNamespace(
            source_item_id=item.source_item_id,
            relative_path=item.relative_path,
            item_key=item.item_key,
            source_order=item.source_order,
        )
        for item in source_items
    ]
    local_units = ContextLocalUnitBuilder.build(unit_items)
    return ContextReleaseManifest(
        files=list(files_by_path.values()),
        source_items=source_items,
        local_units=[
            ContextReleaseLocalUnit(
                local_unit_id=unit.unit_id,
                unit_key=unit.unit_key,
                unit_order=index,
                source_item_ids=[item.source_item_id for item in unit.items],
            )
            for index, unit in enumerate(local_units)
        ],
    )


def _backfill_manifests(connection: sqlite3.Connection) -> None:
    releases = connection.execute(
        "SELECT * FROM context_releases ORDER BY created_at, release_id"
    ).fetchall()
    for release in releases:
        existing = connection.execute(
            "SELECT 1 FROM context_release_source_items WHERE release_id = ? LIMIT 1",
            (release["release_id"],),
        ).fetchone()
        if existing is not None:
            continue
        manifest = _legacy_manifest(connection, release)
        if manifest is not None:
            insert_release_manifest(connection, release["release_id"], manifest)


def migrate_context_release_manifest_storage(db_path: str) -> None:
    """Install release manifests and best-effort hydrate releases from v16 data."""

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(RELEASE_MANIFEST_SCHEMA)
        _backfill_manifests(connection)
        connection.commit()
    finally:
        connection.close()
