"""Conservative global event-step consolidation for Context Research.

Only duplicate compiled steps with identical coverage are merged here.  Longer
story arcs with different local units remain candidates for Lead review.  A
merge candidate needs two of three positive signals—shared entities, narrative
continuity, and adjacent units—and crossing a file boundary requires all three.
The module records the evidence for review; it never infers a chain from one
signal alone.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations
import re
from typing import Any

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_research_contract import EvidenceReference, EventChain


def consolidate_event_steps(
    events: Sequence[EventChain],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
) -> tuple[tuple[EventChain, ...], dict[str, Any]]:
    """Deduplicate exact compiled step coverage and expose Lead candidates."""

    units = _coerce_units(local_units)
    groups: defaultdict[tuple[Any, ...], list[EventChain]] = defaultdict(list)
    unkeyed: list[EventChain] = []
    for event in events:
        key = _duplicate_key(event)
        (groups[key] if key is not None else unkeyed).append(event)

    output: list[EventChain] = []
    duplicate_groups: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key in sorted(groups, key=str):
        members = tuple(sorted(groups[key], key=_event_sort_key))
        if len(members) == 1:
            output.append(members[0])
            continue
        merged, conflict = _merge_duplicate_steps(members)
        output.append(merged)
        duplicate_groups.append({
            "coverage": list(key[2]),
            "sequence": key[0],
            "canonical_chain_id": merged.chain_id,
            "merged_chain_ids": [item.chain_id for item in members],
        })
        if conflict:
            conflicts.append(conflict)

    output.extend(unkeyed)
    output = sorted(output, key=_event_sort_key)
    raw_candidates = _chain_merge_candidates(output, units)
    candidates = _compress_candidate_edges(raw_candidates)
    components, boundary_doubts = _compress_review_candidates(candidates, output, units)
    diagnostics = {
        "schema_version": "context-research-chain-consolidator-v1",
        "automatic_duplicate_merge_count": sum(
            len(group["merged_chain_ids"]) - 1 for group in duplicate_groups
        ),
        "duplicate_groups": duplicate_groups,
        "event_summary_conflicts": conflicts,
        "lead_review_candidates": components,
        "lead_review_components": components,
        "boundary_doubts": boundary_doubts,
        "candidate_edge_count": len(candidates),
        "raw_candidate_edge_count": len(raw_candidates),
        "candidate_edges": candidates,
    }
    return tuple(output), diagnostics


def _compress_review_candidates(
    candidates: Sequence[dict[str, Any]],
    events: Sequence[EventChain],
    units: Mapping[str, LocalTextUnit],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn candidate edges into component-level review units.

    The graph is used only to group related evidence.  It never authorizes an
    automatic merge, so a component remains one Lead decision regardless of
    how many pairwise edges produced it.
    """
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for candidate in candidates:
        left, right = candidate["event_a"], candidate["event_b"]
        union(left, right)

    by_ref = {f"{event.chain_id}:{event.sequence}": event for event in events}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[find(candidate["event_a"])].append(candidate)

    components: list[dict[str, Any]] = []
    boundary_doubts: list[dict[str, Any]] = []
    for index, edges in enumerate(sorted(grouped.values(), key=_component_sort_key), 1):
        refs = sorted({ref for edge in edges for ref in (edge["event_a"], edge["event_b"])})
        member_events = [by_ref[ref] for ref in refs if ref in by_ref]
        evidence = _evidence_summary(member_events)
        signals = sorted({signal for edge in edges for signal in edge["signals"]})
        linkage = _component_linkage_report(member_events, units)
        component = {
            "component_id": f"chain-review-component-{index:03d}",
            "member_chain_ids": sorted({event.chain_id for event in member_events}),
            "member_event_refs": refs,
            "local_unit_ids": sorted({unit_id for edge in edges for unit_id in edge["local_unit_ids"]}),
            "key_families": sorted({family for edge in edges for family in edge["key_families"]}),
            "shared_entity_ids": sorted({entity for edge in edges for entity in edge["shared_entity_ids"]}),
            "signals": signals,
            "candidate_edge_count": len(edges),
            "evidence_summary": evidence,
            "complete_linkage": linkage["complete_linkage"],
            "rejected_pairs": linkage["rejected_pairs"],
            "requires_lead_decision": True,
        }
        components.append(component)
        boundary_reasons = sorted({
            reason
            for edge in edges
            for reason in _boundary_reason_codes(
                edge["signals"], edge["shared_entity_ids"],
            )
        })
        if boundary_reasons:
            boundary_doubts.append({
                "component_id": component["component_id"],
                "member_event_refs": refs,
                "reason_codes": boundary_reasons,
                "evidence_summary": evidence,
            })
        if linkage["rejected_pairs"]:
            boundary_doubts.append({
                "component_id": component["component_id"],
                "member_event_refs": refs,
                "reason_codes": sorted({
                    reason
                    for pair in linkage["rejected_pairs"]
                    for reason in pair["reason_codes"]
                }),
                "rejected_pairs": linkage["rejected_pairs"],
                "evidence_summary": evidence,
            })
    return components, boundary_doubts


