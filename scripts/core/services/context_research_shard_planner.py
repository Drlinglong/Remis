"""Pure deterministic local-unit shard planning for context research."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scripts.core.context_local_units import LocalTextUnit


DEFAULT_SHARD_CORE_UNITS = 12
DEFAULT_SHARD_OVERLAP_UNITS = 1
DEFAULT_SHARD_SOURCE_ITEMS = 20
DEFAULT_SHARD_CHARS = 6000
SHARD_REQUEST_BUDGET = 6
SHARD_TOOL_CALL_BUDGET = 12


def _unit_stats(unit: LocalTextUnit) -> dict[str, Any]:
    items = tuple(unit.items)
    orders = [
        int(item.source_order) for item in items
        if isinstance(getattr(item, "source_order", None), int)
    ]
    paths = list(dict.fromkeys(
        str(getattr(item, "relative_path", "")) for item in items
        if str(getattr(item, "relative_path", ""))
    ))
    source_ids = list(dict.fromkeys(
        str(getattr(item, "source_item_id", "")) for item in items
        if str(getattr(item, "source_item_id", ""))
    ))
    return {
        "source_item_count": len(source_ids),
        "source_item_ids": source_ids,
        "estimated_chars": sum(len(str(getattr(item, "source_text", ""))) for item in items),
        "source_order_range": [min(orders), max(orders)] if orders else None,
        "paths": paths,
    }


def build_investigation_shards(
    units: Sequence[LocalTextUnit],
    *,
    core_units: int = DEFAULT_SHARD_CORE_UNITS,
    overlap_units: int = DEFAULT_SHARD_OVERLAP_UNITS,
    max_source_items: int = DEFAULT_SHARD_SOURCE_ITEMS,
    max_chars: int = DEFAULT_SHARD_CHARS,
) -> list[dict[str, Any]]:
    """Partition ordered units without splitting a local family."""

    if core_units < 1 or overlap_units < 0 or max_source_items < 1 or max_chars < 1:
        raise ValueError("investigation shard limits must be positive")
    stats = tuple(_unit_stats(unit) for unit in units)
    records: list[dict[str, Any]] = []
    start = 0
    while start < len(units):
        core: list[int] = []
        source_count = 0
        estimated_chars = 0
        while start + len(core) < len(units):
            candidate_index = start + len(core)
            candidate = stats[candidate_index]
            if core and (
                len(core) >= core_units
                or source_count + candidate["source_item_count"] > max_source_items
                or estimated_chars + candidate["estimated_chars"] > max_chars
            ):
                break
            core.append(candidate_index)
            source_count += candidate["source_item_count"]
            estimated_chars += candidate["estimated_chars"]
        if not core:
            core = [start]
        overlap = list(range(max(0, core[0] - overlap_units), core[0]))
        records.append(_shard_record(
            len(records), units, stats, core, overlap,
            max_source_items=max_source_items, max_chars=max_chars,
        ))
        start = core[-1] + 1
    return records


def _aggregate(stats: Sequence[dict[str, Any]], indexes: Sequence[int]) -> dict[str, Any]:
    selected = [stats[index] for index in indexes]
    orders = [value for item in selected for value in (item["source_order_range"] or [])]
    paths = list(dict.fromkeys(path for item in selected for path in item["paths"]))
    source_ids = list(dict.fromkeys(
        source_id for item in selected for source_id in item["source_item_ids"]
    ))
    return {
        "local_unit_count": len(indexes),
        "source_item_count": len(source_ids),
        "source_item_ids": source_ids,
        "estimated_chars": sum(item["estimated_chars"] for item in selected),
        "source_order_range": [min(orders), max(orders)] if orders else None,
        "paths": paths,
    }


def _shard_record(
    index: int,
    units: Sequence[LocalTextUnit],
    stats: Sequence[dict[str, Any]],
    core_indexes: Sequence[int],
    overlap_indexes: Sequence[int],
    *,
    max_source_items: int,
    max_chars: int,
) -> dict[str, Any]:
    core = _aggregate(stats, core_indexes)
    overlap = _aggregate(stats, overlap_indexes)
    all_indexes = (*overlap_indexes, *core_indexes)
    core_ids = [units[item].unit_id for item in core_indexes]
    overlap_ids = [units[item].unit_id for item in overlap_indexes]
    all_ids = [units[item].unit_id for item in all_indexes]
    ownership = {
        unit_id: {"evidence_role": "owner", "owner_shard_id": f"investigation-{index:03d}"}
        for unit_id in core_ids
    }
    ownership.update({
        unit_id: {"evidence_role": "context_only", "owner_shard_id": None}
        for unit_id in overlap_ids
    })
    return {
        "shard_id": f"investigation-{index:03d}",
        "unit_index_range": [core_indexes[0], core_indexes[-1]],
        "core_local_unit_ids": core_ids,
        "overlap_local_unit_ids": overlap_ids,
        "local_unit_ids": all_ids,
        "ownership": ownership,
        "core_unit_key_hints": [units[item].unit_key.split("::", 1)[-1] for item in core_indexes],
        "core_source_item_ids": core["source_item_ids"],
        "overlap_source_item_ids": overlap["source_item_ids"],
        "core_source_item_count": core["source_item_count"],
        "overlap_source_item_count": overlap["source_item_count"],
        "source_item_count": len(dict.fromkeys((*core["source_item_ids"], *overlap["source_item_ids"]))),
        "source_order_range": {"core": core["source_order_range"], "overlap": overlap["source_order_range"]},
        "paths": core["paths"],
        "overlap_paths": overlap["paths"],
        "estimated_chars": core["estimated_chars"] + overlap["estimated_chars"],
        "core_estimated_chars": core["estimated_chars"],
        "within_core_read_budget": (
            core["source_item_count"] <= max_source_items and core["estimated_chars"] <= max_chars
        ),
        "oversized_local_unit_ids": [
            units[item].unit_id for item in core_indexes
            if stats[item]["source_item_count"] > max_source_items
            or stats[item]["estimated_chars"] > max_chars
        ],
        "read_budget": {
            "max_requests": SHARD_REQUEST_BUDGET,
            "max_tool_calls": SHARD_TOOL_CALL_BUDGET,
            "recommended_requests": 2,
            "recommended_tool_calls": 2,
        },
        "ownership_policy": "Only core_local_unit_ids own evidence; overlap_local_unit_ids are context only.",
    }


__all__ = [
    "DEFAULT_SHARD_CHARS", "DEFAULT_SHARD_CORE_UNITS", "DEFAULT_SHARD_OVERLAP_UNITS",
    "DEFAULT_SHARD_SOURCE_ITEMS", "SHARD_REQUEST_BUDGET", "SHARD_TOOL_CALL_BUDGET",
    "build_investigation_shards",
]
