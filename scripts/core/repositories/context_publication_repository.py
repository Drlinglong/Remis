"""Atomic publication primitive for immutable context releases."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from scripts.core.repositories.context_delivery_membership_repository import (
    insert_memberships,
    validate_memberships,
)
from scripts.core.repositories.context_release_manifest_repository import (
    insert_release_manifest,
    validate_release_manifest,
)
from scripts.schemas.context import (
    ContextDeliveryMembership,
    ContextRelease,
    ContextReleaseManifest,
    ContextReleaseMetadata,
    GeneratedSynthesis,
)


class ContextPublicationConflictError(RuntimeError):
    """Raised when a run or release cannot satisfy the publication contract."""


class ContextPublicationRepository:
    """Commit one release, its snapshots, and the owning run as one unit."""

    def __init__(
        self,
        db_path: str,
        *,
        failure_injector: Callable[[str], None] | None = None,
    ):
        self.db_path = str(Path(db_path))
        self._lock = threading.RLock()
        self._failure_injector = failure_injector

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
    def _decode(value: str | None, fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @classmethod
    def _release_from_row(cls, row: sqlite3.Row) -> ContextRelease:
        columns = set(row.keys())
        metadata = ContextReleaseMetadata(
            source_snapshot_hash=row["source_snapshot_hash"],
            analysis_scope=cls._decode(row["analysis_scope_json"], {}),
            schema_version=row["schema_version"],
            prompt_version=row["prompt_version"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            analysis_config=cls._decode(row["analysis_config_json"], {}),
            created_at=row["created_at"],
            parent_release_id=row["parent_release_id"],
            upstream_version=row["upstream_version"],
        )
        return ContextRelease(
            release_id=row["release_id"],
            project_id=row["project_id"],
            metadata=metadata,
            analysis_run_id=row["analysis_run_id"] if "analysis_run_id" in columns else None,
        )

    def publish_draft(
        self,
        draft_id: str,
        metadata: ContextReleaseMetadata,
        aggregate_ids: Iterable[str],
        syntheses: Iterable[GeneratedSynthesis],
        delivery_memberships: Iterable[ContextDeliveryMembership] = (),
        release_manifest: ContextReleaseManifest | None = None,
        *,
        analysis_run_id: str | None = None,
    ) -> ContextRelease:
        """Publish a draft with run idempotency and a database seal."""
        aggregates = list(dict.fromkeys(aggregate_ids))
        generated = list(syntheses)
        membership_values = list(delivery_memberships)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run = self._run_for_publication(connection, analysis_run_id)
                existing = self._existing_run_release(connection, analysis_run_id)
                if existing is not None:
                    if run is not None and existing["project_id"] != run["project_id"]:
                        raise ContextPublicationConflictError(
                            "analysis run release belongs to another project"
                        )
                    if run is not None and run["publication_status"] != "published":
                        self._mark_run_published(connection, analysis_run_id)
                    connection.commit()
                    return self._release_from_row(existing)

                draft = self._draft_for_publish(connection, draft_id)
                if run is not None and draft["project_id"] != run["project_id"]:
                    raise ContextPublicationConflictError(
                        "analysis run and draft belong to different projects"
                    )
                if (
                    metadata.parent_release_id is not None
                    and metadata.parent_release_id != draft["base_release_id"]
                ):
                    raise ValueError(
                        "metadata.parent_release_id must match the draft base_release_id"
                    )
                self._validate_parent_release(
                    connection, draft["project_id"], draft["base_release_id"]
                )
                aggregate_rows = self._aggregate_rows(
                    connection, aggregates, draft["project_id"]
                )
                self._validate_syntheses(generated, aggregates, aggregate_rows)
                membership_values = validate_memberships(
                    connection,
                    membership_values,
                    set(aggregates),
                    draft["project_id"],
                )
                if release_manifest is not None:
                    validate_release_manifest(
                        connection, release_manifest, draft["project_id"],
                    )
                release_id = str(uuid.uuid4())
                self._insert_release(
                    connection,
                    release_id,
                    draft["project_id"],
                    metadata,
                    draft["base_release_id"],
                    analysis_run_id,
                )
                self._inject("after_release_insert")
                self._snapshot_aggregates(connection, release_id, aggregate_rows)
                self._insert_syntheses(connection, release_id, generated)
                insert_memberships(connection, release_id, membership_values)
                if release_manifest is not None:
                    insert_release_manifest(connection, release_id, release_manifest)
                self._copy_draft_overrides(connection, draft_id, release_id)
                self._inject("after_children_before_run_update")
                if analysis_run_id is not None:
                    self._mark_run_published(connection, analysis_run_id)
                self._inject("after_run_update_before_seal")
                connection.execute(
                    "INSERT INTO context_release_seals (release_id, sealed_at) VALUES (?, ?)",
                    (release_id, self._now()),
                )
                connection.execute(
                    "UPDATE context_drafts SET status = 'published', updated_at = ? "
                    "WHERE draft_id = ?",
                    (self._now(), draft_id),
                )
                release_row = connection.execute(
                    "SELECT * FROM context_releases WHERE release_id = ?",
                    (release_id,),
                ).fetchone()
                connection.commit()
                if release_row is None:  # pragma: no cover - transaction invariant
                    raise RuntimeError("Published context release could not be reloaded")
                return self._release_from_row(release_row)
            except Exception:
                connection.rollback()
                raise

    def get_release_for_analysis_run(self, analysis_run_id: str) -> ContextRelease | None:
        with self._lock, self._connect() as connection:
            row = self._existing_run_release(connection, analysis_run_id)
        return self._release_from_row(row) if row else None

    def _inject(self, stage: str) -> None:
        if self._failure_injector is not None:
            self._failure_injector(stage)

    @staticmethod
    def _run_for_publication(
        connection: sqlite3.Connection, analysis_run_id: str | None
    ) -> sqlite3.Row | None:
        if analysis_run_id is None:
            return None
        row = connection.execute(
            "SELECT * FROM context_analysis_runs WHERE run_id = ?",
            (analysis_run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown context analysis run: {analysis_run_id}")
        if row["status"] == "complete" and row["publication_status"] != "published":
            raise ContextPublicationConflictError(
                "completed analysis run cannot publish a context release"
            )
        return row

    @staticmethod
    def _existing_run_release(
        connection: sqlite3.Connection, analysis_run_id: str | None
    ) -> sqlite3.Row | None:
        if analysis_run_id is None:
            return None
        return connection.execute(
            "SELECT * FROM context_releases WHERE analysis_run_id = ?",
            (analysis_run_id,),
        ).fetchone()

    @staticmethod
    def _mark_run_published(
        connection: sqlite3.Connection, analysis_run_id: str | None
    ) -> None:
        if analysis_run_id is None:
            return
        updated = connection.execute(
            """
            UPDATE context_analysis_runs
            SET phase = 'complete', status = 'complete',
                publication_status = 'published',
                updated_at = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), analysis_run_id),
        )
        if updated.rowcount != 1:
            raise KeyError(f"Unknown context analysis run: {analysis_run_id}")

    @staticmethod
    def _draft_for_publish(
        connection: sqlite3.Connection, draft_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM context_drafts WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown context draft: {draft_id}")
        if row["status"] != "draft":
            raise ValueError("Only an open context draft can be published")
        return row

    @staticmethod
    def _validate_parent_release(
        connection: sqlite3.Connection, project_id: str, release_id: str | None
    ) -> None:
        if release_id is None:
            return
        row = connection.execute(
            "SELECT project_id FROM context_releases WHERE release_id = ?",
            (release_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown context release: {release_id}")
        if row["project_id"] != project_id:
            raise ValueError("A draft parent release must belong to the draft project")

    @staticmethod
    def _aggregate_rows(
        connection: sqlite3.Connection,
        aggregate_ids: list[str],
        project_id: str,
    ) -> list[sqlite3.Row]:
        rows = []
        for aggregate_id in aggregate_ids:
            row = connection.execute(
                "SELECT * FROM context_aggregates WHERE aggregate_id = ?",
                (aggregate_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown context aggregate: {aggregate_id}")
            if row["project_id"] != project_id:
                raise ValueError("All release aggregates must belong to the draft project")
            rows.append(row)
        return rows

    @classmethod
    def _validate_syntheses(
        cls,
        syntheses: list[GeneratedSynthesis],
        aggregate_ids: list[str],
        aggregate_rows: list[sqlite3.Row],
    ) -> None:
        allowed = set(aggregate_ids)
        by_aggregate: dict[str, list[GeneratedSynthesis]] = {}
        for synthesis in syntheses:
            if synthesis.aggregate_id not in allowed:
                raise ValueError(
                    "Generated synthesis references aggregates outside the release: "
                    + synthesis.aggregate_id
                )
            by_aggregate.setdefault(synthesis.aggregate_id, []).append(synthesis)
        duplicate_keys = [
            key for key, values in by_aggregate.items() if len(values) != 1
        ]
        if duplicate_keys:
            raise ValueError(
                "Each synthesized aggregate must have exactly one synthesis: "
                + ", ".join(sorted(duplicate_keys))
            )
        missing = [
            row["aggregate_id"]
            for row in aggregate_rows
            if not cls._is_audit_only(row) and row["aggregate_id"] not in by_aggregate
        ]
        if missing:
            raise ValueError(
                "Each synthesized aggregate must have exactly one synthesis: "
                + ", ".join(sorted(missing))
            )
        for row in aggregate_rows:
            values = by_aggregate.get(row["aggregate_id"], [])
            if values and values[0].context_key != row["aggregate_key"]:
                raise ValueError(
                    "Generated synthesis context_key must match aggregate_key for "
                    + row["aggregate_id"]
                )
        audit_only_with_synthesis = [
            row["aggregate_id"]
            for row in aggregate_rows
            if cls._is_audit_only(row) and row["aggregate_id"] in by_aggregate
        ]
        if audit_only_with_synthesis:
            raise ValueError(
                "Audit-only aggregates cannot have generated syntheses: "
                + ", ".join(sorted(audit_only_with_synthesis))
            )

    @classmethod
    def _is_audit_only(cls, row: sqlite3.Row) -> bool:
        payload = cls._decode(row["payload_json"], {})
        return bool(
            isinstance(payload, dict)
            and (
                payload.get("audit_only") is True
                or payload.get("synthesis_required") is False
            )
        )

    def _insert_release(
        self,
        connection: sqlite3.Connection,
        release_id: str,
        project_id: str,
        metadata: ContextReleaseMetadata,
        parent_id: str | None,
        analysis_run_id: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO context_releases (
                release_id, project_id, source_snapshot_hash, analysis_scope_json,
                schema_version, prompt_version, provider_id, model_id,
                analysis_config_json, created_at, parent_release_id, upstream_version,
                analysis_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                project_id,
                metadata.source_snapshot_hash,
                self._json(metadata.analysis_scope),
                metadata.schema_version,
                metadata.prompt_version,
                metadata.provider_id,
                metadata.model_id,
                self._json(metadata.analysis_config),
                metadata.created_at,
                parent_id,
                metadata.upstream_version,
                analysis_run_id,
            ),
        )

    def _snapshot_aggregates(
        self,
        connection: sqlite3.Connection,
        release_id: str,
        aggregate_rows: list[sqlite3.Row],
    ) -> None:
        for row in aggregate_rows:
            contribution_ids = [
                item["contribution_id"]
                for item in connection.execute(
                    """
                    SELECT contribution_id FROM context_aggregate_contributions
                    WHERE aggregate_id = ? ORDER BY contribution_id
                    """,
                    (row["aggregate_id"],),
                ).fetchall()
            ]
            connection.execute(
                """
                INSERT INTO context_release_aggregates (
                    release_id, aggregate_id, aggregate_type, aggregate_key,
                    payload_json, contribution_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    row["aggregate_id"],
                    row["aggregate_type"],
                    row["aggregate_key"],
                    row["payload_json"],
                    self._json(contribution_ids),
                ),
            )

    def _insert_syntheses(
        self,
        connection: sqlite3.Connection,
        release_id: str,
        syntheses: list[GeneratedSynthesis],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO context_release_syntheses
                (synthesis_id, release_id, aggregate_id, context_key, content_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    item.synthesis_id,
                    release_id,
                    item.aggregate_id,
                    item.context_key,
                    self._json(item.content),
                )
                for item in syntheses
            ],
        )

    def _copy_draft_overrides(
        self, connection: sqlite3.Connection, draft_id: str, release_id: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO context_release_overrides (release_id, target_key, value_json, note)
            SELECT ?, target_key, value_json, note
            FROM context_draft_overrides WHERE draft_id = ?
            """,
            (release_id, draft_id),
        )


ContextPublicationCoordinator = ContextPublicationRepository
