"""Translate immutable tree-v2 releases into the shared selection index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scripts.core.repositories.context_tree_v2_storage import ContextTreeV2NotFoundError
from scripts.core.services.source_snapshot_service import (
    normalize_relative_path,
    normalize_source_key,
)


@dataclass(frozen=True)
class TreeV2ContextProjection:
    release_id: str
    source_snapshot_hash: str
    project_summary: tuple[dict[str, Any], ...]
    direct_index: dict[tuple[str, str], tuple[dict[str, Any], ...]]


class ContextTreeV2TranslationAdapter:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def resolve(
        self, project_id: str, requested_release_id: str | None,
    ) -> TreeV2ContextProjection | None:
        try:
            tree = (
                self.repository.get_release_tree(project_id, requested_release_id)
                if requested_release_id
                else self.repository.get_latest_release_tree(project_id)
            )
        except ContextTreeV2NotFoundError:
            return None
        payload = tree.model_dump(mode="json")
        return self._project(payload)

    @classmethod
    def _project(cls, tree: Mapping[str, Any]) -> TreeV2ContextProjection:
        project_summary = ()
        if tree.get("project_summary"):
            project_summary = ({
                "context_key": f"project:{tree['project_id']}",
                "aggregate_type": "project",
                "summary": {"text": tree["project_summary"]},
            },)
        fragments = {
            item["fragment_id"]: item for item in tree.get("local_fragments", [])
        }
        group_by_fragment = {
            fragment_id: group
            for group in tree.get("groups", [])
            for fragment_id in group.get("fragment_ids", [])
        }
        direct: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for route in tree.get("unit_routes", []):
            if route.get("route") != "narrative":
                continue
            cls._add_route_context(route, fragments, group_by_fragment, direct)
        cls._add_entity_context(tree, direct)
        return TreeV2ContextProjection(
            release_id=str(tree["release_id"]),
            source_snapshot_hash=str(tree["source_snapshot_hash"]),
            project_summary=project_summary,
            direct_index={
                key: tuple(cls._unique_contexts(values)) for key, values in direct.items()
            },
        )

    @classmethod
    def _add_route_context(
        cls,
        route: Mapping[str, Any],
        fragments: Mapping[str, Mapping[str, Any]],
        group_by_fragment: Mapping[str, Mapping[str, Any]],
        direct: dict[tuple[str, str], list[dict[str, Any]]],
    ) -> None:
        unit_id = route.get("local_unit_id") or route.get("unit_id")
        for fragment_id in route.get("fragment_ids", []):
            fragment = fragments.get(fragment_id)
            group = group_by_fragment.get(fragment_id)
            if not fragment or not group:
                continue
            item = cls._group_context(group, fragments)
            for evidence in fragment.get("source_evidence_refs", []):
                if evidence.get("local_unit_id") != unit_id:
                    continue
                identity = cls._identity(evidence)
                if identity:
                    direct.setdefault(identity, []).append(item)

    @staticmethod
    def _group_context(
        group: Mapping[str, Any], fragments: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        bullets = [
            fragments[fragment_id]["summary"]
            for fragment_id in group.get("fragment_ids", [])
            if fragment_id in fragments
        ]
        return {
            "context_key": f"event_group:{group['group_id']}",
            "aggregate_type": "event",
            "summary": {"summary_bullets": bullets},
        }

    @classmethod
    def _add_entity_context(
        cls, tree: Mapping[str, Any], direct: dict[tuple[str, str], list[dict[str, Any]]],
    ) -> None:
        digests = {
            item["entity_id"]: item for item in tree.get("entity_digests", [])
            if item.get("final_digest") and item.get("level") in {"A", "B"}
        }
        for evidence in tree.get("entity_evidence", []):
            digest = digests.get(evidence.get("entity_id"))
            identity = cls._identity(evidence)
            if not digest or not identity:
                continue
            direct.setdefault(identity, []).append({
                "context_key": str(digest["entity_id"]),
                "aggregate_type": "entity",
                "summary": {"summary": digest["final_digest"]},
            })

    @staticmethod
    def _identity(value: Mapping[str, Any]) -> tuple[str, str] | None:
        try:
            path = normalize_relative_path(
                value.get("source_ref") or value.get("relative_path") or ""
            )
            key = normalize_source_key(value.get("item_key"))
        except ValueError:
            return None
        return (path, key) if key else None

    @staticmethod
    def _unique_contexts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list({str(item["context_key"]): item for item in values}.values())


__all__ = ["ContextTreeV2TranslationAdapter", "TreeV2ContextProjection"]
