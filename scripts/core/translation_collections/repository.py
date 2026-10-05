"""Transactional collection records in the configured Remis project database.

Members are references, not project copies. Removing a collection never removes
projects, translation outputs or exported packages. Revision checks protect edits
from a second browser or Agent; export history retains the exact release snapshot.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid

from scripts.app_settings import PROJECTS_DB_PATH


class CollectionConflict(ValueError):
    """A stale revision cannot replace a newer collection."""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class CollectionRepository:
    def __init__(self, db_path: str = PROJECTS_DB_PATH):
        self.db_path = str(db_path)

    @contextmanager
    def connection(self):
        with sqlite3.connect(self.db_path, timeout=30) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("""CREATE TABLE IF NOT EXISTS translation_collections (
                collection_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                document TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS translation_collection_exports (
                plan_id TEXT PRIMARY KEY, collection_id TEXT NOT NULL,
                created_at TEXT NOT NULL, document TEXT NOT NULL)""")
            yield db

    def list(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT document FROM translation_collections ORDER BY rowid DESC")
            return [json.loads(row[0]) for row in rows]

    def get(self, collection_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT document FROM translation_collections WHERE collection_id=?",
                             (collection_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def create(self, data: dict) -> dict:
        identity = uuid.uuid4().hex
        now = timestamp()
        document = {**data, "collection_id": identity, "mod_id": "RemisCollection" + identity[:16],
                    "revision": 1, "steam_id": "", "last_export": None,
                    "created_at": now, "updated_at": now}
        with self.connection() as db:
            db.execute("INSERT INTO translation_collections VALUES (?, ?, ?)",
                       (identity, 1, encode(document)))
        return document

    def replace(self, collection_id: str, expected_revision: int, changes: dict) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT document FROM translation_collections WHERE collection_id=?",
                             (collection_id,)).fetchone()
            if not row:
                raise KeyError(collection_id)
            current = json.loads(row[0])
            if current["revision"] != expected_revision:
                raise CollectionConflict("Collection changed; reload before saving.")
            document = {**current, **changes, "revision": expected_revision + 1, "updated_at": timestamp()}
            db.execute("UPDATE translation_collections SET document=?, revision=? WHERE collection_id=?",
                       (encode(document), document["revision"], collection_id))
        return document

    def delete(self, collection_id: str, expected_revision: int) -> None:
        with self.connection() as db:
            cursor = db.execute("DELETE FROM translation_collections WHERE collection_id=? AND revision=?",
                                (collection_id, expected_revision))
            if not cursor.rowcount:
                raise CollectionConflict("Collection changed or was removed; reload before removing it.")

    def record_export(self, collection: dict, plan_id: str, result: dict) -> dict:
        receipt = {**result, "plan_id": plan_id, "collection_id": collection["collection_id"],
                   "collection_revision": collection["revision"], "snapshot": collection,
                   "created_at": timestamp()}
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO translation_collection_exports VALUES (?, ?, ?, ?)",
                       (plan_id, collection["collection_id"], receipt["created_at"], encode(receipt)))
            summary = {key: receipt[key] for key in
                       ("plan_id", "package_path", "created_at", "collection_revision", "mode")}
            updated = {**collection, "last_export": summary}
            cursor = db.execute("UPDATE translation_collections SET document=? WHERE collection_id=? AND revision=?",
                                (encode(updated), collection["collection_id"], collection["revision"]))
            if cursor.rowcount == 0:
                raise CollectionConflict("Collection changed or was removed during export; preview again.")
        return receipt

    def history(self, collection_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT document FROM translation_collection_exports WHERE collection_id=? "
                              "ORDER BY created_at DESC", (collection_id,))
            return [json.loads(row[0]) for row in rows]
