"""Evidence-bound adjudication for deterministic event-chain candidate edges.

The compiler owns candidate generation and hard-negative filtering.  A small,
tool-free Lead call may only choose ``merge`` or ``no_merge`` for the remaining
edges.  This module validates that response and rewrites chain identities while
preserving every event step, unit, sequence, and source reference.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_research_chain_consolidation import (
    _assess_merge_pair,
    _coerce_units,
    _event_ref,
    _unit_positions,
    validate_event_merge_evidence,
)
from scripts.core.services.context_research_lead_decisions import (
    EventChainAdjudicationDecision,
    EventChainAdjudicationResult,
)


def build_event_adjudication_packet(
    events: Sequence[Any],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
    chain_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one bounded evidence packet from compiled candidate edges."""

    units = _coerce_units(local_units)
    by_ref = {_event_ref(event): event for event in events}
    diagnostics = chain_diagnostics or {}
    candidates = tuple(diagnostics.get("candidate_edges", ()) or ())
    components = tuple(diagnostics.get("lead_review_components", ()) or ())
    component_by_ref = _component_index(components)
    edges = []
    missing_refs = []
    for index, candidate in enumerate(candidates, 1):
        left = by_ref.get(str(candidate.get("event_a", "")))
        right = by_ref.get(str(candidate.get("event_b", "")))
        if left is None or right is None:
            missing_refs.append({
                "candidate_index": index,
                "event_a": candidate.get("event_a"),
                "event_b": candidate.get("event_b"),
                "reason": "candidate_event_reference_not_in_compiled_events",
            })
            continue
        positive, negative = _assess_merge_pair(left, right, units)
        edge = _edge_payload(
            index, candidate, left, right, units, component_by_ref,
            positive, negative,
        )
        edges.append(edge)
    eligible = tuple(edge for edge in edges if not edge["hard_rejected"])
    rejected = tuple(edge for edge in edges if edge["hard_rejected"])
    return {
        "schema_version": "context-research-event-adjudication-v1",
        "candidate_count": len(edges),
        "eligible_candidate_count": len(eligible),
        "hard_rejected_candidate_count": len(rejected),
        "component_count": len(components),
        "edges": list(edges),
        "eligible_edges": list(eligible),
        "hard_rejected_edges": list(rejected),
        "missing_event_references": missing_refs,
        "decision_requirements": {
            "one_decision_per_eligible_edge": True,
            "allowed_decisions": ["merge", "no_merge"],
            "merge_positive_signal_minimum": 2,
            "merge_source_ids_must_cover_both_sides": True,
            "hard_rejections_are_not_model_questions": True,
        },
    }


def event_adjudication_prompt(packet: Mapping[str, Any], language: str = "en") -> str:
    """Render a compact no-tools prompt for one adjudication request."""

    eligible = packet.get("eligible_edges", ())
    return (
        "You are the final evidence adjudicator for an archive event-chain graph. "
        "Do not use tools, delegate, infer missing IDs, or rewrite event text. "
        f"Return EventChainAdjudicationResult only; reasons may use {language}. "
        "Return exactly one decision for every eligible candidate_id. Choose merge only "
        "when the packet's deterministic positive signals are grounded in the two listed "
        "chains and the cited evidence_source_item_ids include at least one source from "
        "each side. Copy IDs exactly. Use positive_signals from the packet and never cite "
        "a hard-rejected edge. Prefer no_merge when the narrative boundary is uncertain. "
        "A merge changes only the chain identity; it must preserve each step's sequence. "
        "Eligible candidate packet: "
        + json.dumps({"eligible_edges": eligible}, ensure_ascii=False, separators=(",", ":"))
    )


