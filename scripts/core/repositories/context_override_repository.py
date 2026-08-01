"""Persistence collaborator for immutable-release human override drafts."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.schemas.context import (
    ContextDraft,
    ContextRelease,
    ContextReleaseMetadata,
    HumanOverride,
)
from scripts.schemas.context_override import (
    MAX_CONTEXT_KEY_LENGTH,
    SaveContextOverrideRequest,
)


class ContextReleaseNotFoundError(LookupError):
    """The requested published release does not exist."""


class ContextDraftNotFoundError(LookupError):
    """The requested draft does not exist."""


class ContextOwnershipError(LookupError):
    """The requested release or draft belongs to another project."""


class ContextDraftClosedError(RuntimeError):
    """A published draft cannot be edited or published again."""


class ContextKeyNotFoundError(LookupError):
    """An override target is not part of the draft's parent release."""


class ContextOverrideValidationError(ValueError):
    """The submitted override is outside the bounded domain contract."""


class ContextOverrideRepository:
    """Own the small, transaction-sensitive normal-user override surface."""

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
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(value: str | None, fallback: Any) -> Any:
        if value is None:
            return deepcopy(fallback)
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)

    @classmethod
    def _draft_from_connection(
        cls, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> ContextDraft:
        overrides = connection.execute(
            """
            SELECT target_key, value_json, note
            FROM context_draft_overrides
            WHERE draft_id = ? ORDER BY target_key
            """,
            (row["draft_id"],),
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
                    value=cls._decode(item["value_json"], {}),
                    note=item["note"],
                )
                for item in overrides
            ],
        )

    @staticmethod
    def _draft_row(
        connection: sqlite3.Connection, draft_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM context_drafts WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            raise ContextDraftNotFoundError("Context draft not found")
        return row

    @staticmethod
    def _check_draft_project(row: sqlite3.Row, project_id: str) -> None:
        if row["project_id"] != project_id:
            raise ContextOwnershipError("Context draft does not belong to this project")

    @staticmethod
    def _check_open_draft(row: sqlite3.Row) -> None:
        if row["status"] != "draft":
            raise ContextDraftClosedError("Context draft has already been published")

    def create_draft(self, project_id: str, base_release_id: str) -> ContextDraft:
        """Create a draft and copy the parent release's existing overrides."""
        if not base_release_id or len(base_release_id) > 200:
            raise ContextReleaseNotFoundError("Context release not found")
        draft_id = str(uuid.uuid4())
        now = self._now()
        with self._lock, self._connect() as connection:
            parent = connection.execute(
                "SELECT project_id FROM context_releases WHERE release_id = ?",
                (base_release_id,),
            ).fetchone()
            if parent is None:
                raise ContextReleaseNotFoundError("Context release not found")
            if parent["project_id"] != project_id:
                raise ContextOwnershipError("Context release does not belong to this project")
            connection.execute(
                """
                INSERT INTO context_drafts
                    (draft_id, project_id, base_release_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (draft_id, project_id, base_release_id, now, now),
            )
            connection.execute(
                """
                INSERT INTO context_draft_overrides
                    (draft_id, target_key, value_json, note, updated_at)
                SELECT ?, target_key, value_json, note, ?
                FROM context_release_overrides
                WHERE release_id = ?
                """,
                (draft_id, now, base_release_id),
            )
            connection.commit()
            row = self._draft_row(connection, draft_id)
            return self._draft_from_connection(connection, row)

    def get_draft(self, project_id: str, draft_id: str) -> ContextDraft:
        with self._lock, self._connect() as connection:
            row = self._draft_row(connection, draft_id)
            self._check_draft_project(row, project_id)
            return self._draft_from_connection(connection, row)

    def save_override(
        self,
        project_id: str,
        draft_id: str,
        context_key: str,
        value: dict[str, Any],
        note: str | None,
    ) -> ContextDraft:
        """Save one override after checking it targets the immutable parent."""
        try:
            validated = SaveContextOverrideRequest(
                context_key=context_key,
                value=value,
                note=note,
            )
        except ValueError as error:
            raise ContextOverrideValidationError("Human override value is not valid") from error
        context_key = validated.context_key
        value = validated.value
        note = validated.note
        if len(context_key) > MAX_CONTEXT_KEY_LENGTH:
            raise ContextKeyNotFoundError("Context key is not valid")
        now = self._now()
        with self._lock, self._connect() as connection:
            draft = self._draft_row(connection, draft_id)
            self._check_draft_project(draft, project_id)
            self._check_open_draft(draft)
            exists = connection.execute(
                """
                SELECT 1 FROM context_release_syntheses
                WHERE release_id = ? AND context_key = ?
                """,
                (draft["base_release_id"], context_key),
            ).fetchone()
            if exists is None:
                raise ContextKeyNotFoundError("Context key is not in the parent release")
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
                (draft_id, context_key, self._json(value), note, now),
            )
            connection.execute(
                "UPDATE context_drafts SET updated_at = ? WHERE draft_id = ?",
                (now, draft_id),
            )
            connection.commit()
            return self._draft_from_connection(connection, self._draft_row(connection, draft_id))

    def publish_override_draft(self, project_id: str, draft_id: str) -> ContextRelease:
        """Publish a child by copying only the immutable parent release rows."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            draft = self._draft_row(connection, draft_id)
            self._check_draft_project(draft, project_id)
            self._check_open_draft(draft)
            parent_id = draft["base_release_id"]
            if not parent_id:
                raise ContextReleaseNotFoundError("Override drafts require a parent release")
            parent = connection.execute(
                "SELECT * FROM context_releases WHERE release_id = ?", (parent_id,)
            ).fetchone()
            if parent is None:
                raise ContextReleaseNotFoundError("Context release not found")
            if parent["project_id"] != draft["project_id"]:
                raise ContextOwnershipError("Context release does not belong to this project")
            release_id = str(uuid.uuid4())
            created_at = self._now()
            connection.execute(
                """
                INSERT INTO context_releases (
                    release_id, project_id, source_snapshot_hash, analysis_scope_json,
                    schema_version, prompt_version, provider_id, model_id,
                    analysis_config_json, created_at, parent_release_id, upstream_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    parent["project_id"],
                    parent["source_snapshot_hash"],
                    parent["analysis_scope_json"],
                    parent["schema_version"],
                    parent["prompt_version"],
                    parent["provider_id"],
                    parent["model_id"],
                    parent["analysis_config_json"],
                    created_at,
                    parent_id,
                    parent["upstream_version"],
                ),
            )
            connection.execute(
                """
                INSERT INTO context_release_aggregates (
                    release_id, aggregate_id, aggregate_type, aggregate_key,
                    payload_json, contribution_ids_json
                )
                SELECT ?, aggregate_id, aggregate_type, aggregate_key,
                       payload_json, contribution_ids_json
                FROM context_release_aggregates
                WHERE release_id = ?
                """,
                (release_id, parent_id),
            )
            parent_syntheses = connection.execute(
                """
                SELECT aggregate_id, context_key, content_json
                FROM context_release_syntheses
                WHERE release_id = ? ORDER BY context_key
                """,
                (parent_id,),
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO context_release_syntheses
                    (synthesis_id, release_id, aggregate_id, context_key, content_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        release_id,
                        row["aggregate_id"],
                        row["context_key"],
                        row["content_json"],
                    )
                    for row in parent_syntheses
                ],
            )
            connection.execute(
                """
                INSERT INTO context_release_overrides (release_id, target_key, value_json, note)
                SELECT ?, target_key, value_json, note
                FROM context_draft_overrides WHERE draft_id = ?
                """,
                (release_id, draft_id),
            )
            connection.execute(
                "UPDATE context_drafts SET status = 'published', updated_at = ? WHERE draft_id = ?",
                (created_at, draft_id),
            )
            connection.commit()
        return ContextRelease(
            release_id=release_id,
            project_id=parent["project_id"],
            metadata=ContextReleaseMetadata(
                source_snapshot_hash=parent["source_snapshot_hash"],
                analysis_scope=self._decode(parent["analysis_scope_json"], {}),
                schema_version=parent["schema_version"],
                prompt_version=parent["prompt_version"],
                provider_id=parent["provider_id"],
                model_id=parent["model_id"],
                analysis_config=self._decode(parent["analysis_config_json"], {}),
                created_at=created_at,
                parent_release_id=parent_id,
                upstream_version=parent["upstream_version"],
            ),
        )
