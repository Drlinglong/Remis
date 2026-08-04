"""Durable, idempotent checkpoints for bounded context analysis batches."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class ContextAnalysisBatchConflictError(RuntimeError):
    """Raised when a batch index is reused with different evidence or output."""


class ContextAnalysisConfigurationError(ValueError):
    """Raised when analysis metadata is unsafe or cannot be canonicalized."""


@dataclass(frozen=True)
class ContextAnalysisRun:
    run_id: str
    task_id: str | None
    project_id: str
    source_snapshot_hash: str
    analysis_scope: dict[str, Any]
    config_fingerprint: str
    config: dict[str, Any]
    phase: str
    status: str
    publication_status: str
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class ContextAnalysisBatch:
    batch_id: str
    run_id: str
    phase: str
    batch_index: int
    source_item_ids: tuple[str, ...]
    payload: dict[str, Any]
    status: str
    error: dict[str, Any] | None
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_credentials(value: Any, path: str = "analysis") -> None:
    forbidden = {"api_key", "api_token", "authorization", "password", "secret", "token", "credential"}
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in forbidden or normalized.endswith("_token") or normalized.endswith("_secret"):
                raise ContextAnalysisConfigurationError(f"credentials are not allowed in {path}.{key}")
            _reject_credentials(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_credentials(nested, f"{path}[{index}]")


def _canonical_json(value: Any) -> str:
    _reject_credentials(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ContextAnalysisConfigurationError("analysis metadata must be JSON serializable") from exc


def analysis_config_fingerprint(config: Mapping[str, Any] | None) -> str:
    """Return a stable fingerprint without persisting credentials."""
    canonical = _canonical_json(dict(config or {}))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


config_fingerprint = analysis_config_fingerprint


class ContextAnalysisBatchRepository:
    """SQLite store for run identity, per-batch output, and resume checkpoints."""

    VALID_PHASES = {"extraction", "review", "aggregation", "synthesis"}

    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _decode(value: str | None, fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @classmethod
    def _run_from_row(cls, row: sqlite3.Row) -> ContextAnalysisRun:
        return ContextAnalysisRun(
            run_id=row["run_id"], task_id=row["task_id"], project_id=row["project_id"],
            source_snapshot_hash=row["source_snapshot_hash"],
            analysis_scope=cls._decode(row["analysis_scope_json"], {}),
            config_fingerprint=row["config_fingerprint"], config=cls._decode(row["config_json"], {}),
            phase=row["phase"], status=row["status"], publication_status=row["publication_status"],
            created_at=row["created_at"], updated_at=row["updated_at"], completed_at=row["completed_at"],
        )

    @classmethod
    def _batch_from_row(cls, row: sqlite3.Row) -> ContextAnalysisBatch:
        ids = cls._decode(row["source_item_ids_json"], [])
        return ContextAnalysisBatch(
            batch_id=row["batch_id"], run_id=row["run_id"], phase=row["phase"],
            batch_index=row["batch_index"], source_item_ids=tuple(str(item) for item in ids),
            payload=cls._decode(row["payload_json"], {}), status=row["status"],
            error=cls._decode(row["error_json"], None), created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def start_or_resume_run(
        self,
        project_id: str,
        task_id: str | None,
        source_snapshot_hash: str,
        analysis_scope: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        run_id: str | None = None,
    ) -> ContextAnalysisRun:
        """Reuse only an unfinished run whose complete identity matches."""
        if not project_id or not source_snapshot_hash:
            raise ValueError("project_id and source_snapshot_hash are required")
        scope_json = _canonical_json(dict(analysis_scope))
        config_json = _canonical_json(dict(config or {}))
        fingerprint = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = None
            if run_id:
                row = connection.execute(
                    "SELECT * FROM context_analysis_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row and not self._identity_matches(row, project_id, source_snapshot_hash, scope_json, fingerprint):
                    raise ContextAnalysisBatchConflictError("requested run identity does not match current analysis")
                if (
                    row
                    and row["status"] == "complete"
                    and row["publication_status"] != "published"
                ):
                    raise ContextAnalysisBatchConflictError("completed analysis runs cannot be resumed")
            if row is None:
                row = connection.execute(
                    """SELECT * FROM context_analysis_runs
                       WHERE project_id = ? AND source_snapshot_hash = ?
                         AND analysis_scope_json = ? AND config_fingerprint = ?
                         AND status != 'complete'
                       ORDER BY updated_at DESC LIMIT 1""",
                    (project_id, source_snapshot_hash, scope_json, fingerprint),
                ).fetchone()
            if row:
                return self._run_from_row(row)
            now = _now()
            new_run_id = run_id or str(uuid.uuid4())
            connection.execute(
                """INSERT INTO context_analysis_runs
                   (run_id, task_id, project_id, source_snapshot_hash, analysis_scope_json,
                    config_fingerprint, config_json, phase, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'extraction', 'running', ?, ?)""",
                (new_run_id, task_id, project_id, source_snapshot_hash, scope_json,
                 fingerprint, config_json, now, now),
            )
            return self._run_from_row(
                connection.execute("SELECT * FROM context_analysis_runs WHERE run_id = ?", (new_run_id,)).fetchone()
            )

    @staticmethod
    def _identity_matches(
        row: sqlite3.Row, project_id: str, snapshot_hash: str, scope_json: str, fingerprint: str
    ) -> bool:
        return (
            row["project_id"] == project_id
            and row["source_snapshot_hash"] == snapshot_hash
            and row["analysis_scope_json"] == scope_json
            and row["config_fingerprint"] == fingerprint
        )

    def get_run(self, run_id: str) -> ContextAnalysisRun | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM context_analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
            return self._run_from_row(row) if row else None

    def list_runs(self, project_id: str) -> list[ContextAnalysisRun]:
        """Return project analysis runs from newest to oldest."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM context_analysis_runs
                   WHERE project_id = ?
                   ORDER BY updated_at DESC, created_at DESC, run_id DESC""",
                (project_id,),
            ).fetchall()
            return [self._run_from_row(row) for row in rows]

    def get_batch(self, run_id: str, phase: str, batch_index: int) -> ContextAnalysisBatch | None:
        if phase not in self.VALID_PHASES or batch_index < 0:
            raise ValueError("invalid analysis batch identity")
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_analysis_batches WHERE run_id = ? AND phase = ? AND batch_index = ?",
                (run_id, phase, batch_index),
            ).fetchone()
            return self._batch_from_row(row) if row else None

    def list_batches(self, run_id: str, phase: str | None = None) -> list[ContextAnalysisBatch]:
        parameters: list[Any] = [run_id]
        clause = ""
        if phase is not None:
            if phase not in self.VALID_PHASES:
                raise ValueError("invalid analysis batch phase")
            clause = " AND phase = ?"
            parameters.append(phase)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM context_analysis_batches WHERE run_id = ?{clause} ORDER BY phase, batch_index",
                parameters,
            ).fetchall()
            return [self._batch_from_row(row) for row in rows]

    def save_batch(
        self,
        run_id: str,
        phase: str,
        batch_index: int,
        source_item_ids: Sequence[str],
        payload: Mapping[str, Any],
        *,
        status: str = "succeeded",
        error: Mapping[str, Any] | None = None,
    ) -> ContextAnalysisBatch:
        """Atomically write one batch; retries cannot duplicate or rewrite success."""
        if phase not in self.VALID_PHASES or batch_index < 0 or status not in {"succeeded", "failed"}:
            raise ValueError("invalid analysis batch state")
        ids_json = _canonical_json(list(dict.fromkeys(str(item) for item in source_item_ids)))
        payload_json = _canonical_json(dict(payload))
        error_json = _canonical_json(dict(error)) if error is not None else None
        now = _now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM context_analysis_batches WHERE run_id = ? AND phase = ? AND batch_index = ?",
                (run_id, phase, batch_index),
            ).fetchone()
            if existing and existing["status"] == "succeeded":
                if existing["source_item_ids_json"] != ids_json or existing["payload_json"] != payload_json:
                    raise ContextAnalysisBatchConflictError("successful batch cannot be overwritten")
                return self._batch_from_row(existing)
            if existing:
                connection.execute(
                    """UPDATE context_analysis_batches
                       SET source_item_ids_json = ?, payload_json = ?, status = ?, error_json = ?, updated_at = ?
                       WHERE batch_id = ?""",
                    (ids_json, payload_json, status, error_json, now, existing["batch_id"]),
                )
                batch_id = existing["batch_id"]
            else:
                batch_id = str(uuid.uuid4())
                connection.execute(
                    """INSERT INTO context_analysis_batches
                       (batch_id, run_id, phase, batch_index, source_item_ids_json, payload_json,
                        status, error_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (batch_id, run_id, phase, batch_index, ids_json, payload_json, status, error_json, now, now),
                )
            if status == "succeeded":
                run_phase = {
                    "extraction": "extraction",
                    "review": "review",
                    "aggregation": "aggregation",
                    "synthesis": "synthesis",
                }[phase]
                connection.execute(
                    "UPDATE context_analysis_runs SET phase = ?, status = 'running', updated_at = ? WHERE run_id = ?",
                    (run_phase, now, run_id),
                )
            else:
                connection.execute(
                    "UPDATE context_analysis_runs SET status = 'failed', updated_at = ? WHERE run_id = ?",
                    (now, run_id),
                )
            row = connection.execute("SELECT * FROM context_analysis_batches WHERE batch_id = ?", (batch_id,)).fetchone()
            return self._batch_from_row(row)

    def mark_complete(self, run_id: str) -> ContextAnalysisRun:
        return self._update_run(run_id, phase="complete", status="complete", completed_at=_now())

    def mark_analysis_ready(self, run_id: str) -> ContextAnalysisRun:
        """Leave the run resumable until a separate candidate publish succeeds."""
        return self._update_run(run_id, phase="publishing", status="running", completed_at=None)

    def mark_failed(self, run_id: str) -> ContextAnalysisRun:
        """Keep successful batches resumable after any later workflow failure."""
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown context analysis run: {run_id}")
        if run.status == "complete":
            return run
        return self._update_run(run_id, status="failed", completed_at=None)

    def mark_published(self, run_id: str, candidate_ids: Sequence[str] = ()) -> ContextAnalysisRun:
        """Mark publication separately while preserving all batch rows."""
        return self._update_run(
            run_id, phase="complete", status="complete", publication_status="published", completed_at=_now()
        )

    def _update_run(self, run_id: str, **updates: Any) -> ContextAnalysisRun:
        allowed = {"phase", "status", "publication_status", "completed_at"}
        if set(updates) - allowed:
            raise ValueError("unsupported context analysis run update")
        assignments = [f"{key} = ?" for key in updates]
        values = list(updates.values()) + [_now(), run_id]
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"UPDATE context_analysis_runs SET {', '.join(assignments)}, updated_at = ? WHERE run_id = ?",
                values,
            )
            row = connection.execute("SELECT * FROM context_analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                raise KeyError(f"unknown context analysis run: {run_id}")
            return self._run_from_row(row)

    def resume_checkpoint(self, run_id: str) -> dict[str, Any]:
        """Expose the last successful batch without pretending workflow wiring exists."""
        batches = [item for item in self.list_batches(run_id) if item.status == "succeeded"]
        latest: dict[str, ContextAnalysisBatch] = {}
        for item in batches:
            current = latest.get(item.phase)
            if current is None or item.batch_index > current.batch_index:
                latest[item.phase] = item
        return {
            "run_id": run_id,
            "run": self.get_run(run_id),
            "last_successful_batch": {phase: item.batch_index for phase, item in latest.items()},
            "batches": batches,
        }


ContextAnalysisBatchStore = ContextAnalysisBatchRepository