def _component_sort_key(edges: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted(edge["event_a"] for edge in edges) + sorted(edge["event_b"] for edge in edges))


def _boundary_reason_codes(signals: Sequence[str], shared_entities: Sequence[str]) -> list[str]:
    reasons = []
    if "adjacent_local_units" not in signals:
        reasons.append("non_adjacent_units")
    if not shared_entities:
        reasons.append("no_shared_entity")
    if "narrative_continuity" not in signals:
        reasons.append("no_narrative_continuity")
    return reasons


def _evidence_summary(events: Sequence[EventChain]) -> list[dict[str, Any]]:
    summary: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        for evidence in event.evidence:
            key = (
                ",".join(sorted(set(evidence.source_item_ids))),
                evidence.snippet or "", evidence.relative_path or "", evidence.item_key or "",
            )
            summary.setdefault(key, {
                "source_item_ids": sorted(set(evidence.source_item_ids)),
                "snippet": evidence.snippet,
                "relative_path": evidence.relative_path,
                "item_key": evidence.item_key,
            })
    return [summary[key] for key in sorted(summary)]


def _coerce_units(
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
) -> dict[str, LocalTextUnit]:
    if isinstance(local_units, Mapping):
        return {str(key): value for key, value in local_units.items()}
    return {str(unit.unit_id): unit for unit in local_units}


def _duplicate_key(event: EventChain) -> tuple[Any, ...] | None:
    coverage = tuple(sorted(set(event.local_unit_ids)))
    if coverage:
        return event.sequence, "local_units", coverage
    source_coverage = tuple(sorted(set(event.source_item_ids)))
    if source_coverage:
        return event.sequence, "source_items", source_coverage
    return None


def _merge_duplicate_steps(
    members: Sequence[EventChain],
) -> tuple[EventChain, dict[str, Any] | None]:
    canonical = min(members, key=_event_sort_key)
    merged = canonical.model_copy(update={
        "source_item_ids": _sorted_unique(
            source_id for item in members for source_id in item.source_item_ids
        ),
        "local_unit_ids": _sorted_unique(
            unit_id for item in members for unit_id in item.local_unit_ids
        ),
        "archive_context_ids": _sorted_unique(
            context_id for item in members for context_id in item.archive_context_ids
        ),
        "entity_ids": _sorted_unique(
            entity_id for item in members for entity_id in item.entity_ids
        ),
        "evidence": _merge_evidence(members),
    })
    summaries = {item.event for item in members}
    conflict = None
    if len(summaries) > 1:
        conflict = {
            "chain_ids": [item.chain_id for item in members],
            "sequence": canonical.sequence,
            "event_summaries": sorted(summaries),
        }
    return merged, conflict


def _merge_evidence(members: Sequence[EventChain]) -> tuple[EvidenceReference, ...]:
    values: dict[tuple[str, ...], EvidenceReference] = {}
    for member in members:
        for evidence in member.evidence:
            source_ids = tuple(sorted(set(evidence.source_item_ids)))
            candidate = evidence.model_copy(update={"source_item_ids": source_ids})
            previous = values.get(source_ids)
            if previous is None or _evidence_sort_key(candidate) < _evidence_sort_key(previous):
                values[source_ids] = candidate
    return tuple(values[key] for key in sorted(values))


