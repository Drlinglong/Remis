from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.app_settings import PROJECTS_DB_PATH


class SteamWorkshopRepository:
    """SQLite persistence for publication workspaces and immutable assets."""

    def __init__(self, db_path: str = PROJECTS_DB_PATH):
        self.db_path = str(Path(db_path))
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _decode_json(value: str | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return json.loads(value)

    @classmethod
    def _version_dict(cls, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = cls._decode_json(result.pop("metadata_json")) or {}
        result["canvas"] = cls._decode_json(result.pop("cover_canvas_json"))
        result["bbcode"] = result.pop("description_bbcode")
        result["language"] = result.pop("description_language")
        result["mime_type"] = result.pop("cover_mime_type")
        result["width"] = result.pop("cover_width")
        result["height"] = result.pop("cover_height")
        cover_file_ref = result.pop("cover_file_ref")
        if cover_file_ref:
            result["content_url"] = (
                f"/api/steam-workshop/versions/{result['version_id']}/content"
            )
        else:
            result["content_url"] = None
        return result

    def list_workspaces(self, project_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM steam_workshop_workspaces"
        params: tuple[Any, ...] = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (project_id,)
        query += " ORDER BY updated_at DESC, workspace_id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, params)]

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM steam_workshop_workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_workspace(self, data: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        workspace_id = str(uuid.uuid4())
        values = (
            workspace_id,
            data["name"],
            data.get("game_id"),
            data.get("project_id"),
            data.get("workshop_item_id"),
            now,
            now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO steam_workshop_workspaces (
                    workspace_id, name, game_id, project_id, workshop_item_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        return self.get_workspace(workspace_id)

    def update_workspace(
        self,
        workspace_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        allowed = {"name", "game_id", "project_id", "workshop_item_id"}
        updates = [(key, value) for key, value in data.items() if key in allowed]
        if not updates:
            return self.get_workspace(workspace_id)
        assignments = ", ".join(f"{key} = ?" for key, _ in updates)
        params = [value for _, value in updates]
        params.extend([self._now(), workspace_id])
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE steam_workshop_workspaces "
                f"SET {assignments}, updated_at = ? WHERE workspace_id = ?",
                params,
            )
        return self.get_workspace(workspace_id) if cursor.rowcount else None

    def delete_empty_workspace(self, workspace_id: str) -> bool:
        with self._connect() as connection:
            version = connection.execute(
                "SELECT 1 FROM steam_workshop_asset_versions "
                "WHERE workspace_id = ? LIMIT 1",
                (workspace_id,),
            ).fetchone()
            if version:
                raise ValueError("Workspace with asset versions cannot be deleted")
            cursor = connection.execute(
                "DELETE FROM steam_workshop_workspaces WHERE workspace_id = ?",
                (workspace_id,),
            )
        return bool(cursor.rowcount)

    def create_version(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM steam_workshop_asset_versions
                WHERE workspace_id = ? AND asset_type = ?
                """,
                (data["workspace_id"], data["asset_type"]),
            ).fetchone()
            version_id = data.get("version_id") or str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO steam_workshop_asset_versions (
                    version_id, workspace_id, sequence, asset_type, status,
                    parent_version_id, sha256, metadata_json, source, created_at,
                    description_bbcode, description_language,
                    source_description, source_description_sha256,
                    cover_file_ref, cover_mime_type, cover_width, cover_height,
                    cover_canvas_json
                ) VALUES (?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    data["workspace_id"],
                    row["next_sequence"],
                    data["asset_type"],
                    data.get("parent_version_id"),
                    data["sha256"],
                    json.dumps(data.get("metadata", {}), ensure_ascii=False),
                    data["source"],
                    self._now(),
                    data.get("bbcode"),
                    data.get("language"),
                    data.get("source_description"),
                    data.get("source_description_sha256"),
                    data.get("cover_file_ref"),
                    data.get("mime_type"),
                    data.get("width"),
                    data.get("height"),
                    json.dumps(data["canvas"], ensure_ascii=False)
                    if data.get("canvas") is not None
                    else None,
                ),
            )
            connection.execute(
                "UPDATE steam_workshop_workspaces SET updated_at = ? "
                "WHERE workspace_id = ?",
                (self._now(), data["workspace_id"]),
            )
        return self.get_version(version_id)

    def list_versions(
        self,
        workspace_id: str,
        asset_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM steam_workshop_asset_versions "
            "WHERE workspace_id = ?"
        )
        params: tuple[Any, ...] = (workspace_id,)
        if asset_type:
            query += " AND asset_type = ?"
            params = (workspace_id, asset_type)
        query += " ORDER BY asset_type, sequence DESC"
        with self._connect() as connection:
            return [
                self._version_dict(row)
                for row in connection.execute(query, params)
            ]

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM steam_workshop_asset_versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
        return self._version_dict(row) if row else None

    def get_cover_file_ref(self, version_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cover_file_ref FROM steam_workshop_asset_versions "
                "WHERE version_id = ?",
                (version_id,),
            ).fetchone()
        return row["cover_file_ref"] if row else None

    def select_version(
        self,
        workspace_id: str,
        asset_type: str,
        version_id: str,
    ) -> dict[str, Any]:
        pointer = (
            "current_cover_version_id"
            if asset_type == "cover"
            else "current_description_version_id"
        )
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            target = connection.execute(
                """
                SELECT version_id FROM steam_workshop_asset_versions
                WHERE version_id = ? AND workspace_id = ? AND asset_type = ?
                """,
                (version_id, workspace_id, asset_type),
            ).fetchone()
            if not target:
                raise ValueError("Version does not belong to this workspace and asset type")
            connection.execute(
                "UPDATE steam_workshop_asset_versions SET status = 'candidate' "
                "WHERE workspace_id = ? AND asset_type = ?",
                (workspace_id, asset_type),
            )
            connection.execute(
                "UPDATE steam_workshop_asset_versions SET status = 'selected' "
                "WHERE version_id = ?",
                (version_id,),
            )
            connection.execute(
                f"UPDATE steam_workshop_workspaces SET {pointer} = ?, updated_at = ? "
                "WHERE workspace_id = ?",
                (version_id, self._now(), workspace_id),
            )
        return self.get_version(version_id)
