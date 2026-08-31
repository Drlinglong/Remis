"""Schema migration for durable task idempotency ownership."""

from __future__ import annotations

import json
import sqlite3


def _decode_task_payload(payload: str | None) -> dict | None:
    """Decode a task payload without replacing malformed legacy data."""
    try:
        decoded = json.loads(payload or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def add_task_idempotency_uniqueness(db_path: str) -> None:
    """Make non-empty task keys unique across database connections.

    Older ledgers only had a lookup index and can therefore contain duplicate
    keys. Keep the newest row (the repository uses the same ordering) and clear
    older duplicate keys before creating the unique index. NULL and blank
    legacy values intentionally do not participate in the constraint.
    """
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT task_id, idempotency_key, updated_at, created_at, payload
            FROM background_tasks
            WHERE idempotency_key IS NOT NULL
              AND TRIM(idempotency_key) <> ''
            ORDER BY TRIM(idempotency_key), updated_at DESC,
                     created_at DESC, task_id DESC
            """
        ).fetchall()
        seen_keys: set[str] = set()
        for row in rows:
            key = str(row["idempotency_key"]).strip()
            if key in seen_keys:
                payload = _decode_task_payload(row["payload"])
                if payload is None:
                    connection.execute(
                        "UPDATE background_tasks SET idempotency_key = NULL WHERE task_id = ?",
                        (row["task_id"],),
                    )
                else:
                    payload.pop("idempotency_key", None)
                    connection.execute(
                        """
                        UPDATE background_tasks
                        SET idempotency_key = NULL, payload = ?
                        WHERE task_id = ?
                        """,
                        (json.dumps(payload, ensure_ascii=False), row["task_id"]),
                    )
                continue
            seen_keys.add(key)

            if key != row["idempotency_key"]:
                payload = _decode_task_payload(row["payload"])
                if payload is None:
                    connection.execute(
                        "UPDATE background_tasks SET idempotency_key = ? WHERE task_id = ?",
                        (key, row["task_id"]),
                    )
                else:
                    payload["idempotency_key"] = key
                    connection.execute(
                        """
                        UPDATE background_tasks
                        SET idempotency_key = ?, payload = ?
                        WHERE task_id = ?
                        """,
                        (key, json.dumps(payload, ensure_ascii=False), row["task_id"]),
                    )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                ux_background_tasks_idempotency_key_nonempty
            ON background_tasks (TRIM(idempotency_key))
            WHERE idempotency_key IS NOT NULL AND TRIM(idempotency_key) <> ''
            """
        )
        connection.commit()
    finally:
        connection.close()
