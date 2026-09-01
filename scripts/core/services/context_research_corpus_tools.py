"""Request-bound corpus facade for the developer research harness."""

from __future__ import annotations

from collections.abc import Sequence
from collections import Counter
import json
import re
from typing import Any

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.services.context_research_corpus_reader import (
    CorpusReader, CorpusSourceItem, CorpusToolLimits, InMemoryCorpus,
    MAX_ALLOWED_TOTAL_CHARS, ReadOnlyRemisCorpusTools, bounded_text, normalize_source_item,
)
from scripts.core.services.context_research_ids import ShortIdRegistry
from scripts.core.services.context_research_ownership import OwnedShardCorpusView, ShardLease
from scripts.core.services.context_research_shard_planner import (
    DEFAULT_SHARD_CHARS, DEFAULT_SHARD_CORE_UNITS, DEFAULT_SHARD_OVERLAP_UNITS,
    DEFAULT_SHARD_SOURCE_ITEMS, SHARD_REQUEST_BUDGET, SHARD_TOOL_CALL_BUDGET,
    build_investigation_shards,
)


class BoundCorpusTools:
    """Request-scoped facade with deterministic units and shard plans."""

    def __init__(
        self,
        tools: ReadOnlyRemisCorpusTools,
        project_id: str,
        source_item_ids: Sequence[str] | None,
        source_items: Sequence[Any] | None = None,
    ) -> None:
        self._tools = tools
        self._project_id = project_id
        self._source_item_ids = tuple(dict.fromkeys(
            str(item).strip() for item in source_item_ids or () if str(item).strip()
        ))
        if not self._source_item_ids:
            raise ValueError("BoundCorpusTools requires a non-empty source snapshot")
        materialized = tuple(
            normalize_source_item(item) for item in (source_items or ())
            if _source_id(item) in self._source_item_ids
        )
        if not materialized:
            materialized = tuple(self._tools._items(  # noqa: SLF001
                self._project_id, self._source_item_ids,
            ))
        self._source_items = materialized
        self._local_units = ContextLocalUnitBuilder.build(materialized)
        self._local_unit_by_id = {unit.unit_id: unit for unit in self._local_units}
        self._id_registry = ShortIdRegistry.from_snapshot(
            [item.source_item_id for item in self._source_items],
            [unit.unit_id for unit in self._local_units],
        )

    @property
    def limits(self) -> CorpusToolLimits:
        return self._tools.limits

    @property
    def materialized_source_items(self) -> tuple[Any, ...]:
        """Host-only canonical snapshot used to normalize ID-only requests."""

        return self._source_items

    @property
    def id_registry(self) -> ShortIdRegistry:
        """Request-local aliases; canonical IDs never leave host persistence."""

        return self._id_registry

    def investigation_manifest(self) -> tuple[dict[str, Any], ...]:
        """Host-only complete ownership manifest; never registered as a model tool."""

        return tuple(build_investigation_shards(self._local_units))

    def list_source_items(
        self, offset: int = 0, path: str | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        _require_offset(offset)
        items = tuple(item for item in self._source_items if _path_matches(path, item))
        records = [self._tools._record(item, include_text=False) for item in items[offset:]]  # noqa: SLF001
        records = records[: self.limits.max_items]
        if _model_facing:
            records = [self._id_registry.modelize_record(item, "source") for item in records]
        next_offset = offset + len(records)
        return {
            "items": records, "count": len(records), "returned_count": len(records),
            "offset": offset, "next_offset": next_offset if next_offset < len(items) else None,
            "has_more": next_offset < len(items), "path": path, "read_only": True,
        }

    def read_source_items(
        self, source_item_ids: Sequence[str] | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        allowed = set(self._source_item_ids)
        if source_item_ids is not None and not source_item_ids:
            if _model_facing:
                return _structured_id_error(
                    "source", "", "empty_request", "provide at least one source ID",
                )
            raise ValueError("at least one source_item_id is required")
        raw_requested = tuple(dict.fromkeys(
            str(item).strip() for item in (
                self._source_item_ids if source_item_ids is None else source_item_ids
            )
            if str(item).strip()
        ))
        requested, id_rejections = self._id_registry.resolve_many(
            "source", raw_requested, allowed_canonical_ids=allowed,
        )
        rejected = tuple(item.value for item in id_rejections)
        available = [item for item in self._source_items if item.source_item_id in requested]
        records = self._tools._bounded_records(available)  # noqa: SLF001
        available_ids = {item.source_item_id for item in available}
        returned_ids = {str(item["source_item_id"]) for item in records}
        result = {
            "items": records,
            "count": len(records),
            "requested_source_item_ids": list(raw_requested[: self.limits.max_items]),
            "missing_source_item_ids": [item for item in requested if item not in available_ids][: self.limits.max_items],
            "truncated_source_item_ids": [item for item in requested if item in available_ids and item not in returned_ids][: self.limits.max_items],
            "read_only": True,
        }
        result["rejected_source_item_ids"] = list(rejected)[: self.limits.max_items]
        result["id_rejections"] = [item.as_dict() for item in id_rejections[: self.limits.max_items]]
        if _model_facing:
            result["items"] = [self._id_registry.modelize_record(item, "source") for item in records]
            result["missing_source_item_ids"] = self._id_registry.modelize_ids(
                result["missing_source_item_ids"], "source",
            )
            result["truncated_source_item_ids"] = self._id_registry.modelize_ids(
                result["truncated_source_item_ids"], "source",
            )
        result["has_more"] = bool(result.get("truncated_source_item_ids"))
        return result

    def search_source_items(self, query: str, *, _model_facing: bool = False) -> dict[str, Any]:
        normalized = bounded_text(query, 400).strip().casefold()
        matches = [item for item in self._source_items if normalized and normalized in f"{item.key} {item.text}".casefold()]
        records = self._tools._bounded_records(matches)  # noqa: SLF001
        if _model_facing:
            records = [self._id_registry.modelize_record(item, "source") for item in records]
        return {
            "items": records, "count": len(records), "returned_count": len(records),
            "has_more": len(records) < len(matches), "query": normalized,
            "read_only": True,
        }

    def corpus_manifest(self, *, _model_facing: bool = False) -> dict[str, Any]:
        paths = Counter(item.relative_path or "(unknown)" for item in self._source_items)
        ranked = sorted(paths.items(), key=lambda item: (-item[1], item[0]))
        shard_page = self.investigation_shards(
            page_limit=min(3, self.limits.max_items), _model_facing=_model_facing,
        )
        return {
            "source_item_count": len(self._source_items), "local_unit_count": len(self._local_units),
            "path_count": len(paths),
            "paths": [{"path": bounded_text(path, 240), "source_item_count": count} for path, count in ranked[: self.limits.max_items]],
            "paths_truncated": len(paths) > self.limits.max_items,
            "recommended_planning_mode": "adaptive_multi_shard" if len(self._local_units) > self.limits.max_items else "single_shard_per_role",
            "overlap_policy": (
                "Overlap is investigative only. Adjacent shards share boundary units for context; "
                "core units own evidence."
            ),
            "shard_policy": {
                "core_units_target": DEFAULT_SHARD_CORE_UNITS, "overlap_units": DEFAULT_SHARD_OVERLAP_UNITS,
                "max_core_source_items": DEFAULT_SHARD_SOURCE_ITEMS, "max_core_chars": DEFAULT_SHARD_CHARS,
                "max_requests_per_shard": SHARD_REQUEST_BUDGET, "max_tool_calls_per_shard": SHARD_TOOL_CALL_BUDGET,
                "ownership": "core_local_unit_ids only; overlap is context_only",
            },
            "shard_count": shard_page["total_count"], "shards": shard_page["shards"],
            "shards_offset": shard_page["offset"], "shards_next_offset": shard_page["next_offset"],
            "shards_has_more": shard_page["has_more"], "read_only": True,
            "structure_source": "deterministic_manifest_only",
            "id_scheme": {
                "source_item_ids": "S001, S002, ...",
                "local_unit_ids": "U001, U002, ...",
                "canonical_persistence": "source-item hash and unit_N",
            },
        }

    def investigation_shards(
        self, offset: int = 0, path: str | None = None, *, page_limit: int | None = None,
        _model_facing: bool = False,
    ) -> dict[str, Any]:
        _require_offset(offset)
        shards = build_investigation_shards(self._local_units)
        if path is not None:
            normalized = str(path).replace("\\", "/").strip().casefold()
            if not normalized:
                raise ValueError("path must not be blank")
            shards = [shard for shard in shards if any(
                str(item).replace("\\", "/").casefold() == normalized
                for item in (*shard["paths"], *shard["overlap_paths"])
            )]
        if page_limit is not None and (not isinstance(page_limit, int) or isinstance(page_limit, bool) or not 1 <= page_limit <= self.limits.max_items):
            raise ValueError("page_limit must be within the corpus item budget")
        page = shards[offset: offset + (page_limit or self.limits.max_items)]
        used = 0
        bounded_page = []
        for shard in page:
            size = len(json.dumps(shard, ensure_ascii=False, separators=(",", ":")))
            if bounded_page and used + size > self.limits.max_total_chars:
                break
            bounded_page.append(shard)
            used += size
        if _model_facing:
            bounded_page = [_modelize_shard(shard, self._id_registry) for shard in bounded_page]
        next_offset = offset + len(bounded_page)
        return {
            "shards": bounded_page, "count": len(bounded_page), "total_count": len(shards),
            "offset": offset, "next_offset": next_offset if next_offset < len(shards) else None,
            "has_more": next_offset < len(shards), "path": path, "read_only": True,
            "structure_source": "deterministic_shard_manifest",
        }

    def read_investigation_shards(
        self, shard_ids: Sequence[str], *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        requested = tuple(dict.fromkeys(str(item).strip() for item in shard_ids if str(item).strip()))
        if not requested:
            if _model_facing:
                return {
                    "shards": [], "count": 0, "requested_shard_ids": [],
                    "read_only": True,
                    "id_rejections": [{
                        "kind": "shard", "value": "", "code": "empty_request",
                        "message": "provide at least one investigation shard ID",
                    }],
                }
            raise ValueError("at least one shard_id is required")
        if len(requested) > 3:
            raise ValueError("at most 3 investigation shards may be read at once")
        known = {item["shard_id"]: item for item in build_investigation_shards(self._local_units)}
        unknown = [item for item in requested if item not in known]
        if unknown:
            if _model_facing:
                return {
                    "shards": [], "count": 0,
                    "requested_shard_ids": list(requested), "read_only": True,
                    "id_rejections": [{
                        "kind": "shard", "value": item, "code": "unknown_id",
                        "message": "unknown investigation shard ID; use an exact leased shard ID",
                    } for item in unknown],
                }
            raise ValueError(f"unknown investigation shard(s): {unknown}")
        output = []
        used = 0
        envelope_limit = MAX_ALLOWED_TOTAL_CHARS
        for shard_id in requested:
            shard = known[shard_id]
            units = [self._unit_record(
                self._local_unit_by_id[unit_id], include_text=True, model_facing=_model_facing,
            ) for unit_id in shard["local_unit_ids"]]
            record = {**shard, "units": units, "truncated": False, "omitted_local_unit_ids": []}
            size = len(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            if used + size > envelope_limit:
                available = max(0, envelope_limit - used)
                kept, omitted = [], []
                for unit_id, unit in zip(shard["local_unit_ids"], units):
                    candidate = {**record, "units": [*kept, unit], "truncated": bool(omitted), "omitted_local_unit_ids": omitted}
                    if len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))) > available:
                        omitted.append(unit_id)
                    else:
                        kept.append(unit)
                record["units"] = kept
                record["truncated"] = bool(omitted)
                record["omitted_local_unit_ids"] = omitted
                size = len(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                if used + size > envelope_limit:
                    if output:
                        break
                    record["units"] = []
                    record["truncated"] = True
                    record["omitted_local_unit_ids"] = list(shard["local_unit_ids"])
                    size = len(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            output.append(record)
            used += size
        if _model_facing:
            output = [_modelize_shard(record, self._id_registry) for record in output]
        return {
            "shards": output, "count": len(output), "requested_shard_ids": list(requested),
            "truncated": len(output) < len(requested) or any(item["truncated"] for item in output),
            "read_only": True, "structure_source": "deterministic_shard_manifest",
        }

    def shard_lease(self, shard_ids: str | Sequence[str]) -> ShardLease:
        known = {shard["shard_id"]: shard for shard in build_investigation_shards(self._local_units)}
        requested = (shard_ids,) if isinstance(shard_ids, str) else tuple(shard_ids)
        unknown = [str(shard_id) for shard_id in requested if str(shard_id) not in known]
        if unknown:
            raise ValueError(f"unknown investigation shard(s): {unknown}")
        return ShardLease.from_plans(tuple(known[str(shard_id)] for shard_id in requested))

    def owned_shard_view(self, shard_ids: str | Sequence[str]) -> OwnedShardCorpusView:
        return OwnedShardCorpusView(self, self.shard_lease(shard_ids))

    def validate_delegation_task(self, task: Any) -> tuple[str, ...]:
        shard_ids = tuple(dict.fromkeys(re.findall(r"investigation-\d{3}", str(task or ""))))
        if not shard_ids:
            raise ValueError("delegation must name 1-3 exact investigation shard IDs")
        if len(shard_ids) > 3:
            raise ValueError("large-corpus delegation may name at most 3 investigation shards")
        known = {shard["shard_id"] for shard in build_investigation_shards(self._local_units)}
        unknown = [item for item in shard_ids if item not in known]
        if unknown:
            raise ValueError(f"unknown investigation shard(s): {unknown}")
        return shard_ids

    def list_local_units(
        self, offset: int = 0, path: str | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        _require_offset(offset)
        matching = tuple(unit for unit in self._local_units if path is None or any(_path_matches(path, item) for item in unit.items))
        selected = matching[offset: offset + self.limits.max_items]
        next_offset = offset + len(selected)
        return {
            "units": [self._unit_record(unit, include_text=False, model_facing=_model_facing) for unit in selected], "count": len(selected),
            "offset": offset, "next_offset": next_offset if next_offset < len(matching) else None,
            "has_more": next_offset < len(matching), "path": path, "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def read_local_units(
        self, local_unit_ids: Sequence[str], *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        raw_requested = tuple(dict.fromkeys(str(item).strip() for item in local_unit_ids if str(item).strip()))
        if not raw_requested:
            if _model_facing:
                return _structured_id_error(
                    "unit", "", "empty_request", "provide at least one local-unit ID",
                )
            raise ValueError("at least one local_unit_id is required")
        requested, id_rejections = self._id_registry.resolve_many("unit", raw_requested)
        accepted = tuple(item for item in requested if item in self._local_unit_by_id)
        units = [self._unit_record(
            self._local_unit_by_id[item], include_text=True, model_facing=_model_facing,
        ) for item in accepted]
        units, omitted = _bounded_unit_records(units, self.limits.max_total_chars)
        return {
            "units": units,
            "count": len(units), "requested_local_unit_ids": list(raw_requested),
            "rejected_local_unit_ids": [item.value for item in id_rejections]
            + [item for item in requested if item not in self._local_unit_by_id],
            "id_rejections": [item.as_dict() for item in id_rejections],
            "truncated": bool(omitted) or len(accepted) < len(requested),
            "omitted_local_unit_ids": omitted,
            "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def search_local_units(self, query: str, *, _model_facing: bool = False) -> dict[str, Any]:
        normalized = bounded_text(query, 400).strip().casefold()
        matches = [unit for unit in self._local_units if normalized and normalized in self._unit_text(unit)]
        selected = matches[: self.limits.max_items]
        return {
            "units": [self._unit_record(unit, include_text=True, model_facing=_model_facing) for unit in selected], "count": len(selected),
            "has_more": len(selected) < len(matches), "query": normalized, "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def _unit_record(
        self, unit: LocalTextUnit, *, include_text: bool, model_facing: bool = False,
    ) -> dict[str, Any]:
        entries, omitted, used = [], [], 0
        for item in unit.items:
            source_id = str(item.source_item_id)
            if model_facing:
                source_id = self._id_registry.source_alias(source_id)
            entry = {"source_item_id": source_id, "key": str(item.item_key or ""), "source_order": item.source_order}
            if include_text:
                remaining = max(0, self.limits.max_total_chars - used)
                entry["text"] = bounded_text(item.source_text, min(self.limits.max_item_chars, remaining))
                entry["text_truncated"] = len(item.source_text) > len(entry["text"])
            cost = len(str(entry))
            if used + cost > self.limits.max_total_chars:
                omitted.append(source_id)
            else:
                entries.append(entry)
                used += cost
        return {
            "local_unit_id": self._id_registry.unit_alias(unit.unit_id) if model_facing else unit.unit_id,
            "derived_unit_key": unit.unit_key.split("::", 1)[-1],
            "paths": list(dict.fromkeys(str(item.relative_path) for item in unit.items)),
            "item_keys": [str(item.item_key or "") for item in unit.items], "entries": entries,
            "truncated": bool(omitted), "omitted_source_item_ids": omitted,
        }

    @staticmethod
    def _unit_text(unit: LocalTextUnit) -> str:
        return " ".join(f"{item.item_key or ''} {item.source_text}" for item in unit.items).casefold()


def _source_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("source_item_id") or item.get("id") or "").strip()
    return str(getattr(item, "source_item_id", "")).strip()


def _structured_id_error(
    kind: str, value: str, code: str, message: str,
) -> dict[str, Any]:
    return {
        "items" if kind == "source" else "units": [],
        "count": 0,
        "read_only": True,
        "id_rejections": [{
            "kind": kind, "value": value, "code": code, "message": message,
        }],
    }


def _modelize_shard(
    shard: dict[str, Any], registry: ShortIdRegistry,
) -> dict[str, Any]:
    """Project a canonical host shard into the model's short-ID vocabulary."""

    result = dict(shard)
    for field in (
        "core_local_unit_ids", "overlap_local_unit_ids", "local_unit_ids",
        "omitted_local_unit_ids",
    ):
        if field in result:
            result[field] = registry.modelize_ids(result[field], "unit")
    for field in ("core_source_item_ids", "overlap_source_item_ids"):
        if field in result:
            result[field] = registry.modelize_ids(result[field], "source")
    ownership = result.get("ownership")
    if isinstance(ownership, dict):
        result["ownership"] = {
            registry.alias_by_unit.get(str(unit_id), str(unit_id)): value
            for unit_id, value in ownership.items()
        }
    if "units" in result:
        model_units = []
        for unit in result["units"]:
            model_unit = registry.modelize_record(unit, "unit")
            model_unit["entries"] = [
                registry.modelize_record(entry, "source")
                for entry in unit.get("entries", [])
            ]
            model_units.append(model_unit)
        result["units"] = model_units
    return result


def _path_matches(path: str | None, item: Any) -> bool:
    if path is None:
        return True
    normalized = str(path).replace("\\", "/").strip().casefold()
    if not normalized:
        raise ValueError("path must not be blank")
    return str(getattr(item, "relative_path", "")).replace("\\", "/").casefold() == normalized


def _require_offset(offset: int) -> None:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset must be a non-negative integer")


def _bounded_unit_records(
    units: Sequence[dict[str, Any]], max_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    omitted: list[str] = []
    used = 0
    for unit in units:
        cost = len(json.dumps(unit, ensure_ascii=False, separators=(",", ":")))
        if selected and used + cost > max_chars:
            omitted.append(str(unit["local_unit_id"]))
            continue
        selected.append(unit)
        used += cost
    return selected, omitted


RemisCorpusTools = ReadOnlyRemisCorpusTools

__all__ = [
    "CorpusReader", "CorpusSourceItem", "CorpusToolLimits", "InMemoryCorpus",
    "ReadOnlyRemisCorpusTools", "RemisCorpusTools", "BoundCorpusTools",
    "OwnedShardCorpusView", "ShardLease",
    "ShortIdRegistry",
]
