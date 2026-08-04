"""Deterministic evidence selection and project-overview helpers for v2."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


def _field(raw: Any, *names: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return default
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def _unit_id(unit: Any) -> str:
    return str(_field(unit, "unit_id", "local_unit_id", default=""))


def _unit_order(unit: Any, position: int) -> int:
    value = _field(unit, "unit_order", "order", "source_order", default=None)
    try:
        return int(value) if value is not None else position
    except (TypeError, ValueError):
        return position


def _batch_index(unit: Any) -> int | None:
    value = _field(unit, "batch_index", "batch", default=None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _groups(unit: Any) -> tuple[str, ...]:
    raw = _field(unit, "event_group_ids", "event_group_id", "group_id", default=())
    if raw is None:
        return ()
    values = (raw,) if isinstance(raw, str) else raw
    try:
        return tuple(dict.fromkeys(str(item) for item in values if str(item)))
    except TypeError:
        return (str(raw),) if str(raw) else ()


def _source_text(unit: Any) -> str:
    return str(_field(unit, "source_text", "text", "original_text", default=""))


def _density_key(text: str) -> tuple[float, int, int, int]:
    tokens = re.findall(r"[\w-]+", text, flags=re.UNICODE)
    if not tokens:
        return (0.0, 0, 0, len(text))
    unique = {token.casefold() for token in tokens}
    signals = re.findall(r"\d+|\b[A-Z][\w-]*\b", text)
    return (round(len(unique) / len(tokens), 6), len(signals), len(unique), min(len(text), 2_000))


def _ordered_units(
    requested_ids: Sequence[str],
    local_units: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[Mapping[str, Any]], dict[str, int], list[str]]:
    unit_by_id = {_unit_id(unit): unit for unit in local_units if _unit_id(unit)}
    positions = {_unit_id(unit): index for index, unit in enumerate(local_units) if _unit_id(unit)}
    requested = list(dict.fromkeys(str(unit_id) for unit_id in requested_ids))
    missing = [unit_id for unit_id in requested if unit_id not in unit_by_id]
    eligible = [unit_by_id[unit_id] for unit_id in requested if unit_id in unit_by_id]
    eligible.sort(key=lambda unit: (_unit_order(unit, positions[_unit_id(unit)]), positions[_unit_id(unit)]))
    return requested, eligible, positions, missing


def _diagnostic(candidate_id: str, code: str, detail: str) -> dict[str, str]:
    return {"code": code, "candidate_id": candidate_id, "detail": detail}


def _validate_budgets(max_units: int, max_source_chars: int) -> None:
    if max_units < 1 or max_source_chars < 1:
        raise ValueError("digest selection budgets must be positive")


def _mark_sample(
    unit: Mapping[str, Any],
    reason: str,
    selected: list[Mapping[str, Any]],
    selected_ids: set[str],
    reasons: dict[str, list[str]],
    max_units: int,
) -> bool:
    unit_id = _unit_id(unit)
    if reason not in reasons.setdefault(unit_id, []):
        reasons[unit_id].append(reason)
    if unit_id in selected_ids:
        return True
    if len(selected) >= max_units:
        return False
    selected.append(unit)
    selected_ids.add(unit_id)
    return True


def _choose_sample_units(
    candidate_id: str,
    eligible: Sequence[Mapping[str, Any]],
    positions: Mapping[str, int],
    max_units: int,
    missing: Sequence[str],
) -> tuple[list[Mapping[str, Any]], dict[str, list[str]], Mapping[str, Any] | None, Mapping[str, Any] | None, Mapping[str, Any] | None, tuple[str, ...], list[dict[str, str]]]:
    reasons: dict[str, list[str]] = {}
    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()
    first = eligible[0] if eligible else None
    last = eligible[-1] if eligible else None
    if first is not None:
        _mark_sample(first, "first_occurrence", selected, selected_ids, reasons, max_units)
    if last is not None:
        _mark_sample(last, "last_occurrence", selected, selected_ids, reasons, max_units)
    group_first: dict[str, Mapping[str, Any]] = {}
    for unit in eligible:
        for group_id in _groups(unit):
            group_first.setdefault(group_id, unit)
    diagnostics = [
        _diagnostic(candidate_id, "candidate_local_unit_not_found", f"Dropped candidate reference to unknown local unit {unit_id!r}.")
        for unit_id in missing
    ]
    all_groups = tuple(sorted(group_first))
    for group_id in all_groups:
        if not _mark_sample(group_first[group_id], f"event_group:{group_id}", selected, selected_ids, reasons, max_units):
            diagnostics.append(_diagnostic(candidate_id, "sampling_event_group_budget_limited", f"Unit budget prevented selecting event group {group_id!r}."))
    high = max(eligible, key=lambda unit: (_density_key(_source_text(unit)), -positions[_unit_id(unit)]), default=None)
    if high is not None:
        _mark_sample(high, "high_information_density", selected, selected_ids, reasons, max_units)
    remaining = [unit for unit in eligible if _unit_id(unit) not in selected_ids]
    remaining.sort(key=lambda unit: (_density_key(_source_text(unit)), -positions[_unit_id(unit)]), reverse=True)
    for unit in remaining:
        if not _mark_sample(unit, "budget_fill", selected, selected_ids, reasons, max_units):
            break
    selected.sort(key=lambda unit: (_unit_order(unit, positions[_unit_id(unit)]), positions[_unit_id(unit)]))
    if not eligible:
        diagnostics.append(_diagnostic(candidate_id, "candidate_has_no_existing_local_units", "Digest request contains compact context without source units."))
    return selected, reasons, first, last, high, all_groups, diagnostics


def _allocate_source_chars(selected: Sequence[Mapping[str, Any]], max_source_chars: int) -> list[int]:
    allocations = [0] * len(selected)
    remaining_chars = max_source_chars
    remaining_slots = len(selected)
    for index, unit in enumerate(selected):
        if remaining_chars <= 0:
            break
        text = _source_text(unit)
        take = min(len(text), max(1, remaining_chars // remaining_slots))
        allocations[index] = take
        remaining_chars -= take
        remaining_slots -= 1
    while remaining_chars > 0:
        made_progress = False
        for index, unit in enumerate(selected):
            capacity = len(_source_text(unit)) - allocations[index]
            if capacity <= 0:
                continue
            take = min(capacity, remaining_chars)
            allocations[index] += take
            remaining_chars -= take
            made_progress = True
            if remaining_chars == 0:
                break
        if not made_progress:
            break
    return allocations


def _sampled_payload(
    selected: Sequence[Mapping[str, Any]],
    allocations: Sequence[int],
    reasons: Mapping[str, Sequence[str]],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    sampled: list[dict[str, Any]] = []
    truncated_ids: list[str] = []
    for unit, allocation in zip(selected, allocations, strict=True):
        unit_id = _unit_id(unit)
        text = _source_text(unit)
        truncated = allocation < len(text)
        if truncated:
            truncated_ids.append(unit_id)
        sampled.append({
            "unit_id": unit_id,
            "source_text": text[:allocation],
            "event_group_ids": _groups(unit),
            "batch_index": _batch_index(unit),
            "selection_reasons": tuple(reasons.get(unit_id, ())),
            "original_char_count": len(text),
            "included_char_count": allocation,
            "truncated": truncated,
        })
    return sampled, tuple(truncated_ids)


def sample_entity_units(
    candidate_id: str,
    candidate_unit_ids: Sequence[str],
    local_units: Sequence[Mapping[str, Any]],
    *,
    max_units: int = 12,
    max_source_chars: int = 8_000,
) -> dict[str, Any]:
    """Select first/last, event-group and high-density evidence deterministically."""

    _validate_budgets(max_units, max_source_chars)
    requested, eligible, positions, missing = _ordered_units(candidate_unit_ids, local_units)
    selected, reasons, first, last, high, all_groups, diagnostics = _choose_sample_units(
        candidate_id, eligible, positions, max_units, missing,
    )
    sampled, truncated_ids = _sampled_payload(
        selected, _allocate_source_chars(selected, max_source_chars), reasons,
    )
    covered_groups = tuple(sorted({group for unit in sampled for group in unit["event_group_ids"]}))
    return {
        "units": tuple(sampled),
        "metadata": {
            "sampler_version": "context-tree-v2-entity-sampling-v1",
            "candidate_id": candidate_id,
            "eligible_unit_count": len(eligible),
            "selected_unit_count": len(sampled),
            "original_char_count": sum(len(_source_text(unit)) for unit in eligible),
            "included_char_count": sum(item["included_char_count"] for item in sampled),
            "unit_budget": max_units,
            "source_char_budget": max_source_chars,
            "first_occurrence_unit_id": _unit_id(first) if first else None,
            "last_occurrence_unit_id": _unit_id(last) if last else None,
            "high_information_density_unit_id": _unit_id(high) if high else None,
            "covered_event_group_ids": covered_groups,
            "omitted_event_group_ids": tuple(group for group in all_groups if group not in covered_groups),
            "selection_reasons": {unit_id: tuple(values) for unit_id, values in reasons.items()},
            "truncated_unit_ids": truncated_ids,
        },
        "diagnostics": diagnostics,
    }


def _segment_entries(eligible: Sequence[Mapping[str, Any]], max_source_chars: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for unit in eligible:
        unit_id = _unit_id(unit)
        text = _source_text(unit)
        batch = _batch_index(unit)
        if len(text) <= max_source_chars:
            entries.append(_segment_entry(unit_id, text, unit, batch, False, 0))
            continue
        start = 0
        part = 0
        while start < len(text):
            chunk = text[start:start + max_source_chars]
            entries.append(_segment_entry(unit_id, chunk, unit, batch, True, part, len(text)))
            start += len(chunk)
            part += 1
    return entries


def _segment_entry(
    unit_id: str,
    text: str,
    unit: Mapping[str, Any],
    batch: int | None,
    force_flush: bool,
    part: int,
    original_length: int | None = None,
) -> dict[str, Any]:
    reasons = ["segment_evidence"]
    if force_flush:
        reasons.extend(("oversized_unit_part", f"part:{part}"))
    if batch is not None:
        reasons.append(f"batch:{batch}")
    return {
        "unit_id": unit_id,
        "source_text": text,
        "event_group_ids": _groups(unit),
        "selection_reasons": tuple(reasons),
        "original_char_count": original_length if original_length is not None else len(text),
        "included_char_count": len(text),
        "truncated": force_flush and len(text) < (original_length or len(text)),
        "batch_index": batch,
        "force_flush": force_flush,
    }


def _segment_record(
    candidate_id: str,
    index: int,
    current: Sequence[Mapping[str, Any]],
    eligible: Sequence[Mapping[str, Any]],
    max_units: int,
    max_source_chars: int,
    diagnostics: Sequence[dict[str, str]],
) -> dict[str, Any]:
    segment_id = f"{candidate_id}::segment-{index:04d}"
    batch_indexes = tuple(sorted({item["batch_index"] for item in current if item["batch_index"] is not None}))
    return {
        "segment_id": segment_id,
        "units": tuple({key: value for key, value in item.items() if key != "force_flush"} for item in current),
        "metadata": {
            "sampler_version": "context-tree-v2-entity-segmentation-v1",
            "candidate_id": candidate_id,
            "eligible_unit_count": len(eligible),
            "selected_unit_count": len(current),
            "original_char_count": sum(item["original_char_count"] for item in current),
            "included_char_count": sum(item["included_char_count"] for item in current),
            "unit_budget": max_units,
            "source_char_budget": max_source_chars,
            "first_occurrence_unit_id": _unit_id(eligible[0]) if eligible else None,
            "last_occurrence_unit_id": _unit_id(eligible[-1]) if eligible else None,
            "high_information_density_unit_id": None,
            "covered_event_group_ids": tuple(sorted({group for item in current for group in item["event_group_ids"]})),
            "omitted_event_group_ids": (),
            "selection_reasons": {item["unit_id"]: item["selection_reasons"] for item in current},
            "truncated_unit_ids": tuple(item["unit_id"] for item in current if item["truncated"]),
            "digest_segment_id": segment_id,
            "batch_indexes": batch_indexes,
            "consumes_all_evidence": False,
        },
        "diagnostics": tuple(diagnostics if index == 0 else ()),
    }


def _pack_segment_entries(
    candidate_id: str,
    entries: Sequence[Mapping[str, Any]],
    eligible: Sequence[Mapping[str, Any]],
    max_units: int,
    max_source_chars: int,
    diagnostics: Sequence[dict[str, str]],
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: list[Mapping[str, Any]] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if current:
            segments.append(_segment_record(candidate_id, len(segments), current, eligible, max_units, max_source_chars, diagnostics))
            current = []
            current_chars = 0

    for entry in entries:
        text_length = len(entry["source_text"])
        if current and (len(current) >= max_units or current_chars + text_length > max_source_chars):
            flush()
        current.append(entry)
        current_chars += text_length
        if entry["force_flush"]:
            flush()
    flush()
    return segments


def _empty_segment(
    candidate_id: str,
    max_units: int,
    max_source_chars: int,
    diagnostics: Sequence[dict[str, str]],
) -> dict[str, Any]:
    segment_id = f"{candidate_id}::segment-0000"
    return {
        "segment_id": segment_id,
        "units": (),
        "metadata": {
            "sampler_version": "context-tree-v2-entity-segmentation-v1",
            "candidate_id": candidate_id,
            "eligible_unit_count": 0,
            "selected_unit_count": 0,
            "original_char_count": 0,
            "included_char_count": 0,
            "unit_budget": max_units,
            "source_char_budget": max_source_chars,
            "digest_segment_id": segment_id,
            "batch_indexes": (),
            "consumes_all_evidence": True,
        },
        "diagnostics": tuple(diagnostics),
    }


def segment_entity_units(
    candidate_id: str,
    candidate_unit_ids: Sequence[str],
    local_units: Sequence[Mapping[str, Any]],
    *,
    max_units: int = 12,
    max_source_chars: int = 8_000,
) -> list[dict[str, Any]]:
    """Partition all known evidence into lossless bounded digest segments."""

    _validate_budgets(max_units, max_source_chars)
    _, eligible, positions, missing = _ordered_units(candidate_unit_ids, local_units)
    eligible.sort(key=lambda unit: (
        _batch_index(unit) if _batch_index(unit) is not None else 10**9,
        _unit_order(unit, positions[_unit_id(unit)]),
        positions[_unit_id(unit)],
    ))
    diagnostics = [
        _diagnostic(candidate_id, "candidate_local_unit_not_found", f"Dropped candidate reference to unknown local unit {unit_id!r}.")
        for unit_id in missing
    ]
    entries = _segment_entries(eligible, max_source_chars)
    segments = _pack_segment_entries(candidate_id, entries, eligible, max_units, max_source_chars, diagnostics)
    if not segments:
        segments = [_empty_segment(candidate_id, max_units, max_source_chars, diagnostics)]
    segments[-1]["metadata"]["consumes_all_evidence"] = True
    return segments


def build_program_project_overview(
    project_title: str,
    human_summary: str | None,
    event_groups: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    unit_summaries: Sequence[Mapping[str, Any]],
    *,
    max_chars: int = 2_000,
) -> dict[str, Any]:
    """Build a capped human-first overview without another model call."""

    diagnostics: list[dict[str, str]] = []
    if str(human_summary or "").strip():
        text = str(human_summary).strip()
        truncated = len(text) > max_chars
        if truncated:
            diagnostics.append({"code": "project_summary_truncated", "detail": "Human summary was capped."})
        return {"text": text[:max_chars], "source": "human", "char_count": min(len(text), max_chars), "truncated": truncated, "parts": ("human_project_summary",), "diagnostics": diagnostics}
    title = str(project_title or "").strip() or "Untitled project"
    parts = [f"Project: {title}"]
    if isinstance(event_groups, Mapping):
        groups = event_groups.items()
    else:
        groups = (
            (
                _field(group, "group_id", "event_group_id", "id", default=f"group_{index}"),
                _field(group, "summary", "description", "text", default=""),
            )
            for index, group in enumerate(event_groups or ())
        )
    for group_id, summary in groups:
        if str(summary or "").strip():
            parts.append(f"Event group {group_id}: {str(summary).strip()}")
    for unit in unit_summaries:
        summary = str(_field(unit, "summary", "fragment_summary", default="")).strip()
        if summary:
            parts.append(f"Local fragment {_field(unit, 'unit_id')}: {summary}")
    text = "\n".join(parts)
    truncated = len(text) > max_chars
    if truncated:
        diagnostics.append({"code": "generated_project_overview_truncated", "detail": "Fallback overview was capped."})
    return {"text": text[:max_chars], "source": "generated", "char_count": min(len(text), max_chars), "truncated": truncated, "parts": tuple(parts), "diagnostics": diagnostics}


__all__ = ["build_program_project_overview", "sample_entity_units", "segment_entity_units"]
