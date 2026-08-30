"""Pure projection and validation helpers for the v2 context tree.

The persisted analysis result is immutable.  Draft edits are represented as
small relationship operations and are applied to a detached dictionary before
the tree is returned or validated.  Keeping this logic independent from
SQLite makes the no-source-evidence-mutation boundary easy to test.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


EDITABLE_TARGETS = frozenset({
    "story",
    "group",
    "fragment_edge",
    "unit_route",
    "unresolved_reference",
})
EDITABLE_VALUE_KEYS = frozenset({
    "group_id",
    "position",
    "story_id",
    "title",
    "name",
    "label",
    "route",
    "reason",
    "status",
    "reference_type",
    "reference_id",
    "display_order",
    "summary",
    "before_fragment_id",
})
ROUTES = frozenset({"reference_asset", "narrative", "no_context"})


class TreeProjectionError(ValueError):
    """Raised when an edit cannot be applied to a v2 tree projection."""


def _copy_tree(tree: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(tree))
    for key in (
        "stories",
        "groups",
        "fragments",
        "fragment_edges",
        "unit_routes",
        "unresolved_references",
    ):
        result[key] = list(result.get(key) or [])
    return result


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dict(dump(mode="json"))
    raise TypeError("Tree projection items must be mappings or Pydantic models")


def _target_list(tree: dict[str, Any], target_type: str) -> list[dict[str, Any]]:
    key = {
        "story": "stories",
        "group": "groups",
        "fragment_edge": "fragment_edges",
        "unit_route": "unit_routes",
        "unresolved_reference": "unresolved_references",
    }.get(target_type)
    if key is None:
        raise TreeProjectionError(f"Unsupported tree edit target: {target_type}")
    values = [_as_dict(item) for item in tree.get(key, [])]
    tree[key] = values
    return values


def _identity(item: Mapping[str, Any], target_type: str) -> str:
    key = {
        "story": "story_id",
        "group": "group_id",
        "fragment_edge": "fragment_id",
        "unit_route": "unit_id",
        "unresolved_reference": "unresolved_id",
    }.get(target_type)
    if key is None:
        raise TreeProjectionError(f"Unsupported tree edit target: {target_type}")
    return str(item.get(key) or "")


def _find_item(values: list[dict[str, Any]], target_type: str, target_id: str) -> dict[str, Any] | None:
    return next((item for item in values if _identity(item, target_type) == target_id), None)


def _reject_source_fields(value: Mapping[str, Any]) -> None:
    forbidden = {
        "source", "source_evidence", "evidence", "content", "raw_text", "source_text",
        "full_source_text", "source_item_id", "batch_source", "digest_segment_id",
    }
    normalized = {str(key).strip().lower().replace("-", "_") for key in value}
    if normalized & forbidden:
        raise TreeProjectionError("Tree draft edits cannot change source evidence")
    unknown = normalized - EDITABLE_VALUE_KEYS
    if unknown:
        raise TreeProjectionError("Tree draft edits contain non-derived fields")


def _upsert(values: list[dict[str, Any]], target_type: str, item: dict[str, Any]) -> None:
    target_id = _identity(item, target_type)
    current = _find_item(values, target_type, target_id)
    if current is None:
        values.append(item)
    else:
        current.update(item)


def _apply_edge_edit(tree: dict[str, Any], target_id: str, operation: str, value: dict[str, Any]) -> None:
    edges = _target_list(tree, "fragment_edge")
    if operation in {"delete", "remove", "mark_unresolved"}:
        tree["fragment_edges"] = [item for item in edges if _identity(item, "fragment_edge") != target_id]
        _normalize_positions(tree)
        return
    group_id = value.get("group_id")
    if not group_id:
        raise TreeProjectionError("A fragment edge edit requires group_id")
    remaining = [item for item in edges if _identity(item, "fragment_edge") != target_id]
    current = {"fragment_id": target_id, "group_id": group_id, "position": len(remaining)}
    remaining.append(current)
    tree["fragment_edges"] = remaining
    _normalize_positions(tree)
    before_id = value.get("before_fragment_id")
    if before_id:
        _move_before(tree, target_id, group_id, str(before_id))
    elif "position" in value:
        current["position"] = value["position"]
        _normalize_positions(tree)


def _normalize_positions(tree: dict[str, Any]) -> None:
    edges = tree.get("fragment_edges", [])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        grouped.setdefault(str(edge.get("group_id") or ""), []).append(edge)
    for group_edges in grouped.values():
        group_edges.sort(key=lambda item: (item.get("position", 0), item.get("fragment_id", "")))
        for position, edge in enumerate(group_edges):
            edge["position"] = position


def _move_before(tree: dict[str, Any], fragment_id: str, group_id: str, before_id: str) -> None:
    edges = tree.get("fragment_edges", [])
    moving = next((item for item in edges if item.get("fragment_id") == fragment_id), None)
    before = next((item for item in edges if item.get("fragment_id") == before_id), None)
    if moving is None or before is None or before.get("group_id") != group_id:
        raise TreeProjectionError("before_fragment_id must identify a fragment in the target group")
    ordered = [item for item in edges if item.get("group_id") == group_id and item is not moving]
    other = [item for item in edges if item.get("group_id") != group_id]
    insertion = next(index for index, item in enumerate(ordered) if item is before)
    ordered.insert(insertion, moving)
    for position, edge in enumerate(ordered):
        edge["position"] = position
    tree["fragment_edges"] = other + ordered
    _normalize_positions(tree)


def _apply_container_edit(tree: dict[str, Any], target_type: str, target_id: str, operation: str, value: dict[str, Any]) -> None:
    values = _target_list(tree, target_type)
    current = _find_item(values, target_type, target_id)
    if operation in {"delete", "remove"}:
        tree[{
            "story": "stories",
            "group": "groups",
        }[target_type]] = [item for item in values if _identity(item, target_type) != target_id]
        if target_type == "group":
            tree["fragment_edges"] = [item for item in tree["fragment_edges"] if item.get("group_id") != target_id]
        return
    if operation in {"create", "upsert"} and current is None:
        item = {f"{target_type}_id": target_id}
        item.update(value)
        values.append(item)
        return
    if current is None:
        raise TreeProjectionError(f"Unknown {target_type}: {target_id}")
    for key, nested in value.items():
        if key in {"title", "name", "label", "story_id", "display_order", "summary"}:
            current[key] = nested


def _apply_route_edit(tree: dict[str, Any], target_id: str, operation: str, value: dict[str, Any]) -> None:
    routes = _target_list(tree, "unit_route")
    if operation in {"delete", "remove"}:
        tree["unit_routes"] = [item for item in routes if _identity(item, "unit_route") != target_id]
        return
    route = value.get("route")
    if route not in ROUTES:
        raise TreeProjectionError("Unit route must be reference_asset, narrative, or no_context")
    derived_fragments = [
        item.get("fragment_id")
        for item in tree.get("fragments", [])
        if target_id in (item.get("unit_ids") or [])
    ]
    current = _find_item(routes, "unit_route", target_id)
    if current is None:
        routes.append({
            "unit_id": target_id,
            "route": route,
            "fragment_ids": list(value.get("fragment_ids") or derived_fragments),
        })
    else:
        current["route"] = route
        if route != "narrative":
            current["fragment_ids"] = []
        elif value.get("fragment_ids"):
            current["fragment_ids"] = list(value.get("fragment_ids") or [])


def _apply_unresolved_edit(tree: dict[str, Any], target_id: str, operation: str, value: dict[str, Any]) -> None:
    values = _target_list(tree, "unresolved_reference")
    if operation in {"delete", "remove", "resolve"}:
        tree["unresolved_references"] = [item for item in values if _identity(item, "unresolved_reference") != target_id]
        return
    current = _find_item(values, "unresolved_reference", target_id)
    if current is None:
        item = {"unresolved_id": target_id, "reference_id": target_id}
        item.update(value)
        values.append(item)
    else:
        current.update({key: nested for key, nested in value.items() if key in {"reason", "status"}})


def _refresh_group_membership(tree: dict[str, Any]) -> None:
    groups = {str(item.get("group_id")): item for item in tree.get("groups", [])}
    for group in groups.values():
        group["fragment_ids"] = []
    for edge in sorted(
        tree.get("fragment_edges", []),
        key=lambda item: (str(item.get("group_id") or ""), item.get("position", 0)),
    ):
        group = groups.get(str(edge.get("group_id") or ""))
        if group is not None and edge.get("fragment_id"):
            group["fragment_ids"].append(edge["fragment_id"])


def apply_draft_overrides(tree: Mapping[str, Any], overrides: Iterable[Any]) -> dict[str, Any]:
    """Apply relationship-only edits in audit order to a detached tree copy."""
    projected = _copy_tree(tree)
    for raw_override in overrides:
        override = _as_dict(raw_override)
        target_type = str(override.get("target_type") or override.get("target_kind") or "")
        target_id = str(override.get("target_id") or "")
        operation = str(override.get("operation") or "upsert")
        value = dict(override.get("value") or {})
        if "operation_payload" in value:
            value = dict(value["operation_payload"] or {})
        if target_type not in EDITABLE_TARGETS or not target_id:
            raise TreeProjectionError("Tree draft override has an invalid target")
        _reject_source_fields(value)
        if target_type == "fragment_edge":
            _apply_edge_edit(projected, target_id, operation, value)
        elif target_type in {"story", "group"}:
            _apply_container_edit(projected, target_type, target_id, operation, value)
        elif target_type == "unit_route":
            _apply_route_edit(projected, target_id, operation, value)
        else:
            _apply_unresolved_edit(projected, target_id, operation, value)
        _refresh_group_membership(projected)
    return projected


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def validate_tree(tree: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic publication findings without changing the tree."""
    stories = [_as_dict(item) for item in tree.get("stories", [])]
    groups = [_as_dict(item) for item in tree.get("groups", [])]
    fragments = [_as_dict(item) for item in tree.get("fragments", [])]
    edges = [_as_dict(item) for item in tree.get("fragment_edges", [])]
    routes = [_as_dict(item) for item in tree.get("unit_routes", [])]
    unresolved = [_as_dict(item) for item in tree.get("unresolved_references", [])]
    issues: list[dict[str, Any]] = []
    story_ids = {_identity(item, "story") for item in stories}
    group_ids = {_identity(item, "group") for item in groups}
    fragment_ids = {str(item.get("fragment_id") or "") for item in fragments}
    if len(story_ids) != len(stories):
        issues.append(_issue("duplicate_story", "Story IDs must be unique"))
    if len(group_ids) != len(groups):
        issues.append(_issue("duplicate_group", "Group IDs must be unique"))
    if len(fragment_ids) != len(fragments):
        issues.append(_issue("duplicate_fragment", "Fragment IDs must be unique"))
    for group in groups:
        story_id = group.get("story_id")
        if story_id and story_id not in story_ids:
            issues.append(_issue("missing_story", "Group references a missing story", group_id=group.get("group_id")))
    edge_by_fragment: dict[str, list[dict[str, Any]]] = {}
    positions: set[tuple[str, int]] = set()
    for edge in edges:
        fragment_id = str(edge.get("fragment_id") or "")
        group_id = str(edge.get("group_id") or "")
        position = edge.get("position", 0)
        if fragment_id not in fragment_ids:
            issues.append(_issue("missing_fragment", "Fragment edge references a missing fragment", fragment_id=fragment_id))
        if group_id not in group_ids:
            issues.append(_issue("missing_group", "Fragment edge references a missing group", group_id=group_id))
        if not isinstance(position, int) or isinstance(position, bool) or position < 0:
            issues.append(_issue("invalid_position", "Fragment edge position must be a non-negative integer", fragment_id=fragment_id))
        elif (group_id, position) in positions:
            issues.append(_issue("duplicate_position", "Fragment positions must be unique within each group", group_id=group_id, position=position))
        else:
            positions.add((group_id, position))
        edge_by_fragment.setdefault(fragment_id, []).append(edge)
    unresolved_fragment_ids = {
        str(item.get("reference_id") or "")
        for item in unresolved
        if item.get("reference_type") == "fragment"
    }
    for fragment_id in sorted(fragment_ids):
        count = len(edge_by_fragment.get(fragment_id, []))
        if count != 1 and fragment_id not in unresolved_fragment_ids:
            issues.append(_issue("fragment_membership_incomplete", "Each fragment must have one group edge or an unresolved record", fragment_id=fragment_id))
        if count > 1:
            issues.append(_issue("fragment_multiple_groups", "A fragment cannot belong to multiple groups", fragment_id=fragment_id))
    route_ids = {str(item.get("unit_id") or "") for item in routes}
    for route in routes:
        if route.get("route") not in ROUTES:
            issues.append(_issue("invalid_unit_route", "Unit route is not supported", unit_id=route.get("unit_id")))
    for fragment in fragments:
        for unit_id in fragment.get("unit_ids") or []:
            if str(unit_id) not in route_ids:
                issues.append(_issue("missing_unit_route", "Fragment references a unit without a route", fragment_id=fragment.get("fragment_id"), unit_id=unit_id))
    issues.extend(_validate_required_digests(tree))
    return issues


def _validate_required_digests(tree: Mapping[str, Any]) -> list[dict[str, Any]]:
    digests = {
        str(item.get("entity_id") or ""): item
        for item in map(_as_dict, tree.get("entity_digests", []))
    }
    issues: list[dict[str, Any]] = []
    for candidate in map(_as_dict, tree.get("candidates", [])):
        if not candidate.get("summary_eligible"):
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        digest = digests.get(candidate_id, {})
        if not digest.get("final_digest") or digest.get("digest_provenance") != "final":
            issues.append(_issue(
                "required_entity_digest_incomplete",
                "Every A/B entity must have a complete final digest before publication",
                reference_id=candidate_id,
            ))
    return issues
