"""Write commands for immutable context tree v2 rows and draft overrides."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Iterable, Mapping

from scripts.core.context_tree_v2_projection import (
    TreeProjectionError,
    apply_draft_overrides,
    validate_tree,
)
from scripts.core.repositories.context_tree_v2_reader import ContextTreeV2Reader
from scripts.core.repositories.context_tree_v2_storage import (
    ContextTreeV2ConflictError,
    ContextTreeV2NotFoundError,
    ContextTreeV2ValidationError,
    TreeV2StorageSupport,
)


class ContextTreeV2Writer(TreeV2StorageSupport):
    """Persist source-grounded tree data and append relationship-only edits."""

    def save_tree(self, tree: Any) -> Any:
        payload = self._dump(tree)
        project_id, tree_id = self._tree_key(payload)
        source_hash = str(payload.get("source_snapshot_hash") or tree_id)
        now = payload.get("created_at") or self._now()
        with self._lock, self._connect() as connection:
            if not self._find_project(connection, project_id):
                raise ContextTreeV2NotFoundError("Project not found")
            try:
                self._ensure_root(connection, payload, project_id, tree_id, source_hash, now)
                routes = self._insert_routes(connection, tree_id, payload.get("unit_routes", []))
                self._insert_fragments(connection, tree_id, payload, routes, now)
                self._insert_stories(connection, tree_id, payload.get("stories", []), now)
                self._insert_groups(connection, tree_id, payload.get("groups", []), now)
                self._insert_edges(connection, tree_id, payload, now)
                self._insert_unresolved(connection, tree_id, payload.get("unresolved_references", []))
                connection.commit()
            except (ContextTreeV2NotFoundError, ContextTreeV2ValidationError, ValueError):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ContextTreeV2ConflictError("Context tree v2 conflicts with existing data") from error
        return ContextTreeV2Reader(self.db_path).get_tree(project_id, tree_id)

    create_tree = save_tree

    def _ensure_root(
        self, connection, payload: Mapping[str, Any], project_id: str, tree_id: str, source_hash: str, now: str
    ) -> None:
        values = {
            "source_snapshot_hash": source_hash,
            "schema_version": payload.get("schema_version") or "context-tree-v2",
            "prompt_version": payload.get("prompt_version") or "context-tree-v2",
            "project_title": payload.get("project_title"),
            "project_summary": payload.get("project_summary"),
            "entity_evidence_json": self._json(payload.get("entity_evidence", [])),
            "entity_digests_json": self._json(payload.get("entity_digests", [])),
            "candidates_json": self._json(payload.get("candidates", [])),
            "term_variants_json": self._json(payload.get("term_variants", [])),
        }
        existing = connection.execute(
            "SELECT * FROM context_tree_v2_trees WHERE tree_id = ?", (tree_id,)
        ).fetchone()
        if existing is not None:
            if existing["project_id"] != project_id or any(
                existing[key] != value for key, value in values.items()
                if key in existing.keys()
            ):
                raise ContextTreeV2ConflictError("Context tree v2 source rows are immutable")
            return
        connection.execute(
            """
            INSERT INTO context_tree_v2_trees
                (tree_id, project_id, source_snapshot_hash, schema_version,
                 prompt_version, project_title, entity_evidence_json,
                 entity_digests_json, candidates_json, term_variants_json,
                 project_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tree_id,
                project_id,
                values["source_snapshot_hash"],
                values["schema_version"],
                values["prompt_version"],
                values["project_title"],
                values["entity_evidence_json"],
                values["entity_digests_json"],
                values["candidates_json"],
                values["term_variants_json"],
                values["project_summary"],
                now,
            ),
        )

    def _insert_routes(self, connection, tree_id: str, values: Iterable[Any]) -> dict[str, dict[str, Any]]:
        route_map: dict[str, dict[str, Any]] = {}
        for item in values:
            value = self._dump(item)
            unit_id = self._require_text(value.get("local_unit_id") or value.get("unit_id"), "local_unit_id")
            route = self._require_text(value.get("route"), "route")
            fragment_ids = list(value.get("fragment_ids") or [])
            if route not in {"narrative", "reference_asset", "no_context"}:
                raise ValueError(f"Unsupported unit route: {route}")
            if route != "narrative" and fragment_ids:
                raise ValueError("Non-narrative routes cannot carry fragment IDs")
            if unit_id in route_map:
                raise ValueError(f"Duplicate unit route: {unit_id}")
            route_map[unit_id] = value
            metadata = {
                "entity_summary": value.get("entity_summary", {}),
                "entity_evidence": value.get("entity_evidence", []),
                "entity_digests": value.get("entity_digests", []),
                "batch_sources": value.get("batch_sources", []),
                "metadata": value.get("metadata", {}),
            }
            connection.execute(
                """
                INSERT OR IGNORE INTO context_tree_v2_unit_routes
                    (tree_id, unit_id, route, route_reason, entity_summary_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tree_id, unit_id, route, value.get("route_reason"), self._json(metadata), self._now()),
            )
        return route_map

    def _insert_fragments(
        self, connection, tree_id: str, payload: Mapping[str, Any], routes: Mapping[str, Any], now: str
    ) -> None:
        values = payload.get("local_fragments", payload.get("fragments", []))
        for item in values:
            value = self._dump(item)
            fragment_id = self._require_text(value.get("fragment_id"), "fragment_id")
            unit_ids = list(value.get("unit_ids") or value.get("local_unit_ids") or [])
            missing = [unit_id for unit_id in unit_ids if unit_id not in routes]
            if missing:
                raise ValueError(f"Fragment {fragment_id} references units without routes: {missing}")
            boundary = value.get("boundary") or {
                "includes": value.get("boundary_includes"),
                "excludes": value.get("boundary_excludes"),
                "edge_metadata": value.get("edge_metadata") or {},
            }
            evidence = value.get("source_evidence_refs", value.get("source_evidence", []))
            connection.execute(
                """
                INSERT OR IGNORE INTO context_tree_v2_fragments
                    (tree_id, fragment_id, summary, unit_ids_json,
                     continuation_clues_json, boundary_json, source_evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tree_id,
                    fragment_id,
                    self._require_text(value.get("summary"), "fragment summary"),
                    self._json(unit_ids),
                    self._json(value.get("continuation_clues", [])),
                    self._json(boundary),
                    self._json(evidence),
                    value.get("created_at") or now,
                ),
            )

    def _insert_stories(self, connection, tree_id: str, values: Iterable[Any], now: str) -> None:
        for item in values:
            value = self._dump(item)
            story_id = self._require_text(value.get("story_id"), "story_id")
            title = value.get("title") or value.get("name") or story_id
            description = self._json({"summary": value.get("summary")})
            connection.execute(
                """
                INSERT OR IGNORE INTO context_tree_v2_stories
                    (tree_id, story_id, title, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tree_id, story_id, title, description, value.get("created_at") or now),
            )

    def _insert_groups(self, connection, tree_id: str, values: Iterable[Any], now: str) -> None:
        story_ids = {
            row[0] for row in connection.execute(
                "SELECT story_id FROM context_tree_v2_stories WHERE tree_id = ?", (tree_id,)
            ).fetchall()
        }
        for item in values:
            value = self._dump(item)
            group_id = self._require_text(value.get("group_id"), "group_id")
            story_id = value.get("story_id")
            if story_id is not None and story_id not in story_ids:
                raise ValueError(f"Group {group_id} references an unknown story: {story_id}")
            title = value.get("title") or value.get("name") or group_id
            description = self._json({"summary": value.get("summary")})
            connection.execute(
                """
                INSERT OR IGNORE INTO context_tree_v2_groups
                    (tree_id, group_id, story_id, title, description, display_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tree_id,
                    group_id,
                    story_id,
                    title,
                    description,
                    value.get("display_order"),
                    value.get("created_at") or now,
                ),
            )

    def _insert_edges(self, connection, tree_id: str, payload: Mapping[str, Any], now: str) -> None:
        groups = {self._dump(item)["group_id"]: self._dump(item) for item in payload.get("groups", [])}
        explicit = [self._dump(item) for item in payload.get("fragment_edges", [])]
        fragments = {
            row[0] for row in connection.execute(
                "SELECT fragment_id FROM context_tree_v2_fragments WHERE tree_id = ?", (tree_id,)
            ).fetchall()
        }
        for group_id, group in groups.items():
            ordered = list(group.get("fragment_ids") or [])
            if not ordered:
                ordered = self._edge_sequence(group_id, explicit)
            for position, fragment_id in enumerate(ordered):
                if fragment_id not in fragments:
                    raise ValueError(f"Group {group_id} references an unknown fragment: {fragment_id}")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO context_tree_v2_fragment_edges
                        (tree_id, group_id, fragment_id, position, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tree_id, group_id, fragment_id, position, now),
                )

    @staticmethod
    def _edge_sequence(group_id: str, values: list[dict[str, Any]]) -> list[str]:
        scoped = [item for item in values if item.get("group_id") == group_id]
        membership = [item for item in scoped if item.get("fragment_id")]
        if membership:
            membership.sort(key=lambda item: (item.get("position", 0), item.get("fragment_id", "")))
            return list(dict.fromkeys(item["fragment_id"] for item in membership))
        sequence: list[str] = []
        for item in sorted(scoped, key=lambda value: value.get("position", 0)):
            for key in ("from_fragment_id", "to_fragment_id"):
                fragment_id = item.get(key)
                if fragment_id and fragment_id not in sequence:
                    sequence.append(fragment_id)
        return sequence

    def _insert_unresolved(self, connection, tree_id: str, values: Iterable[Any]) -> None:
        for item in values:
            value = self._dump(item)
            reference_id = self._require_text(
                value.get("reference_id") or value.get("unresolved_id"), "reference_id"
            )
            target_id = self._require_text(value.get("target_id") or reference_id, "target_id")
            reason = self._require_text(value.get("reason") or value.get("reason_code"), "reason")
            original = dict(value.get("original_reference") or {})
            original.setdefault("target_id", target_id)
            connection.execute(
                """
                INSERT OR IGNORE INTO context_tree_v2_unresolved_references
                    (tree_id, unresolved_id, source_kind, source_id, reference_type,
                     reference_id, reason, original_reference_json, repair_attempts,
                     repair_detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tree_id,
                    reference_id,
                    value.get("source_kind") or value.get("reference_type") or "unknown",
                    self._require_text(value.get("source_id"), "unresolved source_id"),
                    self._require_text(value.get("reference_type"), "reference_type"),
                    reference_id,
                    reason,
                    self._json(original),
                    value.get("repair_attempts", 0),
                    value.get("repair_detail"),
                    value.get("created_at") or self._now(),
                ),
            )

    def create_draft(self, project_id: str, tree_id: str) -> Any:
        with self._lock, self._connect() as connection:
            self._tree_row(connection, project_id, tree_id)
            draft_id = str(uuid.uuid4())
            now = self._now()
            connection.execute(
                """
                INSERT INTO context_tree_v2_drafts
                    (draft_id, tree_id, project_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (draft_id, tree_id, project_id, now, now),
            )
            connection.commit()
        return ContextTreeV2Reader(self.db_path).get_draft(project_id, draft_id)

    start_draft = create_draft

    def save_draft_operation(self, project_id: str, draft_id: str, operation: Any) -> Any:
        return self.save_draft_overrides(project_id, draft_id, [operation])

    save_draft_override = save_draft_operation
    save_override = save_draft_operation

    def save_draft_overrides(self, project_id: str, draft_id: str, overrides: Iterable[Any]) -> Any:
        values = [self._dump(operation) for operation in overrides]
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            draft = self._draft_row(connection, draft_id)
            self._check_draft_project(draft, project_id)
            self._check_open_draft(draft)
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), -1) + 1 FROM context_tree_v2_draft_overrides WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()[0]
            try:
                for offset, value in enumerate(values):
                    target_type, target_id, db_operation, projection = self._operation_projection(value)
                    stored = {"projection": projection, "operation_payload": value}
                    connection.execute(
                        """INSERT INTO context_tree_v2_draft_overrides
                           (draft_id, sequence, target_type, target_id, operation,
                            value_json, note, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            draft_id, sequence + offset, target_type, target_id,
                            db_operation, self._json(stored), value.get("note"), self._now(),
                        ),
                    )
                base = ContextTreeV2Reader(self.db_path)._tree_payload(
                    connection, project_id, draft["tree_id"]
                )
                rows = ContextTreeV2Reader(self.db_path)._overrides(connection, draft_id)
                apply_draft_overrides(base, rows)
            except (TreeProjectionError, TypeError, ValueError) as error:
                connection.rollback()
                raise ContextTreeV2ValidationError(str(error)) from error
            connection.execute(
                "UPDATE context_tree_v2_drafts SET updated_at = ? WHERE draft_id = ?",
                (self._now(), draft_id),
            )
            connection.commit()
        return ContextTreeV2Reader(self.db_path).get_draft(project_id, draft_id)

    @classmethod
    def _operation_projection(cls, value: Mapping[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
        operation = cls._require_text(value.get("operation"), "operation")
        field_targets = {
            "create_story": ("story", value.get("story_id")),
            "add_story": ("story", value.get("story_id")),
            "rename_story": ("story", value.get("story_id")),
            "delete_story": ("story", value.get("story_id")),
            "remove_story": ("story", value.get("story_id")),
            "create_group": ("group", value.get("group_id")),
            "add_group": ("group", value.get("group_id")),
            "rename_group": ("group", value.get("group_id")),
            "delete_group": ("group", value.get("group_id")),
            "remove_group": ("group", value.get("group_id")),
            "move_fragment": ("fragment_edge", value.get("fragment_id")),
            "reorder_fragment": ("fragment_edge", value.get("fragment_id")),
            "set_unit_route": ("unit_route", value.get("local_unit_id")),
            "mark_unresolved": ("unresolved_reference", value.get("reference_id")),
            "resolve_reference": ("unresolved_reference", value.get("reference_id")),
            "update_derived_summary": ("group", value.get("target_id")),
        }
        target_type, target_id = field_targets.get(operation, ("", None))
        target_id = cls._require_text(target_id, "operation target")
        db_operation = cls._database_operation(operation)
        return target_type, target_id, db_operation, cls._projection_value(operation, value)

    @staticmethod
    def _database_operation(operation: str) -> str:
        if operation in {"create_story", "add_story", "create_group", "add_group"}:
            return "create"
        if operation in {"delete_story", "remove_story", "delete_group", "remove_group"}:
            return "delete"
        if operation == "move_fragment":
            return "move"
        if operation == "reorder_fragment":
            return "reorder"
        if operation == "resolve_reference":
            return "resolve"
        return "update"

    @staticmethod
    def _projection_value(operation: str, value: Mapping[str, Any]) -> dict[str, Any]:
        if operation == "move_fragment":
            return {"group_id": value["target_group_id"], "before_fragment_id": value.get("before_fragment_id")}
        if operation == "reorder_fragment":
            return {"group_id": value["group_id"], "before_fragment_id": value.get("before_fragment_id")}
        if operation == "set_unit_route":
            return {"route": value["route"], "fragment_ids": value.get("fragment_ids", [])}
        if operation in {"rename_story", "rename_group", "create_story", "add_story", "create_group", "add_group"}:
            result = {"title": value.get("new_name")}
            if operation in {"create_group", "add_group"}:
                result["story_id"] = value.get("story_id")
            return result
        if operation == "update_derived_summary":
            return {"summary": value.get("derived_summary")}
        if operation == "mark_unresolved":
            return {
                "reference_type": "fragment",
                "source_id": value.get("target_id"),
                "target_id": value.get("target_id"),
                "reference_id": value.get("reference_id"),
                "reason": value.get("reason"),
            }
        return {}

    def publish_draft(self, project_id: str, draft_id: str, *, idempotency_key: str | None = None) -> Any:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            draft = self._draft_row(connection, draft_id)
            self._check_draft_project(draft, project_id)
            payload = apply_draft_overrides(
                ContextTreeV2Reader(self.db_path)._tree_payload(
                    connection, project_id, draft["tree_id"],
                ),
                ContextTreeV2Reader(self.db_path)._overrides(connection, draft_id),
            )
            issues = list(validate_tree(payload))
            if payload.get("unresolved_references"):
                issues.append({
                    "code": "unresolved_reference",
                    "message": "Unresolved references must be repaired before publication",
                })
            if issues:
                connection.rollback()
                raise ContextTreeV2ValidationError(
                    "Context tree v2 draft is not publishable", issues=issues,
                )
            existing = None
            if idempotency_key:
                existing = connection.execute(
                    "SELECT * FROM context_tree_v2_releases WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
            if existing is not None:
                if existing["draft_id"] != draft_id or existing["project_id"] != project_id:
                    raise ContextTreeV2ConflictError("Release idempotency key belongs to another draft")
                return self._model(("TreeRelease",), self._row_dict(existing))
            if draft["status"] != "draft":
                existing = connection.execute(
                    "SELECT * FROM context_tree_v2_releases WHERE draft_id = ?", (draft_id,)
                ).fetchone()
                if existing is not None:
                    return self._model(("TreeRelease",), self._row_dict(existing))
                self._check_open_draft(draft)
            release_id = str(uuid.uuid4())
            now = self._now()
            connection.execute(
                """
                INSERT INTO context_tree_v2_releases
                    (release_id, tree_id, draft_id, project_id, idempotency_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (release_id, draft["tree_id"], draft_id, project_id, idempotency_key, now),
            )
            connection.execute(
                "UPDATE context_tree_v2_drafts SET status = 'published', updated_at = ? WHERE draft_id = ?",
                (now, draft_id),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM context_tree_v2_releases WHERE release_id = ?", (release_id,)
            ).fetchone()
        return self._row_dict(row)

    publish_tree_draft = publish_draft
    approve_draft = publish_draft


__all__ = ["ContextTreeV2Writer"]
