"""Shared SQLite and model helpers for the split v2 tree repository."""

from __future__ import annotations

import json
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scripts.schemas import context_tree_v2 as tree_schema


class ContextTreeV2NotFoundError(LookupError):
    """The requested v2 tree, draft, or related object does not exist."""


class ContextTreeV2OwnershipError(LookupError):
    """A v2 object belongs to another project or source snapshot."""


class ContextTreeV2DraftClosedError(RuntimeError):
    """A draft that is no longer open cannot receive edits."""


class ContextTreeV2ConflictError(RuntimeError):
    """An immutable v2 object conflicts with an existing row."""


class ContextTreeV2ValidationError(ValueError):
    """A draft edit or approval violates the v2 relationship contract."""

    def __init__(self, message: str, issues: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.issues = issues or []


class TreeV2StorageSupport:
    """Connection, serialization, and ownership primitives shared by readers/writers."""

    def __init__(self, db_path: str):
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
    def _json(value: Any) -> str:
        def normalize(item: Any) -> Any:
            dump = getattr(item, "model_dump", None)
            if callable(dump):
                return normalize(dump(mode="json"))
            if isinstance(item, Mapping):
                return {str(key): normalize(nested) for key, nested in item.items()}
            if isinstance(item, (list, tuple, set)):
                return [normalize(nested) for nested in item]
            return item

        return json.dumps(normalize(value), ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _decode(value: str | None, fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @staticmethod
    def _dump(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        dump = getattr(value, "model_dump", None)
        if callable(dump):
            return dict(dump(mode="json"))
        raise TypeError("Context tree values must be mappings or Pydantic models")

    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    @staticmethod
    def _model(names: tuple[str, ...], payload: dict[str, Any]) -> Any:
        for name in names:
            model = getattr(tree_schema, name, None)
            if model is not None:
                return model.model_validate(payload)
        return payload

    @staticmethod
    def _require_text(value: Any, label: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        return text

    @staticmethod
    def _find_project(connection: sqlite3.Connection, project_id: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone() is not None

    @staticmethod
    def _tree_key(payload: Mapping[str, Any]) -> tuple[str, str]:
        project_id = str(payload.get("project_id") or "").strip()
        snapshot = str(payload.get("tree_id") or payload.get("source_snapshot_hash") or "").strip()
        if not project_id or not snapshot:
            raise ValueError("project_id and source_snapshot_hash are required")
        return project_id, snapshot

    @staticmethod
    def _tree_row(connection: sqlite3.Connection, project_id: str, tree_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM context_tree_v2_trees
            WHERE project_id = ? AND tree_id = ?
            """,
            (project_id, tree_id),
        ).fetchone()
        if row is None:
            raise ContextTreeV2NotFoundError("Context tree v2 not found")
        return row

    @staticmethod
    def _draft_row(connection: sqlite3.Connection, draft_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM context_tree_v2_drafts WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            raise ContextTreeV2NotFoundError("Context tree v2 draft not found")
        return row

    @staticmethod
    def _check_draft_project(row: sqlite3.Row, project_id: str) -> None:
        if row["project_id"] != project_id:
            raise ContextTreeV2OwnershipError("Context tree v2 draft does not belong to this project")

    @staticmethod
    def _check_open_draft(row: sqlite3.Row) -> None:
        if row["status"] != "draft":
            raise ContextTreeV2DraftClosedError("Context tree v2 draft is not open")
