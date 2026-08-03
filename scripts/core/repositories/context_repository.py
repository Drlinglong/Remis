"""SQLite repository for traceable Mod Context inputs and immutable releases."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.core.repositories.context_delivery_membership_repository import (
    counts_by_aggregate,
    list_memberships,
)
from scripts.core.repositories.context_publication_repository import (
    ContextPublicationRepository,
)
from scripts.core.repositories.context_release_manifest_repository import (
    insert_release_manifest,
    load_release_manifest,
    load_release_traceability_source,
    upsert_source_item as persist_source_item,
    validate_release_manifest,
)
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextDeliveryMembership,
    ContextDraft,
    ContextReleaseManifest,
    ContextRelease,
    ContextReleaseMetadata,
    ContextSourceItem,
    EffectiveContext,
    GeneratedSynthesis,
    HumanOverride,
)


class ImmutableContextReleaseError(RuntimeError):
    """Raised when a caller tries to mutate a published context release."""


class ContextRepository:
    """Synchronous SQLite persistence with release snapshots as the boundary."""

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
    def _decode(value: str | None, fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @staticmethod
    def _merge_context(
        generated: dict[str, dict[str, Any]],
        overrides: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        effective = deepcopy(generated)
        for target_key, override in overrides.items():
            current = effective.get(target_key, {})
            if isinstance(current, dict) and isinstance(override, dict):
                current.update(deepcopy(override))
                effective[target_key] = current
            else:  # pragma: no cover - typed contracts currently require dictionaries
                effective[target_key] = deepcopy(override)
        return effective

    @classmethod
    def _source_from_row(cls, row: sqlite3.Row) -> ContextSourceItem:
        return ContextSourceItem(
            source_item_id=row["source_item_id"],
            project_id=row["project_id"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            content=row["content"],
            content_hash=row["content_hash"],
            metadata=cls._decode(row["metadata_json"], {}),
            created_at=row["created_at"],
        )

    @classmethod
    def _contribution_from_row(cls, row: sqlite3.Row) -> ContextContribution:
        return ContextContribution(
            contribution_id=row["contribution_id"],
            source_item_id=row["source_item_id"],
            contribution_type=row["contribution_type"],
            subject_key=row["subject_key"],
            payload=cls._decode(row["payload_json"], {}),
            provenance=row["provenance"],
            created_at=row["created_at"],
        )

    @classmethod
    def _aggregate_from_row(
        cls, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> ContextAggregate:
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
        return ContextAggregate(
            aggregate_id=row["aggregate_id"],
            project_id=row["project_id"],
            aggregate_type=row["aggregate_type"],
            aggregate_key=row["aggregate_key"],
            payload=cls._decode(row["payload_json"], {}),
            contribution_ids=contribution_ids,
            created_at=row["created_at"],
        )

    @classmethod
    def _release_from_row(cls, row: sqlite3.Row) -> ContextRelease:
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
            analysis_run_id=(
                row["analysis_run_id"]
                if "analysis_run_id" in row.keys()
                else None
            ),
        )

    def create_source_item(self, item: ContextSourceItem) -> ContextSourceItem:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO context_source_items (
                    source_item_id, project_id, source_type, source_ref, content,
                    content_hash, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.source_item_id,
                    item.project_id,
                    item.source_type,
                    item.source_ref,
                    item.content,
                    item.content_hash,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )
            connection.commit()
        return item

    def upsert_source_item(self, item: ContextSourceItem) -> ContextSourceItem:
        with self._lock, self._connect() as connection: persist_source_item(connection, item)
        return item
    def get_source_item(self, source_item_id: str) -> ContextSourceItem | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_source_items WHERE source_item_id = ?",
                (source_item_id,),
            ).fetchone()
        return self._source_from_row(row) if row else None

    def list_source_items(self, project_id: str) -> list[ContextSourceItem]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM context_source_items
                WHERE project_id = ? ORDER BY created_at, source_item_id
                """,
                (project_id,),
            ).fetchall()
        return [self._source_from_row(row) for row in rows]

    def create_contribution(self, item: ContextContribution) -> ContextContribution:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO context_contributions (
                    contribution_id, source_item_id, contribution_type, subject_key,
                    payload_json, provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.contribution_id,
                    item.source_item_id,
                    item.contribution_type,
                    item.subject_key,
                    self._json(item.payload),
                    item.provenance,
                    item.created_at,
                ),
            )
            connection.commit()
        return item

    def list_contributions(self, project_id: str) -> list[ContextContribution]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT contribution.*
                FROM context_contributions AS contribution
                JOIN context_source_items AS source
                  ON source.source_item_id = contribution.source_item_id
                WHERE source.project_id = ?
                ORDER BY contribution.created_at, contribution.contribution_id
                """,
                (project_id,),
            ).fetchall()
        return [self._contribution_from_row(row) for row in rows]

    def get_contribution(self, contribution_id: str) -> ContextContribution | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_contributions WHERE contribution_id = ?",
                (contribution_id,),
            ).fetchone()
        return self._contribution_from_row(row) if row else None

    def save_aggregate(self, aggregate: ContextAggregate) -> ContextAggregate:
        with self._lock, self._connect() as connection:
            self._validate_aggregate_inputs(connection, aggregate)
            connection.execute(
                """
                INSERT INTO context_aggregates (
                    aggregate_id, project_id, aggregate_type, aggregate_key,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(aggregate_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    aggregate_type = excluded.aggregate_type,
                    aggregate_key = excluded.aggregate_key,
                    payload_json = excluded.payload_json
                """,
                (
                    aggregate.aggregate_id,
                    aggregate.project_id,
                    aggregate.aggregate_type,
                    aggregate.aggregate_key,
                    self._json(aggregate.payload),
                    aggregate.created_at,
                ),
            )
            connection.execute(
                "DELETE FROM context_aggregate_contributions WHERE aggregate_id = ?",
                (aggregate.aggregate_id,),
            )
            connection.executemany(
                """
                INSERT INTO context_aggregate_contributions (aggregate_id, contribution_id)
                VALUES (?, ?)
                """,
                [(aggregate.aggregate_id, item) for item in aggregate.contribution_ids],
            )
            connection.commit()
        return aggregate

    @staticmethod
    def _validate_aggregate_inputs(
        connection: sqlite3.Connection, aggregate: ContextAggregate
    ) -> None:
        placeholders = ", ".join("?" for _ in aggregate.contribution_ids)
        rows = connection.execute(
            f"""
            SELECT contribution.contribution_id, source.project_id
            FROM context_contributions AS contribution
            JOIN context_source_items AS source
              ON source.source_item_id = contribution.source_item_id
            WHERE contribution.contribution_id IN ({placeholders})
            """,
            aggregate.contribution_ids,
        ).fetchall()
        found = {row["contribution_id"] for row in rows}
        if found != set(aggregate.contribution_ids):
            missing = sorted(set(aggregate.contribution_ids) - found)
            raise ValueError(f"Unknown context contributions: {', '.join(missing)}")
        if any(row["project_id"] != aggregate.project_id for row in rows):
            raise ValueError("All aggregate contributions must belong to the aggregate project")

    def get_aggregate(self, aggregate_id: str) -> ContextAggregate | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_aggregates WHERE aggregate_id = ?",
                (aggregate_id,),
            ).fetchone()
            return self._aggregate_from_row(connection, row) if row else None

    def list_aggregates(self, project_id: str) -> list[ContextAggregate]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM context_aggregates
                WHERE project_id = ? ORDER BY aggregate_type, aggregate_key
                """,
                (project_id,),
            ).fetchall()
            return [self._aggregate_from_row(connection, row) for row in rows]

    def create_draft(self, project_id: str, base_release_id: str | None = None) -> ContextDraft:
        draft = ContextDraft(
            draft_id=str(uuid.uuid4()),
            project_id=project_id,
            base_release_id=base_release_id,
            status="draft",
            created_at=self._now(),
            updated_at=self._now(),
        )
        with self._lock, self._connect() as connection:
            self._validate_parent_release(connection, project_id, base_release_id)
            connection.execute(
                """
                INSERT INTO context_drafts
                    (draft_id, project_id, base_release_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (draft.draft_id, project_id, base_release_id, draft.created_at, draft.updated_at),
            )
            connection.execute(
                """
                INSERT INTO context_draft_overrides
                    (draft_id, target_key, value_json, note, updated_at)
                SELECT ?, target_key, value_json, note, ?
                FROM context_release_overrides
                WHERE release_id = ?
                """,
                (draft.draft_id, draft.updated_at, base_release_id),
            )
            connection.commit()
        return draft

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

    def get_draft(self, draft_id: str) -> ContextDraft | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            if row is None:
                return None
            overrides = connection.execute(
                """
                SELECT target_key, value_json, note
                FROM context_draft_overrides WHERE draft_id = ?
                ORDER BY target_key
                """,
                (draft_id,),
            ).fetchall()
        return ContextDraft(
            draft_id=row["draft_id"],
            project_id=row["project_id"],
            base_release_id=row["base_release_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            overrides=[
                HumanOverride(
                    target_key=item["target_key"],
                    value=self._decode(item["value_json"], {}),
                    note=item["note"],
                )
                for item in overrides
            ],
        )

    def save_draft_override(self, draft_id: str, override: HumanOverride) -> HumanOverride:
        now = self._now()
        with self._lock, self._connect() as connection:
            draft = connection.execute(
                "SELECT status FROM context_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            if draft is None:
                raise KeyError(f"Unknown context draft: {draft_id}")
            if draft["status"] != "draft":
                raise ValueError("Only an open context draft can be edited")
            connection.execute(
                """
                INSERT INTO context_draft_overrides
                    (draft_id, target_key, value_json, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(draft_id, target_key) DO UPDATE SET
                    value_json = excluded.value_json,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (draft_id, override.target_key, self._json(override.value), override.note, now),
            )
            connection.execute(
                "UPDATE context_drafts SET updated_at = ? WHERE draft_id = ?",
                (now, draft_id),
            )
            connection.commit()
        return override

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
        return ContextPublicationRepository(self.db_path).publish_draft(
            draft_id,
            metadata,
            aggregate_ids,
            syntheses,
            delivery_memberships,
            release_manifest,
            analysis_run_id=analysis_run_id,
        )

    def get_release(self, release_id: str) -> ContextRelease | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM context_releases WHERE release_id = ?", (release_id,)
            ).fetchone()
        return self._release_from_row(row) if row else None

    def get_release_manifest(self, release_id: str) -> ContextReleaseManifest | None:
        with self._lock, self._connect() as connection: return load_release_manifest(connection, release_id)

    def list_releases(self, project_id: str) -> list[ContextRelease]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM context_releases
                WHERE project_id = ? ORDER BY created_at DESC, release_id DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._release_from_row(row) for row in rows]

    def get_effective_context(self, release_id: str) -> EffectiveContext | None:
        release = self.get_release(release_id)
        if release is None:
            return None
        with self._lock, self._connect() as connection:
            syntheses = connection.execute(
                """
                SELECT context_key, content_json FROM context_release_syntheses
                WHERE release_id = ? ORDER BY context_key
                """,
                (release_id,),
            ).fetchall()
            overrides = connection.execute(
                """
                SELECT target_key, value_json FROM context_release_overrides
                WHERE release_id = ? ORDER BY target_key
                """,
                (release_id,),
            ).fetchall()
        generated = {
            row["context_key"]: self._decode(row["content_json"], {}) for row in syntheses
        }
        human = {
            row["target_key"]: self._decode(row["value_json"], {}) for row in overrides
        }
        effective = self._merge_context(generated, human)
        return EffectiveContext(
            release=release,
            generated_synthesis=generated,
            human_overrides=human,
            effective_context=effective,
        )

    def get_release_traceability(self, release_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            membership_counts = counts_by_aggregate(connection, release_id)
            aggregate_rows = connection.execute(
                """
                SELECT * FROM context_release_aggregates
                WHERE release_id = ? ORDER BY aggregate_key
                """,
                (release_id,),
            ).fetchall()
            result = []
            for aggregate in aggregate_rows:
                contribution_ids = self._decode(aggregate["contribution_ids_json"], [])
                contributions = []
                for contribution_id in contribution_ids:
                    row = connection.execute(
                        "SELECT * FROM context_contributions WHERE contribution_id = ?",
                        (contribution_id,),
                    ).fetchone()
                    if row is None:
                        continue
                    source = load_release_traceability_source(
                        connection, release_id, row["source_item_id"]
                    )
                    if source is None:
                        continue
                    contributions.append(
                        {
                            "contribution": self._contribution_from_row(row).model_dump(),
                            "source_item": source.model_dump(),
                        }
                    )
                synthesis_rows = connection.execute(
                    """
                    SELECT synthesis_id, context_key, content_json
                    FROM context_release_syntheses
                    WHERE release_id = ? AND aggregate_id = ?
                    ORDER BY context_key
                    """,
                    (release_id, aggregate["aggregate_id"]),
                ).fetchall()
                result.append(
                    {
                        "aggregate": {
                            "aggregate_id": aggregate["aggregate_id"],
                            "aggregate_type": aggregate["aggregate_type"],
                            "aggregate_key": aggregate["aggregate_key"],
                            "payload": self._decode(aggregate["payload_json"], {}),
                        },
                        "contributions": contributions,
                        "syntheses": [
                            {
                                "synthesis_id": row["synthesis_id"],
                                "context_key": row["context_key"],
                                "content": self._decode(row["content_json"], {}),
                            }
                            for row in synthesis_rows
                        ],
                        "delivery_membership": membership_counts.get(
                            aggregate["aggregate_id"], {"count": 0, "role_counts": {}},
                        ),
                    }
                )
            return result

    def list_release_delivery_memberships(self, release_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            return list_memberships(connection, release_id)

    def update_release(self, release_id: str, **changes: Any) -> None:
        del release_id, changes
        raise ImmutableContextReleaseError("Published context releases cannot be updated")

    def delete_release(self, release_id: str) -> None:
        del release_id
        raise ImmutableContextReleaseError("Published context releases cannot be deleted")
