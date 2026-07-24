from __future__ import annotations

import json
import sqlite3
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class TaskRepository:
    """Synchronous SQLite ledger for background task state and ordered events."""

    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _decode(value: Optional[str], fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    def save_task(
        self,
        task: Dict[str, Any],
        *,
        event: Optional[Dict[str, Any]] = None,
    ) -> None:
        snapshot = deepcopy(task)
        snapshot.pop("log", None)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO background_tasks (
                    task_id, kind, project_id, parent_task_id, created_by, title,
                    status, stage, progress, created_at, started_at, updated_at,
                    finished_at, message, attention_reason, checkpoint, result,
                    blocking, dedupe_key, idempotency_key, source_route, archived_at,
                    payload
                ) VALUES (
                    :task_id, :kind, :project_id, :parent_task_id, :created_by, :title,
                    :status, :stage, :progress, :created_at, :started_at, :updated_at,
                    :finished_at, :message, :attention_reason, :checkpoint, :result,
                    :blocking, :dedupe_key, :idempotency_key, :source_route, :archived_at,
                    :payload
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    kind=excluded.kind,
                    project_id=excluded.project_id,
                    parent_task_id=excluded.parent_task_id,
                    created_by=excluded.created_by,
                    title=excluded.title,
                    status=excluded.status,
                    stage=excluded.stage,
                    progress=excluded.progress,
                    created_at=excluded.created_at,
                    started_at=excluded.started_at,
                    updated_at=excluded.updated_at,
                    finished_at=excluded.finished_at,
                    message=excluded.message,
                    attention_reason=excluded.attention_reason,
                    checkpoint=excluded.checkpoint,
                    result=excluded.result,
                    blocking=excluded.blocking,
                    dedupe_key=excluded.dedupe_key,
                    idempotency_key=excluded.idempotency_key,
                    source_route=excluded.source_route,
                    archived_at=excluded.archived_at,
                    payload=excluded.payload
                """,
                {
                    "task_id": str(snapshot["task_id"]),
                    "kind": str(snapshot.get("kind") or snapshot.get("task_kind") or "task"),
                    "project_id": snapshot.get("project_id") or (snapshot.get("summary") or {}).get("project_id"),
                    "parent_task_id": snapshot.get("parent_task_id"),
                    "created_by": self._json(snapshot.get("created_by") or {"type": "user"}),
                    "title": str(snapshot.get("title") or "Background task"),
                    "status": str(snapshot.get("status") or "unknown"),
                    "stage": str((snapshot.get("progress") or {}).get("stage") or snapshot.get("stage") or ""),
                    "progress": self._json(snapshot.get("progress") or {}),
                    "created_at": snapshot.get("created_at"),
                    "started_at": snapshot.get("started_at"),
                    "updated_at": snapshot.get("updated_at"),
                    "finished_at": snapshot.get("finished_at"),
                    "message": snapshot.get("message"),
                    "attention_reason": snapshot.get("attention_reason"),
                    "checkpoint": self._json(snapshot.get("checkpoint") or {}),
                    "result": self._json(snapshot.get("result") or {}),
                    "blocking": int(bool(snapshot.get("blocking", False))),
                    "dedupe_key": snapshot.get("dedupe_key"),
                    "idempotency_key": snapshot.get("idempotency_key"),
                    "source_route": str(snapshot.get("source_route") or "/"),
                    "archived_at": snapshot.get("archived_at"),
                    "payload": self._json(snapshot),
                },
            )
            if event and event.get("message"):
                next_sequence = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_events WHERE task_id = ?",
                    (str(snapshot["task_id"]),),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO task_events (
                        task_id, sequence, timestamp, level, event_type, message, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(snapshot["task_id"]),
                        next_sequence,
                        event.get("timestamp"),
                        str(event.get("level") or "info"),
                        str(event.get("event_type") or "log"),
                        str(event["message"]),
                        self._json(event.get("metadata") or {}),
                    ),
                )
            connection.commit()

    def _row_to_task(self, row: sqlite3.Row, *, include_events: bool = True) -> Dict[str, Any]:
        task = self._decode(row["payload"], {})
        task["task_id"] = row["task_id"]
        task.setdefault("kind", row["kind"])
        task.setdefault("project_id", row["project_id"])
        task.setdefault("parent_task_id", row["parent_task_id"])
        task.setdefault("created_by", self._decode(row["created_by"], {"type": "user"}))
        if task.get("title") or row["title"] != "Background task":
            task["title"] = task.get("title") or row["title"]
        task["status"] = row["status"]
        task["stage"] = row["stage"] or task.get("stage") or ""
        task["progress"] = self._decode(row["progress"], {})
        task["created_at"] = row["created_at"]
        task["started_at"] = row["started_at"]
        task["updated_at"] = row["updated_at"]
        task["finished_at"] = row["finished_at"]
        task["message"] = row["message"]
        task["attention_reason"] = row["attention_reason"]
        task["checkpoint"] = self._decode(row["checkpoint"], {})
        task["result"] = self._decode(row["result"], {})
        if "blocking" in task or row["blocking"]:
            task["blocking"] = bool(row["blocking"])
        task["dedupe_key"] = row["dedupe_key"]
        task["idempotency_key"] = row["idempotency_key"]
        if task.get("source_route") or row["source_route"] != "/":
            task["source_route"] = task.get("source_route") or row["source_route"]
        task["archived_at"] = row["archived_at"]
        if include_events:
            task["log"] = [event["message"] for event in self.list_events(row["task_id"])]
        else:
            task.pop("log", None)
        return task

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM background_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    @staticmethod
    def _in_clause(values: Iterable[str]) -> tuple[str, list[str]]:
        normalized = sorted({str(value).lower() for value in values if value})
        return ", ".join("?" for _ in normalized), normalized

    def list_tasks(
        self,
        *,
        statuses: Optional[Iterable[str]] = None,
        include_events: bool = True,
    ) -> list[Dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if statuses is not None:
            placeholders, normalized = self._in_clause(statuses)
            if not normalized:
                return []
            clauses.append(f"status IN ({placeholders})")
            parameters.extend(normalized)
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM background_tasks
                {where_sql}
                ORDER BY updated_at DESC, created_at DESC
                """,
                parameters,
            ).fetchall()
        return [self._row_to_task(row, include_events=include_events) for row in rows]

    def query_task_page(
        self,
        *,
        include_archived: bool = False,
        statuses: Optional[Iterable[str]] = None,
        kind: Optional[str] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Return one summary page and global queue counts without loading events."""
        clauses: list[str] = []
        parameters: list[Any] = []
        if not include_archived:
            clauses.append("archived_at IS NULL")
        if statuses is not None:
            placeholders, normalized = self._in_clause(statuses)
            if not normalized:
                return {"tasks": [], "total_count": 0, "active_count": 0, "attention_count": 0}
            clauses.append(f"status IN ({placeholders})")
            parameters.extend(normalized)
        if kind:
            clauses.append("kind = ?")
            parameters.append(kind)
        task_time_sql = "COALESCE(created_at, started_at)"
        if from_time:
            clauses.append(f"julianday({task_time_sql}) >= julianday(?)")
            parameters.append(from_time)
        if to_time:
            clauses.append(f"julianday({task_time_sql}) < julianday(?)")
            parameters.append(to_time)
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order_sql = (
            f"julianday({task_time_sql}) DESC"
            if from_time or to_time
            else "updated_at DESC, created_at DESC"
        )

        count_scope = "" if include_archived else "WHERE archived_at IS NULL"
        with self._lock, self._connect() as connection:
            count_row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total_count,
                    COALESCE(SUM(
                        CASE WHEN status IN (
                            'pending', 'starting', 'queued', 'running',
                            'processing', 'in_progress', 'awaiting_approval',
                            'waiting_approval'
                        ) THEN 1 ELSE 0 END
                    ), 0) AS active_count,
                    COALESCE(SUM(
                        CASE WHEN status IN (
                            'awaiting_approval', 'waiting_approval', 'failed',
                            'partial_failed', 'interrupted'
                        ) THEN 1 ELSE 0 END
                    ), 0) AS attention_count
                FROM background_tasks
                {count_scope}
                """
            ).fetchone()
            total_count = connection.execute(
                f"SELECT COUNT(*) FROM background_tasks{where_sql}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT *
                FROM background_tasks
                {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()

        return {
            "tasks": [self._row_to_task(row, include_events=False) for row in rows],
            "total_count": int(total_count),
            "active_count": int(count_row["active_count"]),
            "attention_count": int(count_row["attention_count"]),
        }

    def list_events(self, task_id: str, *, limit: int = 500) -> list[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, task_id, sequence, timestamp, level, event_type, message, metadata
                FROM task_events
                WHERE task_id = ?
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()
        events = [
            {
                "event_id": str(row["event_id"]),
                "task_id": row["task_id"],
                "sequence": row["sequence"],
                "timestamp": row["timestamp"],
                "level": row["level"],
                "event_type": row["event_type"],
                "message": row["message"],
                "metadata": self._decode(row["metadata"], {}),
            }
            for row in rows
        ]
        events.reverse()
        return events