def apply_event_chain_adjudications(
    events: Sequence[Any],
    result: EventChainAdjudicationResult | Mapping[str, Any] | None,
    packet: Mapping[str, Any],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Validate a Lead batch and safely unify accepted chain identities."""

    parsed, parse_error = _parse_result(result)
    diagnostics: dict[str, Any] = {
        "schema_version": "context-research-event-adjudication-v1",
        "decision_count": len(parsed.decisions) if parsed else 0,
        "accepted_edges": [],
        "rejected_edges": [],
        "hard_rejected_edges": [
            {"candidate_id": edge.get("candidate_id"), "reason": "hard_negative_evidence"}
            for edge in packet.get("hard_rejected_edges", ())
        ],
        "missing_decisions": [],
        "complete_linkage_rejections": [],
        "canonical_chain_groups": [],
    }
    if parse_error is not None:
        diagnostics["invalid_output"] = parse_error
        diagnostics["status"] = "invalid_output"
        return tuple(events), diagnostics

    edge_by_id = {
        str(edge.get("candidate_id")): edge
        for edge in packet.get("eligible_edges", ())
    }
    decisions = {item.candidate_id: item for item in parsed.decisions}
    accepted: list[tuple[EventChainRef, EventChainRef, EventChainAdjudicationDecision, dict[str, Any]]] = []
    by_ref = {_event_ref(event): event for event in events}
    for candidate_id, decision in decisions.items():
        edge = edge_by_id.get(candidate_id)
        if edge is None:
            diagnostics["rejected_edges"].append({
                "candidate_id": candidate_id,
                "reason": "unknown_or_hard_rejected_candidate",
            })
            continue
        if decision.decision == "no_merge":
            diagnostics["rejected_edges"].append({
                "candidate_id": candidate_id,
                "reason": "lead_no_merge",
                "reason_detail": decision.reason,
            })
            continue
        error = _validate_decision(decision, edge)
        if error is not None:
            diagnostics["rejected_edges"].append({
                "candidate_id": candidate_id,
                "reason": error,
            })
            continue
        left_ref, right_ref = edge["event_a"]["event_ref"], edge["event_b"]["event_ref"]
        if left_ref not in by_ref or right_ref not in by_ref:
            diagnostics["rejected_edges"].append({
                "candidate_id": candidate_id,
                "reason": "candidate_event_reference_not_in_compiled_events",
            })
            continue
        accepted.append((left_ref, right_ref, decision, edge))

    diagnostics["missing_decisions"] = sorted(set(edge_by_id) - set(decisions))
    output, groups = _apply_accepted_groups(
        list(events), accepted, local_units, diagnostics,
    )
    diagnostics["status"] = "completed"
    diagnostics["accepted_edge_count"] = len(diagnostics["accepted_edges"])
    diagnostics["rejected_edge_count"] = len(diagnostics["rejected_edges"])
    diagnostics["hard_rejected_edge_count"] = len(diagnostics["hard_rejected_edges"])
    diagnostics["canonical_chain_groups"] = groups
    return tuple(output), diagnostics


EventChainRef = str


def _parse_result(
    result: EventChainAdjudicationResult | Mapping[str, Any] | None,
) -> tuple[EventChainAdjudicationResult | None, str | None]:
    if result is None:
        return EventChainAdjudicationResult(), None
    if isinstance(result, EventChainAdjudicationResult):
        return result, None
    try:
        return EventChainAdjudicationResult.model_validate(result), None
    except Exception as error:  # compiler diagnostic, never a workflow crash
        return None, f"{type(error).__name__}: {str(error)[:500]}"


def _component_index(components: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        str(ref): str(component.get("component_id", ""))
        for component in components
        for ref in component.get("member_event_refs", ())
    }


def _edge_payload(
    index: int,
    candidate: Mapping[str, Any],
    left: Any,
    right: Any,
    units: Mapping[str, LocalTextUnit],
    component_by_ref: Mapping[str, str],
    positive: Mapping[str, Any] | None,
    negative: Mapping[str, Any] | None,
) -> dict[str, Any]:
    left_ref, right_ref = _event_ref(left), _event_ref(right)
    positive_signals = tuple(positive.get("positive_signals", ())) if positive else ()
    return {
        "candidate_id": f"event-merge-edge-{index:03d}",
        "component_id": component_by_ref.get(left_ref) or component_by_ref.get(right_ref),
        "event_a": _event_side(left, units),
        "event_b": _event_side(right, units),
        "deterministic": {
            "key_families": list(candidate.get("key_families", ())),
            "shared_entity_ids": list(candidate.get("shared_entity_ids", ())),
            "positive_signals": list(positive_signals),
            "adjacency_distance": _adjacency_distance(left, right, units),
            "negative_evidence": negative or {},
        },
        "hard_rejected": negative is not None or not positive_signals,
        "hard_rejection_reason": (
            "negative_evidence" if negative is not None
            else "positive_evidence_below_threshold" if not positive_signals
            else None
        ),
    }


def _event_side(event: Any, units: Mapping[str, LocalTextUnit]) -> dict[str, Any]:
    unit_payload = []
    for unit_id in event.local_unit_ids:
        unit = units.get(unit_id)
        if unit is None:
            continue
        unit_payload.append({
            "unit_id": unit.unit_id,
            "unit_key": unit.unit_key,
            "items": [
                {
                    "source_item_id": item.source_item_id,
                    "relative_path": item.relative_path,
                    "item_key": item.item_key,
                    "source_text": str(item.source_text)[:800],
                }
                for item in unit.items
            ],
        })
    source_ids = sorted(set(event.source_item_ids))
    return {
        "event_ref": _event_ref(event),
        "chain_id": event.chain_id,
        "sequence": event.sequence,
        "event": event.event,
        "local_unit_ids": list(event.local_unit_ids),
        "source_item_ids": source_ids,
        "entity_ids": list(event.entity_ids),
        "units": unit_payload,
    }


def _adjacency_distance(
    left: Any,
    right: Any,
    units: Mapping[str, LocalTextUnit],
) -> int | None:
    left_positions = _unit_positions(left, units)
    right_positions = _unit_positions(right, units)
    if left_positions and right_positions:
        return min(abs(a - b) for a in left_positions for b in right_positions)
    left_orders = _source_orders(left, units)
    right_orders = _source_orders(right, units)
    if not left_orders or not right_orders:
        return None
    return min(abs(a - b) for a in left_orders for b in right_orders)


def _source_orders(event: Any, units: Mapping[str, LocalTextUnit]) -> tuple[int, ...]:
    return tuple(
        int(item.source_order)
        for unit_id in event.local_unit_ids
        for item in getattr(units.get(unit_id), "items", ())
        if item.source_order is not None
    )


def _validate_decision(
    decision: EventChainAdjudicationDecision,
    edge: Mapping[str, Any],
) -> str | None:
    expected = set(edge["deterministic"].get("positive_signals", ()))
    supplied = set(decision.positive_signals)
    if len(supplied) < 2 or supplied != expected:
        return "lead_positive_signals_mismatch"
    left_sources = set(edge["event_a"].get("source_item_ids", ()))
    right_sources = set(edge["event_b"].get("source_item_ids", ()))
    supplied_sources = set(decision.evidence_source_item_ids)
    if not supplied_sources <= left_sources | right_sources:
        return "lead_evidence_source_not_on_candidate_edge"
    if not supplied_sources & left_sources or not supplied_sources & right_sources:
        return "lead_evidence_must_cover_both_chain_sides"
    return None


def _apply_accepted_groups(
    events: list[Any],
    accepted: Sequence[tuple[EventChainRef, EventChainRef, EventChainAdjudicationDecision, dict[str, Any]]],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
    diagnostics: dict[str, Any],
) -> tuple[list[Any], list[dict[str, Any]]]:
    groups = _accepted_chain_groups(accepted)
    units = _coerce_units(local_units)
    summaries = []
    for chain_ids, accepted_edges in groups:
        selected = [event for event in events if event.chain_id in chain_ids]
        validation = validate_event_merge_evidence(selected, units)
        if not validation.get("allowed"):
            diagnostics["complete_linkage_rejections"].append({
                "candidate_ids": [edge[3]["candidate_id"] for edge in accepted_edges],
                "chain_ids": sorted(chain_ids),
                "reason": validation.get("reason"),
                "rejected_pairs": validation.get("rejected_pairs", []),
            })
            diagnostics["rejected_edges"].extend({
                "candidate_id": edge[3]["candidate_id"],
                "reason": "accepted_component_failed_complete_linkage",
            } for edge in accepted_edges)
            continue
        canonical = min(chain_ids)
        events = [
            event.model_copy(update={"chain_id": canonical})
            if event.chain_id in chain_ids else event
            for event in events
        ]
        for _, _, decision, edge in accepted_edges:
            diagnostics["accepted_edges"].append({
                "candidate_id": edge["candidate_id"],
                "chain_ids": sorted(chain_ids),
                "canonical_chain_id": canonical,
                "positive_signals": list(decision.positive_signals),
                "evidence_source_item_ids": list(decision.evidence_source_item_ids),
                "reason": decision.reason,
            })
        summaries.append({
            "canonical_chain_id": canonical,
            "merged_chain_ids": sorted(chain_ids),
            "candidate_ids": [edge[3]["candidate_id"] for edge in accepted_edges],
            "preserved_event_count": len(selected),
        })
    return events, summaries


def _accepted_chain_groups(
    accepted: Sequence[tuple[EventChainRef, EventChainRef, EventChainAdjudicationDecision, dict[str, Any]]],
) -> list[tuple[set[str], list[tuple[EventChainRef, EventChainRef, EventChainAdjudicationDecision, dict[str, Any]]]]]:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    for left_ref, right_ref, _, _ in accepted:
        left_root, right_root = find(left_ref.split(":", 1)[0]), find(right_ref.split(":", 1)[0])
        if left_root != right_root:
            parent[right_root] = left_root
    grouped: defaultdict[str, list[Any]] = defaultdict(list)
    for edge in accepted:
        grouped[find(edge[0].split(":", 1)[0])].append(edge)
    return [
        (
            {ref.split(":", 1)[0] for edge in edges for ref in edge[:2]},
            sorted(edges, key=lambda edge: edge[3]["candidate_id"]),
        )
        for edges in grouped.values()
    ]


__all__ = [
    "apply_event_chain_adjudications",
    "build_event_adjudication_packet",
    "event_adjudication_prompt",
]
