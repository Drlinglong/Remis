"""Per-delegation shard leases for source and evidence ownership."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShardLease:
    """The only 1-3 shards a delegated investigator may inspect."""

    shard_ids: tuple[str, ...]
    core_local_unit_ids: tuple[str, ...]
    overlap_local_unit_ids: tuple[str, ...] = ()
    owner_shard_by_unit: Mapping[str, str] | None = None

    @classmethod
    def from_plan(cls, plan: Mapping[str, Any]) -> "ShardLease":
        return cls.from_plans((plan,))

    @classmethod
    def from_plans(cls, plans: Sequence[Mapping[str, Any]]) -> "ShardLease":
        if not 1 <= len(plans) <= 3:
            raise ValueError("a delegation lease requires 1-3 investigation shards")
        shard_ids = tuple(str(plan["shard_id"]) for plan in plans)
        if len(shard_ids) != len(set(shard_ids)):
            raise ValueError("a delegation lease cannot repeat a shard")
        core_units = tuple(dict.fromkeys(
            str(item) for plan in plans for item in plan.get("core_local_unit_ids", ())
        ))
        core_set = set(core_units)
        overlap_units = tuple(dict.fromkeys(
            str(item) for plan in plans for item in plan.get("overlap_local_unit_ids", ())
            if str(item) not in core_set
        ))
        owners = {
            str(unit_id): str(plan["shard_id"])
            for plan in plans
            for unit_id in plan.get("core_local_unit_ids", ())
        }
        return cls(
            shard_ids=shard_ids,
            core_local_unit_ids=core_units,
            overlap_local_unit_ids=overlap_units,
            owner_shard_by_unit=owners,
        )

    @property
    def shard_id(self) -> str:
        """Compatibility label for traces; authorization uses ``shard_ids``."""

        return ",".join(self.shard_ids)

    @property
    def allowed_local_unit_ids(self) -> tuple[str, ...]:
        return self.overlap_local_unit_ids + self.core_local_unit_ids

    @property
    def ownership(self) -> dict[str, dict[str, Any]]:
        return {
            **{
                unit_id: {
                    "evidence_role": "context_only",
                    "ownership": "overlap_context",
                    "owner_shard_id": None,
                }
                for unit_id in self.overlap_local_unit_ids
            },
            **{
                unit_id: {
                    "evidence_role": "owner",
                    "ownership": "owned",
                    "owner_shard_id": (self.owner_shard_by_unit or {}).get(unit_id),
                }
                for unit_id in self.core_local_unit_ids
            },
        }

    def role_for_unit(self, unit_id: str) -> str:
        if unit_id in self.core_local_unit_ids:
            return "owned"
        if unit_id in self.overlap_local_unit_ids:
            return "overlap_context"
        return "external_context_only"


class OwnedShardCorpusView:
    """Restrict a request-bound corpus facade to one leased shard.

    The wrapped facade is intentionally duck-typed to avoid a dependency cycle
    with ``BoundCorpusTools``.  Every public read path checks the lease before
    calling the underlying request-bound tools.
    """

    def __init__(self, bound_tools: Any, lease: ShardLease) -> None:
        self._bound = bound_tools
        self.lease = lease

    @property
    def limits(self) -> Any:
        return self._bound.limits

    def _check_units(self, local_unit_ids: Sequence[str]) -> tuple[str, ...]:
        raw_requested = tuple(dict.fromkeys(str(item).strip() for item in local_unit_ids if str(item).strip()))
        if not raw_requested:
            if _model_facing:
                return {
                    "units": [], "count": 0, "read_only": True,
                    "id_rejections": [{
                        "kind": "unit", "value": "", "code": "empty_request",
                        "message": "provide at least one local-unit ID",
                    }],
                }
            raise ValueError("at least one local_unit_id is required")
        requested, rejections = self._bound.id_registry.resolve_many(
            "unit", raw_requested,
            allowed_canonical_ids=self.lease.allowed_local_unit_ids,
        )
        unknown = [item.value for item in rejections]
        if unknown:
            raise ValueError(f"local unit(s) outside shard lease: {unknown}")
        return requested

    def _unit_ownership(self, unit_id: str) -> dict[str, Any]:
        role = self.lease.role_for_unit(unit_id)
        return {
            "evidence_role": "owner" if role == "owned" else "context_only",
            "ownership": role,
            "owner_shard_id": (self.lease.owner_shard_by_unit or {}).get(unit_id),
        }

    def _decorate_units(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decorated = []
        for unit in units:
            unit_id = str(unit["local_unit_id"])
            ownership = self._unit_ownership(unit_id)
            item = dict(unit)
            item.update(ownership)
            item["entries"] = [
                {**entry, **ownership} for entry in item.get("entries", [])
            ]
            decorated.append(item)
        return decorated

    def read_local_units(
        self, local_unit_ids: Sequence[str], *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        raw_requested = tuple(dict.fromkeys(str(item).strip() for item in local_unit_ids if str(item).strip()))
        if not raw_requested:
            raise ValueError("at least one local_unit_id is required")
        requested, rejections = self._bound.id_registry.resolve_many("unit", raw_requested)
        result = self._bound.read_local_units(requested)
        result = dict(result)
        result["units"] = self._decorate_units(result.get("units", []))
        result["ownership"] = self.lease.ownership
        result["shard_id"] = self.lease.shard_id
        if _model_facing:
            result["units"] = [self._modelize_unit(unit) for unit in result["units"]]
            result["requested_local_unit_ids"] = list(raw_requested)
            result["rejected_local_unit_ids"] = [item.value for item in rejections]
            result["id_rejections"] = [item.as_dict() for item in rejections]
            result["ownership"] = {
                self._bound.id_registry.alias_by_unit.get(str(unit["local_unit_id"]), str(unit["local_unit_id"])): {
                    "evidence_role": unit.get("evidence_role"),
                    "ownership": unit.get("ownership"),
                    "owner_shard_id": unit.get("owner_shard_id"),
                }
                for unit in result["units"]
            }
        return result

    def _modelize_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        registry = self._bound.id_registry
        result = registry.modelize_record(unit, "unit")
        result["entries"] = [
            registry.modelize_record(entry, "source")
            for entry in unit.get("entries", [])
        ]
        if "omitted_source_item_ids" in result:
            result["omitted_source_item_ids"] = registry.modelize_ids(
                result["omitted_source_item_ids"], "source",
            )
        return result

    def list_local_units(
        self, offset: int = 0, path: str | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        unit_ids = tuple(getattr(self._bound, "_local_unit_by_id", {}).keys())
        if path is not None:
            normalized = str(path).replace("\\", "/").strip().casefold()
            raw_units = getattr(self._bound, "_local_unit_by_id", {})
            unit_ids = tuple(
                unit_id for unit_id in unit_ids
                if any(
                    str(item.relative_path).replace("\\", "/").casefold() == normalized
                    for item in raw_units[unit_id].items
                )
            )
        selected = unit_ids[offset: offset + self.limits.max_items]
        result = self.read_local_units(selected, _model_facing=_model_facing) if selected else {
            "units": [], "count": 0, "read_only": True,
        }
        result["units"] = [
            {key: value for key, value in unit.items() if key != "entries"}
            for unit in result["units"]
        ]
        next_offset = offset + len(selected)
        result.update({
            "offset": offset,
            "next_offset": next_offset if next_offset < len(unit_ids) else None,
            "has_more": next_offset < len(unit_ids),
            "path": path,
        })
        return result

    def _source_ids(self) -> tuple[str, ...]:
        raw_units = getattr(self._bound, "_local_unit_by_id", {})
        if raw_units:
            return tuple(dict.fromkeys(
                str(item.source_item_id)
                for unit_id in raw_units
                for item in raw_units[unit_id].items
            ))
        unit_result = self._bound.read_local_units(tuple(raw_units))
        return tuple(dict.fromkeys(
            str(entry["source_item_id"])
            for unit in unit_result["units"]
            for entry in unit.get("entries", [])
        ))

    def _source_roles(self) -> dict[str, dict[str, Any]]:
        roles: dict[str, dict[str, Any]] = {}
        raw_units = getattr(self._bound, "_local_unit_by_id", {})
        if raw_units:
            for unit_id in raw_units:
                for item in raw_units[unit_id].items:
                    unit_role = self.lease.role_for_unit(unit_id)
                    metadata = {
                        "evidence_role": "owner" if unit_role == "owned" else "context_only",
                        "ownership": unit_role,
                        "owner_shard_id": (self.lease.owner_shard_by_unit or {}).get(unit_id),
                    }
                    if unit_role == "owned":
                        roles[str(item.source_item_id)] = metadata
                    else:
                        roles.setdefault(str(item.source_item_id), metadata)
            return roles
        for unit_id in raw_units:
            unit = self._bound.read_local_units([unit_id])["units"]
            for entry in unit[0].get("entries", []) if unit else ():
                unit_role = self.lease.role_for_unit(unit_id)
                metadata = {
                    "evidence_role": "owner" if unit_role == "owned" else "context_only",
                    "ownership": unit_role,
                    "owner_shard_id": (self.lease.owner_shard_by_unit or {}).get(unit_id),
                }
                if unit_role == "owned":
                    roles[str(entry["source_item_id"])] = metadata
                else:
                    roles.setdefault(str(entry["source_item_id"]), metadata)
        return roles

    def read_source_items(
        self, source_item_ids: Sequence[str] | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        allowed = set(self._source_ids())
        if source_item_ids is not None and not source_item_ids:
            if _model_facing:
                return {
                    "items": [], "count": 0, "read_only": True,
                    "id_rejections": [{
                        "kind": "source", "value": "", "code": "empty_request",
                        "message": "provide at least one source ID",
                    }],
                }
            raise ValueError("at least one source_item_id is required")
        raw_requested = tuple(str(item).strip() for item in (source_item_ids or allowed) if str(item).strip())
        requested, rejections = self._bound.id_registry.resolve_many("source", raw_requested)
        result = dict(self._bound.read_source_items(requested))
        roles = self._source_roles()
        result["items"] = [{**item, **roles.get(str(item["source_item_id"]), {})} for item in result.get("items", [])]
        result["ownership"] = roles
        result["shard_ids"] = list(self.lease.shard_ids)
        if _model_facing:
            registry = self._bound.id_registry
            result["items"] = [registry.modelize_record(item, "source") for item in result["items"]]
            result["requested_source_item_ids"] = list(raw_requested)
            result["rejected_source_item_ids"] = [item.value for item in rejections]
            result["id_rejections"] = [item.as_dict() for item in rejections]
            result["ownership"] = {
                registry.alias_by_source.get(source_id, source_id): value
                for source_id, value in roles.items()
            }
        return result

    def list_source_items(
        self, offset: int = 0, path: str | None = None, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        result = self.read_source_items(_model_facing=_model_facing)
        items = result.get("items", [])
        if path is not None:
            normalized = str(path).replace("\\", "/").strip().casefold()
            items = [
                item for item in items
                if str(item.get("path", "")).replace("\\", "/").casefold() == normalized
            ]
        selected = items[offset: offset + self.limits.max_items]
        next_offset = offset + len(selected)
        result.update({
            "items": selected,
            "count": len(selected),
            "returned_count": len(selected),
            "offset": offset,
            "next_offset": next_offset if next_offset < len(items) else None,
            "has_more": next_offset < len(items),
            "path": path,
        })
        return result

    def search_source_items(self, query: str, *, _model_facing: bool = False) -> dict[str, Any]:
        normalized = str(query or "").strip().casefold()
        result = self.read_source_items(_model_facing=_model_facing)
        result["items"] = [
            item for item in result.get("items", [])
            if normalized in f"{item.get('key', '')} {item.get('text', '')}".casefold()
        ] if normalized else []
        result["count"] = len(result["items"])
        result["returned_count"] = len(result["items"])
        result["has_more"] = False
        result["query"] = normalized
        return result

    def search_local_units(
        self, query: str, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        normalized = str(query or "").strip().casefold()
        result = self.read_local_units(
            tuple(getattr(self._bound, "_local_unit_by_id", {}).keys()),
            _model_facing=_model_facing,
        )
        result["units"] = [
            unit for unit in result["units"]
            if normalized in " ".join(
                f"{entry.get('key', '')} {entry.get('text', '')}" for entry in unit.get("entries", [])
            ).casefold()
        ] if normalized else []
        result["count"] = len(result["units"])
        result["query"] = normalized
        return result

    def read_investigation_shards(
        self, shard_ids: Sequence[str], *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        requested = tuple(dict.fromkeys(str(item).strip() for item in shard_ids if str(item).strip()))
        if not requested or not set(requested) <= set(self.lease.shard_ids):
            if _model_facing:
                return {
                    "shards": [], "count": 0, "read_only": True,
                    "id_rejections": [{
                        "kind": "shard", "value": item, "code": "outside_lease",
                        "message": "only exact delegated shard IDs may be inspected",
                    } for item in requested],
                }
            raise ValueError(f"only leased shards {self.lease.shard_ids!r} may be read")
        result = dict(self._bound.read_investigation_shards(
            requested, _model_facing=_model_facing,
        ))
        for shard in result.get("shards", []):
            shard["ownership"] = self.lease.ownership
            if _model_facing:
                registry = self._bound.id_registry
                shard["ownership"] = {
                    registry.alias_by_unit.get(unit_id, unit_id): value
                    for unit_id, value in self.lease.ownership.items()
                }
        return result

    def investigation_shards(
        self, offset: int = 0, *, _model_facing: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        plans = self._bound.read_investigation_shards(
            self.lease.shard_ids, _model_facing=_model_facing,
        ).get("shards", [])
        selected = plans[offset: offset + self.limits.max_items]
        next_offset = offset + len(selected)
        return {
            "shards": selected,
            "count": len(selected),
            "total_count": len(plans),
            "offset": offset,
            "next_offset": next_offset if next_offset < len(plans) else None,
            "has_more": next_offset < len(plans),
            "read_only": True,
            "structure_source": "delegation_shard_lease",
        }

    def corpus_manifest(self, *, _model_facing: bool = False) -> dict[str, Any]:
        page = self.investigation_shards(_model_facing=_model_facing)
        ownership = self.lease.ownership
        if _model_facing:
            registry = self._bound.id_registry
            ownership = {
                registry.alias_by_unit.get(unit_id, unit_id): self._unit_ownership(unit_id)
                for unit_id in getattr(self._bound, "_local_unit_by_id", {})
            }
        return {
            "source_item_count": len(self._source_ids()),
            "local_unit_count": len(getattr(self._bound, "_local_unit_by_id", {})),
            "shard_count": len(self.lease.shard_ids),
            "shards": page["shards"],
            "shards_has_more": False,
            "ownership": ownership,
            "id_scheme": {
                "source_item_ids": "S001, S002, ...",
                "local_unit_ids": "U001, U002, ...",
                "canonical_persistence": "source-item hash and unit_N",
            },
            "read_only": True,
            "structure_source": "delegation_shard_lease",
        }


__all__ = ["OwnedShardCorpusView", "ShardLease"]
