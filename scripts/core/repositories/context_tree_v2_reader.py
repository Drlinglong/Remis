"""Read-only projections and publication validation for context tree v2."""

from __future__ import annotations

from typing import Any

from scripts.core.context_tree_v2_projection import apply_draft_overrides, validate_tree
from scripts.core.repositories.context_tree_v2_storage import (
    ContextTreeV2NotFoundError,
    ContextTreeV2OwnershipError,
    TreeV2StorageSupport,
)


class ContextTreeV2Reader(TreeV2StorageSupport):
    """Read immutable analysis rows and project an optional draft."""

    def _tree_payload(self, connection, project_id: str, tree_id: str) -> dict[str, Any]:
        root = self._tree_row(connection, project_id, tree_id)
        fragments = self._rows(connection, "context_tree_v2_fragments", "tree_id", tree_id, "fragment_id")
        routes = self._rows(connection, "context_tree_v2_unit_routes", "tree_id", tree_id, "unit_id")
        stories = self._rows(connection, "context_tree_v2_stories", "tree_id", tree_id, "story_id")
        groups = self._rows(connection, "context_tree_v2_groups", "tree_id", tree_id, "group_id")
        edges = self._rows(
            connection,
            "context_tree_v2_fragment_edges",
            "tree_id",
            tree_id,
            "group_id, position, fragment_id",
        )
        unresolved = self._rows(
            connection,
            "context_tree_v2_unresolved_references",
            "tree_id",
            tree_id,
            "unresolved_id",
        )
        return self._assemble_payload(root, fragments, routes, stories, groups, edges, unresolved)

    @staticmethod
    def _rows(connection, table: str, key: str, value: str, order: str) -> list[Any]:
        return connection.execute(
            f"SELECT * FROM {table} WHERE {key} = ? ORDER BY {order}", (value,)
        ).fetchall()

    @classmethod
    def _assemble_payload(
        cls, root, fragments, routes, stories, groups, edges, unresolved
    ) -> dict[str, Any]:
        edge_by_group: dict[str, list[Any]] = {}
        for row in edges:
            edge_by_group.setdefault(row["group_id"], []).append(row)
        group_map = {row["group_id"]: row for row in groups}
        return {
            "project_id": root["project_id"],
            "tree_id": root["tree_id"],
            "source_snapshot_hash": root["source_snapshot_hash"],
            "schema_version": root["schema_version"],
            "prompt_version": root["prompt_version"],
            "project_title": root["project_title"],
            "project_summary": root["project_summary"],
            "created_at": root["created_at"],
            "fragments": [cls._fragment_payload(row) for row in fragments],
            "unit_routes": [cls._route_payload(row, fragments, edges) for row in routes],
            "stories": [cls._story_payload(row, group_map) for row in stories],
            "groups": [cls._group_payload(row, edge_by_group.get(row["group_id"], [])) for row in groups],
            "fragment_edges": [cls._edge_payload(row) for row in edges],
            "unresolved_references": [cls._unresolved_payload(row) for row in unresolved],
            "entity_evidence": cls._decode(root["entity_evidence_json"], []),
            "entity_digests": cls._decode(root["entity_digests_json"], []),
        }

    @classmethod
    def _fragment_payload(cls, row) -> dict[str, Any]:
        boundary = cls._decode(row["boundary_json"], {})
        return {
            "fragment_id": row["fragment_id"],
            "summary": row["summary"],
            "unit_ids": cls._decode(row["unit_ids_json"], []),
            "continuation_clues": cls._decode(row["continuation_clues_json"], []),
            "boundary": boundary,
            "edge_metadata": boundary.get("edge_metadata", {}),
            "source_evidence": cls._decode(row["source_evidence_json"], []),
            "created_at": row["created_at"],
        }

    @classmethod
    def _route_payload(cls, row, fragments, edges) -> dict[str, Any]:
        metadata = cls._decode(row["entity_summary_json"], {})
        unit_id = row["unit_id"]
        fragment_ids = [
            fragment["fragment_id"]
            for fragment in fragments
            if unit_id in cls._decode(fragment["unit_ids_json"], [])
            and row["route"] == "narrative"
        ]
        return {
            "unit_id": unit_id,
            "route": row["route"],
            "fragment_ids": fragment_ids,
            "entity_summary": metadata.get("entity_summary", {}),
            "entity_evidence": metadata.get("entity_evidence", []),
            "entity_digests": metadata.get("entity_digests", []),
            "batch_sources": metadata.get("batch_sources", []),
        }

    @classmethod
    def _story_payload(cls, row, group_map) -> dict[str, Any]:
        metadata = cls._decode(row["description"], {})
        if not isinstance(metadata, dict):
            metadata = {"summary": row["description"]}
        return {
            "story_id": row["story_id"],
            "group_ids": sorted(
                group_id for group_id, group in group_map.items()
                if group["story_id"] == row["story_id"]
            ),
            "title": row["title"] or None,
            "summary": metadata.get("summary"),
        }

    @classmethod
    def _group_payload(cls, row, edges) -> dict[str, Any]:
        metadata = cls._decode(row["description"], {})
        if not isinstance(metadata, dict):
            metadata = {"summary": row["description"]}
        return {
            "group_id": row["group_id"],
            "story_id": row["story_id"],
            "fragment_ids": [edge["fragment_id"] for edge in sorted(edges, key=lambda item: item["position"])],
            "title": row["title"] or None,
            "summary": metadata.get("summary"),
        }

    @classmethod
    def _edge_payload(cls, row) -> dict[str, Any]:
        return {
            "group_id": row["group_id"],
            "fragment_id": row["fragment_id"],
            "position": row["position"],
        }

    @classmethod
    def _unresolved_payload(cls, row) -> dict[str, Any]:
        original = cls._decode(row["original_reference_json"], {})
        return {
            "reference_id": row["reference_id"],
            "reference_type": row["reference_type"],
            "source_id": row["source_id"],
            "target_id": original.get("target_id", row["reference_id"]),
            "reason": row["reason"],
            "repair_attempts": row["repair_attempts"],
            "repair_detail": row["repair_detail"],
        }

    def _overrides(self, connection, draft_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT target_type, target_id, operation, value_json, note,
                   sequence, created_at
            FROM context_tree_v2_draft_overrides
            WHERE draft_id = ? ORDER BY sequence, override_id
            """,
            (draft_id,),
        ).fetchall()
        return [self._override_payload(row) for row in rows]

    @classmethod
    def _override_payload(cls, row) -> dict[str, Any]:
        stored = cls._decode(row["value_json"], {})
        return {
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "operation": row["operation"],
            "value": stored.get("projection", stored),
            "note": row["note"],
            "sequence": row["sequence"],
            "created_at": row["created_at"],
            "operation_payload": stored.get("operation_payload", {}),
        }

    def get_tree(self, project_id: str, tree_id: str, draft_id: str | None = None) -> Any:
        with self._lock, self._connect() as connection:
            payload = self._tree_payload(connection, project_id, tree_id)
            if draft_id is not None:
                draft = self._draft_row(connection, draft_id)
                self._check_draft_project(draft, project_id)
                if draft["tree_id"] != tree_id:
                    raise ContextTreeV2OwnershipError("Draft does not belong to this tree")
                payload = apply_draft_overrides(payload, self._overrides(connection, draft_id))
                payload["draft_id"] = draft_id
                payload["draft_operations"] = [
                    item["operation_payload"] for item in self._overrides(connection, draft_id)
                ]
        return self._to_read_model(payload)

    read_tree = get_tree

    def get_latest_tree(self, project_id: str) -> Any:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT tree_id FROM context_tree_v2_trees WHERE project_id = ? "
                "ORDER BY created_at DESC, tree_id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if row is None:
            raise ContextTreeV2NotFoundError("No context tree v2 exists for this project")
        return self.get_tree(project_id, row["tree_id"])

    def get_release_tree(self, project_id: str, release_id: str) -> Any:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT tree_id FROM context_tree_v2_releases "
                "WHERE project_id = ? AND release_id = ?",
                (project_id, release_id),
            ).fetchone()
        if row is None:
            raise ContextTreeV2NotFoundError("Context tree v2 release not found")
        return self.get_tree(project_id, row["tree_id"])

    def _to_read_model(self, payload: dict[str, Any]) -> Any:
        groups = payload.get("groups", [])
        response = {
            "project_id": payload["project_id"],
            "tree_id": payload["tree_id"],
            "base_release_id": payload.get("source_snapshot_hash"),
            "draft_id": payload.get("draft_id"),
            "source_snapshot_hash": payload.get("source_snapshot_hash"),
            "schema_version": payload.get("schema_version"),
            "prompt_version": payload.get("prompt_version"),
            "project_title": payload.get("project_title"),
            "project_summary": payload.get("project_summary"),
            "created_at": payload.get("created_at"),
            "local_fragments": [self._to_fragment(item) for item in payload.get("fragments", [])],
            "unit_routes": [self._to_route(item) for item in payload.get("unit_routes", [])],
            "stories": [self._to_story(item, groups) for item in payload.get("stories", [])],
            "groups": [self._to_group(item) for item in groups],
            "fragment_edges": self._pair_edges(groups),
            "unresolved_references": [
                self._to_unresolved(item) for item in payload.get("unresolved_references", [])
            ],
            "entity_evidence": payload.get("entity_evidence", []),
            "entity_digests": payload.get("entity_digests", []),
            "draft_operations": [
                self._operation_model(item) for item in payload.get("draft_operations", [])
            ],
        }
        return self._model(("ReadTreeResponse", "ContextTreeReadResponse"), response)

    @staticmethod
    def _pair_edges(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for group in groups:
            fragments = list(group.get("fragment_ids") or [])
            for position in range(max(0, len(fragments) - 1)):
                result.append({
                    "edge_id": f"{group['group_id']}:{position}",
                    "group_id": group["group_id"],
                    "from_fragment_id": fragments[position],
                    "to_fragment_id": fragments[position + 1],
                    "position": position,
                })
        return result

    @staticmethod
    def _to_fragment(item: dict[str, Any]) -> dict[str, Any]:
        boundary = item.get("boundary") or {}
        return {
            "fragment_id": item["fragment_id"],
            "summary": item["summary"],
            "unit_ids": item.get("unit_ids", []),
            "continuation_clues": item.get("continuation_clues", []),
            "boundary_includes": boundary.get("includes"),
            "boundary_excludes": boundary.get("excludes"),
            "edge_metadata": item.get("edge_metadata", {}),
            "source_evidence_refs": item.get("source_evidence", []),
        }

    @staticmethod
    def _to_route(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "local_unit_id": item["unit_id"],
            "route": item["route"],
            "fragment_ids": item.get("fragment_ids", []),
            "entity_summary": item.get("entity_summary", {}),
            "entity_evidence": item.get("entity_evidence", []),
            "entity_digests": item.get("entity_digests", []),
        }

    @staticmethod
    def _to_story(item: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, Any]:
        group_ids = [group["group_id"] for group in groups if group.get("story_id") == item["story_id"]]
        return {"story_id": item["story_id"], "group_ids": group_ids, "title": item.get("title"), "summary": item.get("summary")}

    @staticmethod
    def _to_group(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "group_id": item["group_id"],
            "story_id": item.get("story_id"),
            "fragment_ids": item.get("fragment_ids", []),
            "title": item.get("title"),
            "summary": item.get("summary"),
        }

    @staticmethod
    def _to_unresolved(item: dict[str, Any]) -> dict[str, Any]:
        return {key: item.get(key) for key in ("reference_id", "reference_type", "source_id", "target_id", "reason", "repair_attempts", "repair_detail")}

    @classmethod
    def _operation_model(cls, item: Any) -> Any:
        if hasattr(item, "model_dump"):
            return item
        return cls._model(("TreeDraftOverrideOperation",), item)

    def get_draft(self, project_id: str, draft_id: str) -> Any:
        with self._lock, self._connect() as connection:
            row = self._draft_row(connection, draft_id)
            self._check_draft_project(row, project_id)
            payload = {
                "draft_id": draft_id,
                "project_id": project_id,
                "base_release_id": row["tree_id"],
                "tree_id": row["tree_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "operations": [
                    item["operation_payload"] for item in self._overrides(connection, draft_id)
                ],
            }
        return self._model(("TreeDraft", "ContextTreeDraft"), payload)

    def validate_draft(
        self,
        project_id: str,
        draft_id: str,
        *,
        reject_unresolved: bool = True,
        include_warnings: bool = True,
    ) -> Any:
        with self._lock, self._connect() as connection:
            draft = self._draft_row(connection, draft_id)
            self._check_draft_project(draft, project_id)
            payload = apply_draft_overrides(
                self._tree_payload(connection, project_id, draft["tree_id"]),
                self._overrides(connection, draft_id),
            )
        issues = list(validate_tree(payload))
        unresolved = payload.get("unresolved_references", [])
        if reject_unresolved:
            issues.extend(self._unresolved_issues(unresolved))
        errors = [self._validation_issue(item) for item in issues]
        return self._model(("PrePublicationValidationResult",), {
            "project_id": project_id,
            "tree_id": draft["tree_id"],
            "draft_id": draft_id,
            "valid": not errors,
            "errors": errors,
            "warnings": [] if include_warnings else [],
            "unresolved_references": [self._to_unresolved(item) for item in unresolved],
            "fragment_count": len(payload.get("fragments", [])),
            "group_count": len(payload.get("groups", [])),
            "edge_count": len(payload.get("fragment_edges", [])),
            "unit_route_count": len(payload.get("unit_routes", [])),
            "checked_at": self._now(),
        })

    @staticmethod
    def _unresolved_issues(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "code": "unresolved_reference",
                "message": "Unresolved references must be repaired before publication",
                "reference_id": item.get("reference_id"),
            }
            for item in values
        ]

    @staticmethod
    def _validation_issue(item: dict[str, Any]) -> dict[str, Any]:
        references = [
            str(item[key])
            for key in ("fragment_id", "group_id", "unit_id", "reference_id")
            if item.get(key)
        ]
        return {
            "code": item["code"],
            "severity": "error",
            "message": item["message"],
            "reference_ids": references,
        }


__all__ = ["ContextTreeV2Reader"]
