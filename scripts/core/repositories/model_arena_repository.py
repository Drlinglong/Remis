from __future__ import annotations

import json
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


class ModelArenaRepository:
    """Synchronous SQLite persistence for durable model-arena history."""

    _RUN_COLUMNS = {
        "project_id",
        "project_name_snapshot",
        "game_id",
        "source_lang_code",
        "target_lang_code",
        "sample_seed",
        "sampler_version",
        "sample_size",
        "eligible_count",
        "status",
        "settings_json",
        "started_at",
        "completed_at",
    }
    _CONTESTANT_COLUMNS = {
        "status",
        "request_count",
        "elapsed_ms",
        "failure_code",
    }
    _JSON_FIELDS = {
        "settings_json": ("settings", {}),
        "config_snapshot_json": ("config_snapshot", {}),
        "effective_parameters_json": ("effective_parameters", {}),
        "usage_json": ("usage", {}),
        "feature_tags_json": ("feature_tags", []),
        "display_permutation_json": ("display_permutation", []),
        "validation_json": ("validation", []),
        "reason_codes_json": ("reason_codes", []),
        "metrics_json": ("metrics", {}),
    }
    _SENSITIVE_CONFIG_KEYS = {
        "account",
        "account_id",
        "api_key",
        "api_token",
        "api_url",
        "authorization",
        "base_url",
        "endpoint",
        "masked_key",
        "password",
        "secret",
        "token",
        "url",
        "username",
    }

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
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _decode(value: Optional[str], fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @classmethod
    def _row_to_dict(cls, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for stored_name, (public_name, fallback) in cls._JSON_FIELDS.items():
            if stored_name in result:
                result[public_name] = cls._decode(result.pop(stored_name), fallback)
        return result

    @classmethod
    def _json_value(
        cls,
        payload: dict[str, Any],
        stored_name: str,
        public_name: str,
        fallback: Any,
    ) -> str:
        value = payload.get(stored_name, payload.get(public_name, fallback))
        if isinstance(value, str):
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError:
                pass
        return cls._json(value)

    @classmethod
    def _assert_safe_config_snapshot(cls, value: Any) -> None:
        if isinstance(value, dict):
            for raw_key, nested in value.items():
                key = str(raw_key).strip().lower().replace("-", "_")
                if (
                    key in cls._SENSITIVE_CONFIG_KEYS
                    or key.endswith("_api_key")
                    or (key.endswith("_token") and not key.endswith("_tokens"))
                ):
                    raise ValueError(
                        f"Sensitive field is not allowed in config_snapshot: {raw_key}"
                    )
                cls._assert_safe_config_snapshot(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                cls._assert_safe_config_snapshot(nested)

    def _insert_contestants(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        contestants: Iterable[dict[str, Any]],
    ) -> None:
        for contestant in contestants:
            config_snapshot = contestant.get(
                "config_snapshot_json",
                contestant.get("config_snapshot", {}),
            )
            if isinstance(config_snapshot, str):
                try:
                    config_snapshot = json.loads(config_snapshot)
                except json.JSONDecodeError as exc:
                    raise ValueError("config_snapshot must contain valid JSON") from exc
            if not isinstance(config_snapshot, dict):
                raise ValueError("config_snapshot must be a JSON object")
            self._assert_safe_config_snapshot(config_snapshot)
            connection.execute(
                """
                INSERT INTO model_arena_contestants (
                    contestant_id, run_id, provider_id, model_id, execution_order,
                    config_snapshot_json, config_fingerprint, prompt_fingerprint,
                    status, request_count, elapsed_ms, failure_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contestant["contestant_id"],
                    run_id,
                    contestant["provider_id"],
                    contestant["model_id"],
                    contestant["execution_order"],
                    self._json(config_snapshot),
                    contestant.get("config_fingerprint", ""),
                    contestant.get("prompt_fingerprint", ""),
                    contestant.get("status", "draft"),
                    contestant.get("request_count", 0),
                    contestant.get("elapsed_ms"),
                    contestant.get("failure_code"),
                ),
            )

    def _insert_samples(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        samples: Iterable[dict[str, Any]],
    ) -> None:
        for sample in samples:
            connection.execute(
                """
                INSERT INTO model_arena_samples (
                    sample_id, run_id, ordinal, entry_key, relative_file_path,
                    line_number, source_text, source_sha256, feature_tags_json,
                    display_permutation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample["sample_id"],
                    run_id,
                    sample["ordinal"],
                    sample["entry_key"],
                    sample["relative_file_path"],
                    sample.get("line_number"),
                    sample["source_text"],
                    sample["source_sha256"],
                    self._json_value(sample, "feature_tags_json", "feature_tags", []),
                    self._json_value(
                        sample,
                        "display_permutation_json",
                        "display_permutation",
                        [],
                    ),
                ),
            )

    def create_run(
        self,
        payload: dict[str, Any],
        contestants: Iterable[dict[str, Any]],
        samples: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """Atomically create one draft together with its frozen participants and samples."""
        run = dict(payload)
        contestants = list(contestants)
        samples = list(samples)
        if len(contestants) not in {2, 3}:
            raise ValueError("Model arena requires 2 or 3 contestants")
        requested_sample_size = run.get("sample_size", len(samples))
        if requested_sample_size != len(samples):
            raise ValueError("sample_size must match the number of persisted samples")
        run_id = str(run["run_id"])
        created_at = run.get("created_at") or self._now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO model_arena_runs (
                    run_id, project_id, project_name_snapshot, game_id,
                    source_lang_code, target_lang_code, sample_seed,
                    sampler_version, sample_size, eligible_count, status,
                    settings_json, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run.get("project_id"),
                    run["project_name_snapshot"],
                    run["game_id"],
                    run["source_lang_code"],
                    run["target_lang_code"],
                    run["sample_seed"],
                    run["sampler_version"],
                    requested_sample_size,
                    run["eligible_count"],
                    run.get("status", "draft"),
                    self._json_value(run, "settings_json", "settings", {}),
                    created_at,
                    run.get("started_at"),
                    run.get("completed_at"),
                ),
            )
            self._insert_contestants(connection, run_id, contestants)
            self._insert_samples(connection, run_id, samples)
            connection.commit()
        created = self.get_run(run_id)
        if created is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError(f"Failed to load newly created model arena run {run_id}")
        return created

    def get_run(
        self,
        run_id: str,
        *,
        include_children: bool = True,
    ) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            run_row = connection.execute(
                "SELECT * FROM model_arena_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None
            result = self._row_to_dict(run_row)
            if not include_children:
                return result

            table_queries = {
                "contestants": (
                    "SELECT * FROM model_arena_contestants "
                    "WHERE run_id = ? ORDER BY execution_order",
                    (run_id,),
                ),
                "samples": (
                    "SELECT * FROM model_arena_samples "
                    "WHERE run_id = ? ORDER BY ordinal",
                    (run_id,),
                ),
                "requests": (
                    """
                    SELECT request.*
                    FROM model_arena_requests AS request
                    JOIN model_arena_contestants AS contestant
                      ON contestant.contestant_id = request.contestant_id
                    WHERE contestant.run_id = ?
                    ORDER BY contestant.execution_order, request.batch_ordinal
                    """,
                    (run_id,),
                ),
                "outputs": (
                    """
                    SELECT output.*
                    FROM model_arena_outputs AS output
                    JOIN model_arena_samples AS sample
                      ON sample.sample_id = output.sample_id
                    JOIN model_arena_contestants AS contestant
                      ON contestant.contestant_id = output.contestant_id
                    WHERE sample.run_id = ?
                    ORDER BY sample.ordinal, contestant.execution_order
                    """,
                    (run_id,),
                ),
                "votes": (
                    """
                    SELECT vote.*
                    FROM model_arena_votes AS vote
                    JOIN model_arena_samples AS sample
                      ON sample.sample_id = vote.sample_id
                    WHERE sample.run_id = ?
                    ORDER BY sample.ordinal
                    """,
                    (run_id,),
                ),
                "events": (
                    "SELECT * FROM model_arena_events "
                    "WHERE run_id = ? ORDER BY sequence",
                    (run_id,),
                ),
            }
            for name, (query, parameters) in table_queries.items():
                rows = connection.execute(query, parameters).fetchall()
                result[name] = [self._row_to_dict(row) for row in rows]
            return result

    def list_runs(
        self,
        *,
        project_id: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        source_lang_code: Optional[str] = None,
        target_lang_code: Optional[str] = None,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if project_id is not None:
            clauses.append("run.project_id = ?")
            parameters.append(project_id)
        if statuses is not None:
            if isinstance(statuses, str):
                statuses = [statuses]
            normalized = sorted({str(status) for status in statuses if status})
            if not normalized:
                return {"runs": [], "total_count": 0}
            clauses.append(
                f"run.status IN ({', '.join('?' for _ in normalized)})"
            )
            parameters.extend(normalized)
        if source_lang_code:
            clauses.append("run.source_lang_code = ?")
            parameters.append(source_lang_code)
        if target_lang_code:
            clauses.append("run.target_lang_code = ?")
            parameters.append(target_lang_code)
        if provider_id or model_id:
            contestant_clauses = ["contestant.run_id = run.run_id"]
            if provider_id:
                contestant_clauses.append("contestant.provider_id = ?")
                parameters.append(provider_id)
            if model_id:
                contestant_clauses.append("contestant.model_id = ?")
                parameters.append(model_id)
            clauses.append(
                "EXISTS (SELECT 1 FROM model_arena_contestants AS contestant "
                f"WHERE {' AND '.join(contestant_clauses)})"
            )
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._lock, self._connect() as connection:
            total_count = connection.execute(
                f"SELECT COUNT(*) FROM model_arena_runs AS run {where_sql}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT run.*
                FROM model_arena_runs AS run
                {where_sql}
                ORDER BY run.created_at DESC, run.run_id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, max(1, min(limit, 200)), max(offset, 0)],
            ).fetchall()
        return {
            "runs": [self._row_to_dict(row) for row in rows],
            "total_count": int(total_count),
        }

    def replace_samples(
        self,
        run_id: str,
        samples: Iterable[dict[str, Any]],
        *,
        sample_seed: Optional[str] = None,
        eligible_count: Optional[int] = None,
        sample_size: Optional[int] = None,
    ) -> dict[str, Any]:
        """Replace samples only while a run is still an unpaid draft."""
        samples = list(samples)
        if sample_size is not None and sample_size != len(samples):
            raise ValueError("sample_size must match the number of replacement samples")
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM model_arena_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown model arena run: {run_id}")
            if row["status"] != "draft":
                raise ValueError("Samples can only be replaced while the run is a draft")
            connection.execute(
                "DELETE FROM model_arena_samples WHERE run_id = ?",
                (run_id,),
            )
            self._insert_samples(connection, run_id, samples)
            changes: list[str] = ["sample_size = ?"]
            values: list[Any] = [
                len(samples)
            ]
            if sample_seed is not None:
                changes.append("sample_seed = ?")
                values.append(sample_seed)
            if eligible_count is not None:
                changes.append("eligible_count = ?")
                values.append(eligible_count)
            values.append(run_id)
            connection.execute(
                f"UPDATE model_arena_runs SET {', '.join(changes)} WHERE run_id = ?",
                values,
            )
            connection.commit()
        result = self.get_run(run_id)
        if result is None:  # pragma: no cover - guarded above
            raise KeyError(f"Unknown model arena run: {run_id}")
        return result

    def update_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        if not changes:
            result = self.get_run(run_id)
            if result is None:
                raise KeyError(f"Unknown model arena run: {run_id}")
            return result

        assignments: list[str] = []
        parameters: list[Any] = []
        for public_name, value in changes.items():
            column_name = "settings_json" if public_name == "settings" else public_name
            if column_name not in self._RUN_COLUMNS:
                raise ValueError(f"Unsupported model arena run field: {public_name}")
            assignments.append(f"{column_name} = ?")
            parameters.append(
                self._json_value(
                    {public_name: value},
                    "settings_json",
                    "settings",
                    {},
                )
                if column_name == "settings_json"
                else value
            )
        parameters.append(run_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE model_arena_runs SET {', '.join(assignments)} WHERE run_id = ?",
                parameters,
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown model arena run: {run_id}")
            connection.commit()
        result = self.get_run(run_id)
        if result is None:  # pragma: no cover - guarded above
            raise KeyError(f"Unknown model arena run: {run_id}")
        return result

    def insert_requests(self, requests: Iterable[dict[str, Any]]) -> None:
        with self._lock, self._connect() as connection:
            for request in requests:
                connection.execute(
                    """
                    INSERT INTO model_arena_requests (
                        request_id, contestant_id, batch_ordinal,
                        system_instruction, prompt_text,
                        effective_parameters_json, prompt_sha256,
                        completion_text_before_parse, completion_source,
                        completion_sha256, usage_json, parse_status,
                        failure_code, elapsed_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request["request_id"],
                        request["contestant_id"],
                        request["batch_ordinal"],
                        request.get("system_instruction"),
                        request["prompt_text"],
                        self._json_value(
                            request,
                            "effective_parameters_json",
                            "effective_parameters",
                            {},
                        ),
                        request["prompt_sha256"],
                        request.get("completion_text_before_parse"),
                        request.get("completion_source", "assistant_content"),
                        request.get("completion_sha256"),
                        self._json_value(request, "usage_json", "usage", {}),
                        request.get("parse_status", "pending"),
                        request.get("failure_code"),
                        request.get("elapsed_ms"),
                        request.get("created_at") or self._now(),
                    ),
                )
            connection.commit()

    def update_contestant(
        self,
        contestant_id: str,
        **changes: Any,
    ) -> dict[str, Any]:
        if not changes:
            with self._lock, self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM model_arena_contestants
                    WHERE contestant_id = ?
                    """,
                    (contestant_id,),
                ).fetchone()
            if row is None:
                raise KeyError(f"Unknown model arena contestant: {contestant_id}")
            return self._row_to_dict(row)
        unsupported = set(changes) - self._CONTESTANT_COLUMNS
        if unsupported:
            raise ValueError(
                "Unsupported model arena contestant fields: "
                + ", ".join(sorted(unsupported))
            )
        assignments = [f"{name} = ?" for name in changes]
        parameters = [changes[name] for name in changes]
        parameters.append(contestant_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE model_arena_contestants SET "
                f"{', '.join(assignments)} WHERE contestant_id = ?",
                parameters,
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown model arena contestant: {contestant_id}")
            row = connection.execute(
                """
                SELECT * FROM model_arena_contestants
                WHERE contestant_id = ?
                """,
                (contestant_id,),
            ).fetchone()
            connection.commit()
        return self._row_to_dict(row)

    def insert_outputs(self, outputs: Iterable[dict[str, Any]]) -> None:
        with self._lock, self._connect() as connection:
            for output in outputs:
                connection.execute(
                    """
                    INSERT INTO model_arena_outputs (
                        output_id, sample_id, contestant_id, translated_text,
                        response_sha256, parse_status, hard_error_count,
                        validation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sample_id, contestant_id) DO UPDATE SET
                        translated_text=excluded.translated_text,
                        response_sha256=excluded.response_sha256,
                        parse_status=excluded.parse_status,
                        hard_error_count=excluded.hard_error_count,
                        validation_json=excluded.validation_json
                    """,
                    (
                        output["output_id"],
                        output["sample_id"],
                        output["contestant_id"],
                        output.get("translated_text"),
                        output.get("response_sha256"),
                        output.get("parse_status", "pending"),
                        output.get("hard_error_count", 0),
                        self._json_value(output, "validation_json", "validation", []),
                    ),
                )
            connection.commit()

    def upsert_vote(self, vote: dict[str, Any]) -> dict[str, Any]:
        verdict = str(vote["verdict"])
        winner_output_id = vote.get("winner_output_id")
        if verdict == "winner" and not winner_output_id:
            raise ValueError("winner_output_id is required for a winner verdict")
        if verdict != "winner" and winner_output_id is not None:
            raise ValueError("winner_output_id is only valid for a winner verdict")

        now = vote.get("updated_at") or self._now()
        created_at = vote.get("created_at") or now
        with self._lock, self._connect() as connection:
            if winner_output_id:
                winner = connection.execute(
                    """
                    SELECT 1 FROM model_arena_outputs
                    WHERE output_id = ? AND sample_id = ?
                    """,
                    (winner_output_id, vote["sample_id"]),
                ).fetchone()
                if winner is None:
                    raise ValueError("Winner output must belong to the voted sample")
            connection.execute(
                """
                INSERT INTO model_arena_votes (
                    vote_id, sample_id, verdict, winner_output_id,
                    reason_codes_json, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sample_id) DO UPDATE SET
                    verdict=excluded.verdict,
                    winner_output_id=excluded.winner_output_id,
                    reason_codes_json=excluded.reason_codes_json,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (
                    vote["vote_id"],
                    vote["sample_id"],
                    verdict,
                    winner_output_id,
                    self._json_value(
                        vote, "reason_codes_json", "reason_codes", []
                    ),
                    vote.get("note"),
                    created_at,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM model_arena_votes WHERE sample_id = ?",
                (vote["sample_id"],),
            ).fetchone()
            connection.commit()
        return self._row_to_dict(row)

    def append_event(
        self,
        run_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sequence = event.get("sequence")
            if sequence is None:
                sequence = connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1
                    FROM model_arena_events
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()[0]
            cursor = connection.execute(
                """
                INSERT INTO model_arena_events (
                    run_id, sequence, timestamp, level, event_type,
                    failure_code, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    event.get("timestamp") or self._now(),
                    event.get("level", "info"),
                    event["event_type"],
                    event.get("failure_code"),
                    self._json_value(event, "metrics_json", "metrics", {}),
                ),
            )
            row = connection.execute(
                "SELECT * FROM model_arena_events WHERE event_id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
        return self._row_to_dict(row)

    def insert_events(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        for event in events:
            inserted.append(self.append_event(str(event["run_id"]), event))
        return inserted

    def delete_run(self, run_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_arena_runs WHERE run_id = ?",
                (run_id,),
            )
            connection.commit()
        return cursor.rowcount > 0
