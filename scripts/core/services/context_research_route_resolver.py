"""Apply explicit delivery decisions without conflating content or entities."""

from __future__ import annotations

from typing import Any

from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_shard_memo import (
    CollectedShardUnit,
    ShardMemoCollection,
)


_SCHEMA_VERSION = "context-research-delivery-resolver-v2"


def apply_delivery_routes(
    collection: ShardMemoCollection,
    findings: ContextResearchFindings | None = None,
) -> ContextResearchFindings:
    """Publish event/reference membership from the independent delivery axis."""

    source = findings or collection.findings
    actual = _actual_routes(source)
    resolutions = {
        unit.local_unit_id: _describe_unit(unit, actual.get(unit.local_unit_id, set()))
        for unit in collection.units
    }
    events, dropped_members, dropped_events = _filter_events(
        source.event_chains, resolutions,
    )
    assets, dropped_assets = _filter_assets(source.reference_assets, resolutions)
    diagnostics = dict(source.diagnostics or {})
    diagnostics["route_resolution"] = {
        "schema_version": _SCHEMA_VERSION,
        "units": [resolutions[key] for key in sorted(resolutions)],
        "content_roles": {
            key: item["content_role"] for key, item in sorted(resolutions.items())
        },
        "delivery_routes": {
            key: item["delivery_route"] for key, item in sorted(resolutions.items())
        },
        "route_without_matching_finding": sorted(
            key for key, item in resolutions.items()
            if item["delivery_route"] != "none"
            and item["delivery_route"] not in item["actual_finding_routes"]
        ),
        "dropped_event_members": dropped_members,
        "dropped_event_findings": dropped_events,
        "dropped_reference_assets": dropped_assets,
        "conflict_count_before": sum(
            1 for routes in actual.values() if len(routes) > 1
        ),
        "conflict_count_after": 0,
    }
    return source.model_copy(update={
        "event_chains": events,
        "reference_assets": assets,
        "diagnostics": diagnostics,
    })


def _actual_routes(findings: ContextResearchFindings) -> dict[str, set[str]]:
    actual: dict[str, set[str]] = {}
    for event in findings.event_chains:
        for unit_id in event.local_unit_ids:
            actual.setdefault(unit_id, set()).add("event")
    for asset in findings.reference_assets:
        if asset.local_unit_id:
            actual.setdefault(asset.local_unit_id, set()).add("reference")
    return actual


def _describe_unit(unit: CollectedShardUnit, actual: set[str]) -> dict[str, Any]:
    return {
        "local_unit_id": unit.local_unit_id,
        "content_role": unit.content_role,
        "delivery_route": unit.delivery_route,
        "confidence": unit.confidence,
        "actual_finding_routes": sorted(actual),
        "notes": unit.notes,
        "evidence": list(unit.evidence),
    }


def _filter_events(events, resolutions):
    output = []
    dropped_members: list[dict[str, Any]] = []
    dropped_events: list[str] = []
    for event in events:
        kept = tuple(
            unit_id for unit_id in event.local_unit_ids
            if resolutions.get(unit_id, {}).get("delivery_route") == "event"
        )
        dropped = tuple(unit_id for unit_id in event.local_unit_ids if unit_id not in kept)
        if dropped:
            dropped_members.append({
                "chain_id": event.chain_id,
                "sequence": event.sequence,
                "local_unit_ids": list(dropped),
            })
        if not kept:
            dropped_events.append(f"{event.chain_id}:{event.sequence}")
            continue
        output.append(event.model_copy(update={"local_unit_ids": kept}))
    return tuple(output), dropped_members, dropped_events


def _filter_assets(assets, resolutions):
    output = []
    dropped: list[str] = []
    for asset in assets:
        unit_id = asset.local_unit_id
        if unit_id is None or (
            resolutions.get(unit_id, {}).get("delivery_route") == "reference"
        ):
            output.append(asset)
        else:
            dropped.append(asset.asset_id)
    return tuple(output), dropped


def resolve_candidate_routes(
    collection: ShardMemoCollection,
    findings: ContextResearchFindings | None = None,
) -> ContextResearchFindings:
    """Compatibility wrapper for callers using the v1 function name."""

    return apply_delivery_routes(collection, findings)


__all__ = ["apply_delivery_routes", "resolve_candidate_routes"]
