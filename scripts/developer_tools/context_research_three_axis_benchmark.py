"""Load and compare the three orthogonal Context Research axes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from scripts.developer_tools.context_archive_benchmark import parse_gold


CONTENT_ROLES = (
    "event_narrative", "background_narrative", "static_reference", "utility_or_noise",
)
DELIVERY_ROUTES = ("event", "reference", "none")


@dataclass(frozen=True)
class GoldUnitAxes:
    unit_id: str
    chain_id: str
    content_role: str
    delivery_route: str


@dataclass(frozen=True)
class ThreeAxisGold:
    units: Mapping[str, GoldUnitAxes]
    entity_names: frozenset[str]
    entity_unit_pairs: frozenset[tuple[str, str]]
    native_three_axis: bool


def load_three_axis_gold(path: Path) -> ThreeAxisGold:
    """Read the new JSON manifest, with an explicit legacy Markdown projection."""

    if path.suffix.casefold() != ".json":
        rows = parse_gold(path, {})
        units = {
            unit_id: GoldUnitAxes(
                unit_id=unit_id,
                chain_id=row.chain_id,
                content_role=_legacy_content_role(row.relation),
                delivery_route=_legacy_delivery_route(row.relation),
            )
            for unit_id, row in rows.items()
        }
        return ThreeAxisGold(units, frozenset(), frozenset(), False)
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("assignments") or document.get("units") or ()
    units: dict[str, GoldUnitAxes] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        unit_id = str(row.get("unit_id") or "")
        if not unit_id or unit_id in units:
            raise ValueError(f"Invalid or duplicate three-axis gold unit: {unit_id!r}")
        relation = str(row.get("relation") or "")
        content_role = str(row.get("content_role") or _legacy_content_role(relation))
        delivery_route = str(row.get("delivery_route") or _legacy_delivery_route(relation))
        if content_role not in CONTENT_ROLES:
            raise ValueError(f"Invalid content_role for {unit_id}: {content_role!r}")
        if delivery_route not in DELIVERY_ROUTES:
            raise ValueError(f"Invalid delivery_route for {unit_id}: {delivery_route!r}")
        units[unit_id] = GoldUnitAxes(
            unit_id=unit_id,
            chain_id=_gold_chain_id(row),
            content_role=content_role,
            delivery_route=delivery_route,
        )
    entities = document.get("entities") or document.get("entity_aggregates") or ()
    names: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for entity in entities if isinstance(entities, list) else ():
        if not isinstance(entity, Mapping):
            continue
        name = _normalize_name(entity.get("canonical_name") or entity.get("name"))
        if not name:
            continue
        names.add(name)
        unit_ids = (
            entity.get("source_unit_ids")
            or entity.get("source_units")
            or entity.get("local_unit_ids")
            or ()
        )
        pairs.update((name, str(unit_id)) for unit_id in unit_ids)
    native = bool(rows) and all(
        isinstance(row, Mapping) and "content_role" in row and "delivery_route" in row
        for row in rows
    )
    return ThreeAxisGold(units, frozenset(names), frozenset(pairs), native)


def predicted_unit_axes(draft: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    diagnostics = draft.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    model = diagnostics.get("model")
    model = model if isinstance(model, Mapping) else diagnostics
    resolution = model.get("route_resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    roles = _string_map(resolution.get("content_roles"))
    deliveries = _string_map(resolution.get("delivery_routes"))
    if roles or deliveries:
        return roles, deliveries
    event_units = {
        str(unit_id)
        for event in draft.get("event_chains") or ()
        for unit_id in event.get("local_unit_ids") or ()
    }
    reference_units = {
        str(asset.get("local_unit_id"))
        for asset in draft.get("reference_assets") or ()
        if asset.get("local_unit_id")
    }
    roles = {unit_id: "event_narrative" for unit_id in event_units}
    roles.update({unit_id: "static_reference" for unit_id in reference_units - event_units})
    deliveries = {unit_id: "event" for unit_id in event_units}
    deliveries.update({unit_id: "reference" for unit_id in reference_units - event_units})
    return roles, deliveries


def predicted_entities(
    draft: Mapping[str, Any],
    canonical_names: frozenset[str] | set[str] | None = None,
) -> tuple[set[str], set[tuple[str, str]]]:
    names: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for entity in draft.get("entities") or ():
        if not isinstance(entity, Mapping):
            continue
        surfaces = tuple(dict.fromkeys(
            _normalize_name(value)
            for value in (entity.get("name"), *(entity.get("aliases") or ()))
            if _normalize_name(value)
        ))
        name = next(
            (surface for surface in surfaces if canonical_names and surface in canonical_names),
            surfaces[0] if surfaces else "",
        )
        if not name:
            continue
        names.add(name)
        pairs.update((name, str(unit_id)) for unit_id in entity.get("local_unit_ids") or ())
    return names, pairs


def categorical_score(
    predicted: Mapping[str, str], expected: Mapping[str, str], labels: tuple[str, ...],
) -> dict[str, Any]:
    per_label: dict[str, dict[str, float | int]] = {}
    for label in labels:
        expected_ids = {key for key, value in expected.items() if value == label}
        predicted_ids = {key for key, value in predicted.items() if value == label}
        tp = len(expected_ids & predicted_ids)
        fp = len(predicted_ids - expected_ids)
        fn = len(expected_ids - predicted_ids)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": precision, "recall": recall, "f1": f1,
        }
    correct = sum(predicted.get(key) == value for key, value in expected.items())
    return {
        "accuracy": correct / len(expected) if expected else 0.0,
        "macro_f1": sum(item["f1"] for item in per_label.values()) / len(labels),
        "missing_unit_ids": sorted(set(expected) - set(predicted)),
        "per_label": per_label,
    }


def _legacy_content_role(relation: str) -> str:
    if relation in {"primary_member", "supporting_context", "narrative"}:
        return "event_narrative"
    if relation in {"archive_narrative", "parent_story_metadata", "theme_related"}:
        return "background_narrative"
    if relation in {"reference_asset", "reference"}:
        return "static_reference"
    return "utility_or_noise"


def _legacy_delivery_route(relation: str) -> str:
    if relation in {"primary_member", "supporting_context", "narrative"}:
        return "event"
    if relation in {"reference_asset", "reference"}:
        return "reference"
    return "none"


def _gold_chain_id(row: Mapping[str, Any]) -> str:
    memberships = row.get("chain_memberships")
    if isinstance(memberships, (list, tuple)) and memberships:
        return ";".join(sorted(str(item) for item in memberships if str(item)))
    return str(row.get("chain_id") or row.get("chain") or row.get("group_key") or "")


def _normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


__all__ = [
    "CONTENT_ROLES", "DELIVERY_ROUTES", "GoldUnitAxes", "ThreeAxisGold",
    "categorical_score", "load_three_axis_gold", "predicted_entities",
    "predicted_unit_axes",
]
