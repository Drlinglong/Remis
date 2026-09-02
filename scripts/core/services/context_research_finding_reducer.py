"""Apply sparse Lead decisions to collected child findings.

The shard collector owns evidence and unit ownership.  This module only applies
explicit Lead decisions on top of that result; it never treats an omitted
finding as permission to rewrite or discard it.  Invalid identities and patch
fields are diagnostics, not reasons to throw away the remaining research.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_lead_decisions import (
    EntityMergeDecision,
    EventMemberDecision,
    FindingDiscardDecision,
    FindingPatchDecision,
    LeadResearchDecisions,
    LeadResearchResult,
)
from scripts.core.services.context_research_shard_memo import ShardMemoCollection


_KINDS = (
    "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
)
_PATCH_FIELDS = {
    "archive_narratives": frozenset({"summary"}),
    "entities": frozenset({"name", "summary", "aliases", "importance"}),
    "event_chains": frozenset({"event", "local_unit_ids", "archive_context_ids", "entity_ids"}),
    "reference_assets": frozenset({"name", "description"}),
    "unresolved": frozenset({"reason", "repair_detail"}),
}
_IDENTITY_FIELDS = {
    "archive_narratives": "narrative_id",
    "entities": "entity_id",
    "event_chains": "chain_id",
    "reference_assets": "asset_id",
    "unresolved": "unresolved_id",
}
_REDUCER_VERSION = "context-research-finding-reducer-v1"


class ContextResearchFindingReducer:
    """Small stateless facade for callers that prefer a service object."""

    def reduce(
        self,
        collected: ShardMemoCollection | ContextResearchFindings,
        lead: LeadResearchResult | LeadResearchDecisions | Mapping[str, Any] | None = None,
        *,
        local_units: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> ContextResearchFindings:
        return reduce_findings(collected, lead, local_units=local_units)


def reduce_findings(
    collected: ShardMemoCollection | ContextResearchFindings,
    lead: LeadResearchResult | LeadResearchDecisions | Mapping[str, Any] | None = None,
    *,
    local_units: Mapping[str, Any] | Sequence[Any] | None = None,
) -> ContextResearchFindings:
    """Apply explicit Lead decisions while retaining all unmentioned findings.

    ``collected`` is normally a :class:`ShardMemoCollection`; accepting the
    underlying findings as well keeps the reducer usable in focused tests and
    in a future persisted-memo replay path.  Mapping input is best-effort: a
    malformed decision set is recorded and the collected findings are returned.
    """

    source = collected.findings if isinstance(collected, ShardMemoCollection) else collected
    findings = source if isinstance(source, ContextResearchFindings) else ContextResearchFindings.model_validate(source)
    decisions, diagnostics = _coerce_decisions(lead)
    values = {kind: list(getattr(findings, kind)) for kind in _KINDS}
    event_stats = _apply_event_members(
        values, decisions.event_members, diagnostics, local_units=local_units,
    )
    entity_stats = _apply_entity_merges(values, decisions.entity_merges, diagnostics)
    discard_stats = _apply_discards(values, decisions.discards, diagnostics)
    patch_stats = _apply_patches(values, decisions.patches, diagnostics)
    if isinstance(lead, LeadResearchResult):
        patch_stats += _apply_repair_patches(values, lead, diagnostics)

    diagnostics = _stable_diagnostics(diagnostics)
    merged_diagnostics = dict(findings.diagnostics or {})
    prior = dict(merged_diagnostics.get("reducer", {}) or {})
    prior.update({
        "schema_version": _REDUCER_VERSION,
        "event_members_applied": event_stats,
        "entity_merges_applied": entity_stats,
        "discards_applied": discard_stats,
        "patches_applied": patch_stats,
        **diagnostics,
    })
    merged_diagnostics["reducer"] = prior
    return ContextResearchFindings.model_validate({**values, "diagnostics": merged_diagnostics})


def _coerce_decisions(value: Any) -> tuple[LeadResearchDecisions, dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "unknown_identities": [], "invalid_fields": [], "conflicts": [], "invalid_decisions": [],
    }
    if value is None:
        return LeadResearchDecisions(), diagnostics
    if isinstance(value, LeadResearchResult):
        return value.decisions, diagnostics
    if isinstance(value, LeadResearchDecisions):
        return value, diagnostics
    try:
        if isinstance(value, Mapping) and any(
            key in value for key in ("event_members", "entity_merges", "discards", "patches")
        ):
            return LeadResearchDecisions.model_validate(value), diagnostics
        parsed = LeadResearchResult.model_validate(value)
    except ValidationError as error:
        diagnostics["invalid_decisions"].append(str(error)[:1_000])
        return LeadResearchDecisions(), diagnostics
    return parsed.decisions, diagnostics


def _apply_event_members(
    values,
    decisions: Sequence[EventMemberDecision],
    diagnostics,
    *,
    local_units: Mapping[str, Any] | Sequence[Any] | None = None,
) -> int:
    applied = 0
    events = values["event_chains"]
    for decision in decisions:
        selected, unknown = _select_events(events, decision)
        diagnostics["unknown_identities"].extend(unknown)
        if not selected:
            continue
        if local_units is not None:
            from scripts.core.services.context_research_chain_consolidation import (
                validate_event_merge_evidence,
            )

            evidence = validate_event_merge_evidence(selected, local_units)
            if not evidence["allowed"]:
                diagnostics.setdefault("merge_evidence_rejections", []).append({
                    "chain_id": decision.chain_id,
                    "sequence": decision.sequence,
                    "member_event_refs": [
                        f"{item.chain_id}:{item.sequence}" for item in selected
                    ],
                    "reason": evidence["reason"],
                    "edges": evidence["edges"],
                    "rejected_pairs": evidence.get("rejected_pairs", []),
                })
                continue
            lead_evidence_error = _validate_lead_merge_evidence(
                decision, selected, evidence,
            )
            if lead_evidence_error is not None:
                diagnostics.setdefault("merge_evidence_rejections", []).append({
                    "chain_id": decision.chain_id,
                    "sequence": decision.sequence,
                    "member_event_refs": [
                        f"{item.chain_id}:{item.sequence}" for item in selected
                    ],
                    "reason": lead_evidence_error,
                    "edges": evidence["edges"],
                })
                continue
            diagnostics.setdefault("merge_evidence_acceptances", []).append({
                "chain_id": decision.chain_id,
                "sequence": decision.sequence,
                "member_event_refs": [
                    f"{item.chain_id}:{item.sequence}" for item in selected
                ],
                "edges": evidence["edges"],
                "lead_positive_evidence": [
                    item.model_dump(mode="json") for item in decision.positive_evidence
                ],
            })
        target = (decision.chain_id, decision.sequence)
        if any((item.chain_id, item.sequence) == target for item in events if item not in selected):
            diagnostics["conflicts"].append(f"event_chains:{decision.chain_id}:{decision.sequence}")
            continue
        merged = _merge_events(selected, decision, diagnostics)
        first_index = min(events.index(item) for item in selected)
        events[:] = [item for item in events if item not in selected]
        events.insert(first_index, merged)
        applied += 1
    return applied


def _validate_lead_merge_evidence(
    decision: EventMemberDecision,
    selected: Sequence[Any],
    verified: Mapping[str, Any],
) -> str | None:
    """Ensure the Lead supplied every deterministic signal it claimed to use."""

    supplied = decision.positive_evidence
    if not supplied:
        return "lead_merge_evidence_missing"
    verified_signals = {
        signal
        for edge in verified.get("edges", ())
        for signal in edge.get("positive_signals", ())
    }
    supplied_signals = {item.signal for item in supplied}
    if supplied_signals != verified_signals or len(supplied_signals) < 2:
        return "lead_merge_evidence_mismatch"
    selected_entities = set().union(*(set(item.entity_ids) for item in selected))
    selected_units = set().union(*(set(item.local_unit_ids) for item in selected))
    selected_sources = set().union(*(
        {
            source_id
            for evidence in item.evidence
            for source_id in evidence.source_item_ids
        }
        for item in selected
    ))
    for item in supplied:
        if not set(item.entity_ids) <= selected_entities:
            return "lead_merge_evidence_unknown_entity"
        if not set(item.local_unit_ids) <= selected_units:
            return "lead_merge_evidence_unknown_local_unit"
        if not set(item.source_item_ids) <= selected_sources:
            return "lead_merge_evidence_unknown_source"
        if item.signal == "shared_entities" and not item.entity_ids:
            return "lead_merge_evidence_missing_entity_detail"
        if item.signal == "adjacent_local_units" and not item.local_unit_ids:
            return "lead_merge_evidence_missing_adjacency_detail"
        if item.signal == "narrative_continuity" and not item.detail:
            return "lead_merge_evidence_missing_narrative_detail"
    return None


def _select_events(events, decision: EventMemberDecision):
    selected = []
    unknown = []
    by_identity = {(item.chain_id, item.sequence): item for item in events}
    for raw in decision.finding_ids:
        identity = _event_identity(raw)
        item = by_identity.get(identity) if identity is not None else None
        if item is None:
            unknown.append(f"event_chains:{raw}")
        elif item not in selected:
            selected.append(item)
    for unit_id in decision.local_unit_ids:
        matches = [item for item in events if unit_id in item.local_unit_ids]
        if not matches:
            unknown.append(f"event_local_unit:{unit_id}")
        for item in matches:
            if item not in selected:
                selected.append(item)
    return selected, unknown


def _event_identity(value: str) -> tuple[str, int] | None:
    text = str(value).strip()
    if text.startswith("event_chains:"):
        text = text[len("event_chains:"):]
    chain, separator, sequence = text.rpartition(":")
    if not separator or not chain:
        return None
    try:
        return chain, int(sequence)
    except ValueError:
        return None


def _merge_events(items, decision, diagnostics):
    first = items[0]
    updates = {
        "chain_id": decision.chain_id,
        "sequence": decision.sequence,
        "local_unit_ids": _union(*(item.local_unit_ids for item in items)),
        "archive_context_ids": _union(*(item.archive_context_ids for item in items)),
        "entity_ids": _union(*(item.entity_ids for item in items)),
        "evidence": _merge_evidence(items, diagnostics),
    }
    requested_units = set(decision.local_unit_ids)
    observed_units = set(updates["local_unit_ids"])
    missing_units = sorted(requested_units - observed_units)
    diagnostics["unknown_identities"].extend(f"event_local_unit:{unit}" for unit in missing_units)
    for item in items[1:]:
        if item.event != first.event:
            diagnostics["conflicts"].append(_label("event_chains", item))
    return first.model_copy(update=updates)


def _apply_entity_merges(values, decisions: Sequence[EntityMergeDecision], diagnostics) -> int:
    applied = 0
    entities = values["entities"]
    for decision in decisions:
        by_id = {item.entity_id: item for item in entities}
        canonical = by_id.get(_plain_identity(decision.canonical_finding_id, "entities"))
        merged = [by_id.get(_plain_identity(item, "entities")) for item in decision.merged_finding_ids]
        if canonical is None:
            diagnostics["unknown_identities"].append(
                f"entities:{decision.canonical_finding_id}"
            )
            continue
        missing = [item for item, resolved in zip(decision.merged_finding_ids, merged) if resolved is None]
        diagnostics["unknown_identities"].extend(f"entities:{item}" for item in missing)
        resolved = [item for item in merged if item is not None and item is not canonical]
        if not resolved:
            continue
        updates = {
            "aliases": _union(
                canonical.aliases,
                *(tuple((item.name, *item.aliases)) for item in resolved),
            ),
            "evidence": _merge_evidence([canonical, *resolved], diagnostics),
        }
        for item in resolved:
            if item.name != canonical.name or item.summary != canonical.summary:
                diagnostics["conflicts"].append(_label("entities", item))
        values["entities"] = [item for item in entities if item not in resolved]
        canonical = canonical.model_copy(update=updates)
        values["entities"][values["entities"].index(by_id[canonical.entity_id])] = canonical
        _rewrite_event_entities(values["event_chains"], {item.entity_id for item in resolved}, canonical.entity_id)
        entities = values["entities"]
        applied += 1
    return applied


def _rewrite_event_entities(events, merged_ids: set[str], canonical_id: str) -> None:
    for index, event in enumerate(events):
        replacement = tuple(
            canonical_id if entity_id in merged_ids else entity_id
            for entity_id in event.entity_ids
        )
        replacement = _union(replacement)
        if replacement != event.entity_ids:
            events[index] = event.model_copy(update={"entity_ids": replacement})


def _apply_discards(values, decisions: Sequence[FindingDiscardDecision], diagnostics) -> int:
    applied = 0
    for decision in decisions:
        kind = decision.finding_kind
        identity = _plain_identity(decision.finding_id, kind)
        items = values[kind]
        kept = [item for item in items if getattr(item, _IDENTITY_FIELDS[kind]) != identity]
        if len(kept) == len(items):
            diagnostics["unknown_identities"].append(f"{kind}:{decision.finding_id}")
            continue
        values[kind] = kept
        applied += 1
    return applied


def _apply_patches(values, decisions: Sequence[FindingPatchDecision], diagnostics) -> int:
    return _apply_patch_values(values, decisions, diagnostics)


def _apply_repair_patches(values, result: LeadResearchResult, diagnostics) -> int:
    return _apply_patch_values(values, result.repair_findings, diagnostics)


def _apply_patch_values(values, decisions, diagnostics) -> int:
    applied = 0
    for decision in decisions:
        kind = decision.finding_kind
        identity = _plain_identity(decision.finding_id, kind)
        allowed = _PATCH_FIELDS[kind]
        invalid = sorted(set(decision.fields) - allowed)
        diagnostics["invalid_fields"].extend({
            "finding_kind": kind, "finding_id": decision.finding_id,
            "field": field, "reason": "field is not patchable",
        } for field in invalid)
        updates = {field: value for field, value in decision.fields.items() if field in allowed}
        items = values[kind]
        index = next((i for i, item in enumerate(items) if getattr(item, _IDENTITY_FIELDS[kind]) == identity), None)
        if index is None:
            diagnostics["unknown_identities"].append(f"{kind}:{decision.finding_id}")
            continue
        if not updates:
            continue
        try:
            candidate = type(items[index]).model_validate({
                **items[index].model_dump(), **updates,
            })
        except ValidationError:
            diagnostics["invalid_fields"].extend({
                "finding_kind": kind, "finding_id": decision.finding_id,
                "field": field, "reason": "field value failed finding validation",
            } for field in updates)
            continue
        items[index] = candidate
        applied += 1
    return applied


def _merge_evidence(items, diagnostics):
    records = {}
    for item in items:
        for evidence in item.evidence:
            key = tuple(evidence.source_item_ids)
            previous = records.get(key)
            if previous is not None and previous.snippet != evidence.snippet:
                diagnostics["conflicts"].append("evidence:" + ",".join(key))
                continue
            records.setdefault(key, evidence)
    return tuple(records[key] for key in sorted(records))


def _plain_identity(value: str, kind: str) -> str:
    prefix = kind + ":"
    return str(value)[len(prefix):] if str(value).startswith(prefix) else str(value)


def _union(*values):
    return tuple(dict.fromkeys(item for group in values for item in group))


def _label(kind: str, item: Any) -> str:
    field = _IDENTITY_FIELDS[kind]
    identity = getattr(item, field)
    if kind == "event_chains":
        identity = f"{identity}:{item.sequence}"
    return f"{kind}:{identity}"


def _stable_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Deduplicate diagnostics without changing their JSON-safe shape."""

    return {
        "unknown_identities": sorted(set(diagnostics["unknown_identities"])),
        "invalid_fields": sorted(
            diagnostics["invalid_fields"],
            key=lambda item: (
                str(item.get("finding_kind")), str(item.get("finding_id")),
                str(item.get("field")), str(item.get("reason")),
            ),
        ),
        "conflicts": sorted(set(diagnostics["conflicts"])),
        "invalid_decisions": list(dict.fromkeys(diagnostics["invalid_decisions"])),
        "merge_evidence_rejections": sorted(
            diagnostics.get("merge_evidence_rejections", []),
            key=lambda item: (
                str(item.get("chain_id")), int(item.get("sequence", 0)),
                str(item.get("reason")),
            ),
        ),
        "merge_evidence_acceptances": sorted(
            diagnostics.get("merge_evidence_acceptances", []),
            key=lambda item: (
                str(item.get("chain_id")), int(item.get("sequence", 0)),
            ),
        ),
    }


__all__ = ["ContextResearchFindingReducer", "reduce_findings"]