def _chain_merge_candidates(
    events: Sequence[EventChain],
    units: Mapping[str, LocalTextUnit],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, first in enumerate(events):
        first_families = _families(first, units)
        if not first_families:
            continue
        first_positions = _unit_positions(first, units)
        for second in events[index + 1:]:
            if first.chain_id == second.chain_id:
                continue
            families = first_families & _families(second, units)
            second_positions = _unit_positions(second, units)
            shared_entities = sorted(set(first.entity_ids) & set(second.entity_ids))
            adjacent = bool(first_positions and second_positions) and min(
                abs(left - right) for left in first_positions for right in second_positions
            ) <= 1
            same_file = bool(_file_paths(first, units) & _file_paths(second, units))
            continuity = _narrative_continuity(first.event, second.event)
            positive_signals = sum((bool(shared_entities), continuity, adjacent))
            if positive_signals < 2 or (not same_file and positive_signals < 3):
                continue
            signals = ["same_key_family"] if families else []
            if same_file:
                signals.append("same_file")
            if adjacent:
                signals.append("adjacent_local_units")
            if shared_entities:
                signals.append("shared_entities")
            if continuity:
                signals.append("narrative_continuity")
            candidates.append({
                "event_a": f"{first.chain_id}:{first.sequence}",
                "event_b": f"{second.chain_id}:{second.sequence}",
                "local_unit_ids": sorted(set(first.local_unit_ids) | set(second.local_unit_ids)),
                "key_families": sorted(families),
                "signals": signals,
                "shared_entity_ids": shared_entities,
                "requires_lead_decision": True,
            })
    return candidates[:200]


def _compress_candidate_edges(
    candidates: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep a strongest spanning forest instead of a dense pairwise graph."""

    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        left = str(candidate["event_a"]).rsplit(":", 1)[0]
        right = str(candidate["event_b"]).rsplit(":", 1)[0]
        grouped[tuple(sorted((left, right)))].append(candidate)
    pair_edges = [min(edges, key=_candidate_rank) for edges in grouped.values()]
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    selected = []
    for candidate in sorted(pair_edges, key=_candidate_rank):
        left = str(candidate["event_a"]).rsplit(":", 1)[0]
        right = str(candidate["event_b"]).rsplit(":", 1)[0]
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            continue
        parent[right_root] = left_root
        selected.append(candidate)
    return sorted(selected, key=lambda item: (
        str(item.get("event_a", "")), str(item.get("event_b", "")),
    ))


def _candidate_rank(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    signals = set(candidate.get("signals", ()))
    positive = {
        "shared_entities", "narrative_continuity", "adjacent_local_units",
    }
    shared_count = len(candidate.get("shared_entity_ids", ()))
    positive_count = len(signals & positive)
    adjacent = int("adjacent_local_units" in signals)
    return (
        -shared_count, -positive_count, -adjacent,
        str(candidate.get("event_a", "")), str(candidate.get("event_b", "")),
    )


def validate_event_merge_evidence(
    events: Sequence[Any],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
) -> dict[str, Any]:
    """Validate that selected members form a positively evidenced merge graph."""

    if len(events) < 2:
        return {"allowed": False, "reason": "merge_requires_two_members", "edges": []}
    units = _coerce_units(local_units)
    refs = [_event_ref(event) for event in events]
    adjacency: dict[str, set[str]] = {ref: set() for ref in refs}
    edges = []
    rejected_pairs = []
    for index, first in enumerate(events):
        for second in events[index + 1:]:
            evidence, rejected = _assess_merge_pair(first, second, units)
            left, right = _event_ref(first), _event_ref(second)
            if rejected:
                rejected_pairs.append(rejected)
                continue
            if evidence is None:
                rejected_pairs.append({
                    "event_a": left,
                    "event_b": right,
                    "reason_codes": ["merge_evidence_below_two_of_three"],
                })
                continue
            adjacency[left].add(right)
            adjacency[right].add(left)
            edges.append(evidence)
    if rejected_pairs:
        reason = (
            "merge_rejected_by_negative_evidence"
            if any("negative_evidence" in pair for pair in rejected_pairs)
            else "merge_not_complete_linkage"
        )
        return {
            "allowed": False,
            "reason": reason,
            "edges": edges,
            "rejected_pairs": rejected_pairs,
        }
    if not edges:
        return {
            "allowed": False,
            "reason": "merge_evidence_below_two_of_three",
            "edges": [],
            "rejected_pairs": rejected_pairs,
        }
    seen = {refs[0]}
    pending = [refs[0]]
    while pending:
        current = pending.pop()
        for neighbor in adjacency[current] - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    if len(seen) != len(refs):
        return {
            "allowed": False,
            "reason": "merge_members_not_one_evidence_component",
            "edges": edges,
            "rejected_pairs": rejected_pairs,
        }
    return {
        "allowed": True,
        "reason": "two_of_three_positive_signals",
        "edges": edges,
        "rejected_pairs": rejected_pairs,
        "complete_linkage": True,
    }


def _merge_evidence_for_pair(
    first: Any,
    second: Any,
    units: Mapping[str, LocalTextUnit],
) -> dict[str, Any] | None:
    first_positions = _unit_positions(first, units)
    second_positions = _unit_positions(second, units)
    adjacent = bool(first_positions and second_positions) and min(
        abs(left - right) for left in first_positions for right in second_positions
    ) <= 1
    shared_entities = sorted(set(getattr(first, "entity_ids", ())) & set(getattr(second, "entity_ids", ())))
    continuity = _narrative_continuity(getattr(first, "event", ""), getattr(second, "event", ""))
    same_file = bool(_file_paths(first, units) & _file_paths(second, units))
    positive = sum((bool(shared_entities), continuity, adjacent))
    if positive < 2 or (not same_file and positive < 3):
        return None
    return {
        "event_a": _event_ref(first),
        "event_b": _event_ref(second),
        "positive_signals": sorted(
            signal for signal, present in (
                ("shared_entities", bool(shared_entities)),
                ("narrative_continuity", continuity),
                ("adjacent_local_units", adjacent),
            ) if present
        ),
        "shared_entity_ids": shared_entities,
        "same_file": same_file,
    }


def _assess_merge_pair(
    first: Any,
    second: Any,
    units: Mapping[str, LocalTextUnit],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return positive evidence and deterministic negative evidence for one pair."""

    negative = _negative_evidence_for_pair(first, second, units)
    if negative:
        return None, {
            "event_a": _event_ref(first),
            "event_b": _event_ref(second),
            "reason_codes": [item["code"] for item in negative],
            "negative_evidence": negative,
        }
    return _merge_evidence_for_pair(first, second, units), None


def _component_linkage_report(
    events: Sequence[EventChain], units: Mapping[str, LocalTextUnit],
) -> dict[str, Any]:
    rejected_pairs = []
    for first, second in ((left, right) for left, right in combinations(events, 2)):
        evidence, rejected = _assess_merge_pair(first, second, units)
        if evidence is None:
            rejected_pairs.append(rejected or {
                "event_a": _event_ref(first),
                "event_b": _event_ref(second),
                "reason_codes": ["merge_evidence_below_two_of_three"],
            })
    return {"complete_linkage": not rejected_pairs, "rejected_pairs": rejected_pairs}


def _negative_evidence_for_pair(
    first: Any,
    second: Any,
    units: Mapping[str, LocalTextUnit],
) -> list[dict[str, str]]:
    first_files = _file_paths(first, units)
    second_files = _file_paths(second, units)
    shared_entities = set(getattr(first, "entity_ids", ())) & set(
        getattr(second, "entity_ids", ())
    )
    first_families = _families(first, units)
    second_families = _families(second, units)
    negative: list[dict[str, str]] = []
    if first_files and second_files and not shared_entities and not (
        first_files & second_files or first_families & second_families
    ):
        negative.append({
            "code": "cross_boundary_without_shared_entity",
            "detail": "different files and key prefixes have no shared entity",
        })
    for code, detail in (
        ("mutually_exclusive_branch", "branch markers identify different alternatives"),
        ("different_narrative_timeline", "explicit timeline markers identify different timelines"),
    ):
        if _marker_conflict(first, second, units, code):
            negative.append({"code": code, "detail": detail})
    return negative


def _marker_conflict(
    first: Any,
    second: Any,
    units: Mapping[str, LocalTextUnit],
    kind: str,
) -> bool:
    markers = {
        "mutually_exclusive_branch": ("branch", "option", "choice", "alternative", "route"),
        "different_narrative_timeline": ("timeline", "universe", "reality", "era"),
    }[kind]
    first_values = _marker_values(first, units, markers)
    second_values = _marker_values(second, units, markers)
    return any(
        first_values.get(root, set()) and second_values.get(root, set())
        and first_values[root].isdisjoint(second_values[root])
        for root in set(first_values) & set(second_values)
    )


def _marker_values(
    event: Any,
    units: Mapping[str, LocalTextUnit],
    markers: Sequence[str],
) -> dict[str, set[str]]:
    values: defaultdict[str, set[str]] = defaultdict(set)
    pattern = re.compile(
        rf"(?:^|[._/:-])({'|'.join(markers)})[._/:-]?([a-z0-9-]+)",
        re.IGNORECASE,
    )
    texts = [str(getattr(event, "event", ""))]
    for unit_id in getattr(event, "local_unit_ids", ()):
        unit = units.get(unit_id)
        for item in getattr(unit, "items", ()):
            texts.extend((str(getattr(item, "relative_path", "")), str(getattr(item, "item_key", ""))))
    for text in texts:
        for match in pattern.finditer(text.casefold()):
            values[match.group(1)].add(match.group(2))
    return values


def _file_paths(event: Any, units: Mapping[str, LocalTextUnit]) -> set[str]:
    return {
        str(item.relative_path).casefold()
        for unit_id in getattr(event, "local_unit_ids", ())
        for item in getattr(units.get(unit_id), "items", ())
        if getattr(item, "relative_path", None)
    }


def _narrative_continuity(first: Any, second: Any) -> bool:
    first_tokens = _narrative_tokens(first)
    second_tokens = _narrative_tokens(second)
    return bool(first_tokens & second_tokens)


def _narrative_tokens(value: Any) -> set[str]:
    text = str(value or "").casefold()
    tokens = set(re.findall(r"[a-z][a-z0-9_-]{3,}|[\u4e00-\u9fff]{2,}", text))
    return tokens - {
        "event", "step", "chain", "事件", "步骤", "发生", "之后", "然后",
        "the", "this", "that", "with", "from", "into", "will", "after",
    }


def _event_ref(event: Any) -> str:
    return f"{event.chain_id}:{event.sequence}"


def _families(event: EventChain, units: Mapping[str, LocalTextUnit]) -> set[str]:
    return {
        family
        for unit_id in event.local_unit_ids
        for family in [_family(units.get(unit_id).unit_key if unit_id in units else "")]
        if family
    }


def _unit_positions(event: EventChain, units: Mapping[str, LocalTextUnit]) -> tuple[int, ...]:
    return tuple(
        int(match.group(1))
        for unit_id in event.local_unit_ids
        if (match := re.fullmatch(r"unit_(\d+)", unit_id))
    )


def _family(unit_key: str) -> str:
    value = str(unit_key).split("::", 1)[-1].casefold()
    segments = [segment for segment in value.split(".") if segment]
    numeric = next((index for index, segment in enumerate(segments) if segment.isdigit()), None)
    if numeric is not None:
        return ".".join(segments[:numeric])
    return re.sub(r"[._](?:title|name|desc|description|tooltip)$", "", value)


def _sorted_unique(values: Sequence[str] | Any) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _event_sort_key(event: EventChain) -> tuple[str, int, str, str]:
    return (
        event.chain_id.casefold(), event.sequence,
        ",".join(sorted(event.local_unit_ids or event.source_item_ids)), event.event,
    )


def _evidence_sort_key(evidence: EvidenceReference) -> tuple[str, str, str]:
    return evidence.snippet or "", evidence.relative_path or "", evidence.item_key or ""


__all__ = ["consolidate_event_steps", "validate_event_merge_evidence"]
