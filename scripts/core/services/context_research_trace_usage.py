"""Usage DTO, provider usage conversion, and aggregation helpers."""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections import defaultdict
from typing import Any, Mapping


@dataclasses.dataclass(frozen=True, slots=True)
class UsageRecord:
    """One provider or tool usage observation, with missing values explicit."""

    scope: str
    role: str | None = None
    shard: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    cache_write_tokens: int | None = None
    cache_read_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    tool_calls: int | None = None
    requests: int | None = None
    cost: float | None = None
    duration_ms: int | None = None
    status: str = "completed"
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("usage scope must not be blank")
        for field_name in (
            "input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens",
            "reasoning_tokens", "tool_calls", "requests", "duration_ms",
        ):
            value = getattr(self, field_name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.cost is not None and self.cost < 0:
            raise ValueError("cost must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def usage_record_from_run_usage(
    usage: Any,
    *,
    scope: str,
    role: str | None = None,
    shard: str | None = None,
    model: str | None = None,
    cost: float | None = None,
    duration_ms: int | None = None,
    status: str = "completed",
    started_at: str | None = None,
    finished_at: str | None = None,
) -> UsageRecord:
    """Convert Pydantic ``RunUsage`` or a dict without estimating missing data."""

    values = _object_mapping(usage)
    details = values.get("details")
    details = details if isinstance(details, Mapping) else {}
    fields = (
        "requests", "tool_calls", "input_tokens", "cache_write_tokens",
        "cache_read_tokens", "output_tokens", "reasoning_tokens",
    )
    merged = {
        field: values.get(field) if values.get(field) is not None else details.get(field)
        for field in fields
    }
    if type(usage).__name__ == "RunUsage":
        for field in fields:
            if merged[field] == 0 and field not in details:
                merged[field] = None
    return UsageRecord(
        scope=scope,
        role=role,
        shard=shard,
        model=model,
        input_tokens=_optional_int(merged["input_tokens"]),
        cache_write_tokens=_optional_int(merged["cache_write_tokens"]),
        cache_read_tokens=_optional_int(merged["cache_read_tokens"]),
        output_tokens=_optional_int(merged["output_tokens"]),
        reasoning_tokens=_optional_int(merged["reasoning_tokens"]),
        tool_calls=_optional_int(merged["tool_calls"]),
        requests=_optional_int(merged["requests"]),
        cost=_optional_float(cost if cost is not None else values.get("cost")),
        duration_ms=duration_ms,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
    )


def normalize_usage(values: Mapping[str, Any]) -> UsageRecord:
    """Normalize a mapping and derive duration only from supplied timestamps."""

    started = values.get("started_at")
    finished = values.get("finished_at")
    duration = values.get("duration_ms")
    if duration is None:
        duration = duration_ms_between(started, finished)
    return UsageRecord(
        scope=str(values.get("scope", "unknown")),
        role=_optional_string(values.get("role")),
        shard=_optional_string(values.get("shard")),
        model=_optional_string(values.get("model")),
        input_tokens=_optional_int(values.get("input_tokens")),
        cache_write_tokens=_optional_int(values.get("cache_write_tokens")),
        cache_read_tokens=_optional_int(values.get("cache_read_tokens")),
        output_tokens=_optional_int(values.get("output_tokens")),
        reasoning_tokens=_optional_int(values.get("reasoning_tokens")),
        tool_calls=_optional_int(values.get("tool_calls")),
        requests=_optional_int(values.get("requests")),
        cost=_optional_float(values.get("cost")),
        duration_ms=_optional_int(duration),
        status=str(values.get("status", "completed")),
        started_at=started,
        finished_at=finished,
    )


def usage_group_summary(scope, role, shard, model, records):
    numeric_fields = (
        "requests", "input_tokens", "cache_write_tokens", "cache_read_tokens",
        "output_tokens", "reasoning_tokens", "tool_calls", "cost", "duration_ms",
    )
    summary = {field: _sum_known(records, field) for field in numeric_fields}
    summary.update({
        "scope": scope, "role": role, "shard": shard, "model": model,
        "calls": len(records), "statuses": dict(status_counts(records)),
        "missing_usage_calls": sum(
            1 for record in records
            if all(record.get(field) is None for field in ("input_tokens", "output_tokens", "reasoning_tokens"))
        ),
        "missing_cost_calls": sum(1 for record in records if record.get("cost") is None),
    })
    return summary


def summarize_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate normalized records by execution scope."""

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = tuple(record.get(field) for field in ("scope", "role", "shard", "model"))
        groups[key].append(record)
    summaries = [
        usage_group_summary(scope, role, shard, model, grouped)
        for (scope, role, shard, model), grouped in groups.items()
    ]
    return {"groups": summaries, "totals": usage_group_summary(None, None, None, None, records)}


def _object_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if type(value).__name__ == "RunUsage" and hasattr(value, "__dict__"):
        return dict(vars(value))
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return dict(vars(value)) if hasattr(value, "__dict__") else {}


def duration_ms_between(started: Any, finished: Any) -> int | None:
    if not started or not finished:
        return None
    try:
        start = dt.datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, round((end - start).total_seconds() * 1000))


def status_counts(records):
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[str(record.get("status", "unknown"))] += 1
    return counts.items()


def _sum_known(records, field: str):
    values = [record.get(field) for record in records if record.get(field) is not None]
    return sum(values) if values else None


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("usage integer fields cannot be boolean")
    return int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


__all__ = ["UsageRecord", "normalize_usage", "summarize_usage", "usage_record_from_run_usage"]
