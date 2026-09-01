"""Pure finding identity merges and packet-authorized targeted repairs."""

from __future__ import annotations

from typing import Any

from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_repair_policy import RepairPacket


_FINDING_COLLECTIONS = {
    "archive_narrative": ("archive_narratives", "narrative_id"),
    "entity": ("entities", "entity_id"),
    "event_chain": ("event_chains", "chain_id"),
    "reference_asset": ("reference_assets", "asset_id"),
    "unresolved": ("unresolved", "unresolved_id"),
}


def _finding_identity(kind: str, finding: Any) -> tuple[Any, ...]:
    if kind == "event_chains":
        return finding.chain_id, finding.sequence
    field = {
        "archive_narratives": "narrative_id",
        "entities": "entity_id",
        "reference_assets": "asset_id",
        "unresolved": "unresolved_id",
    }[kind]
    return (getattr(finding, field),)


def merge_findings(first: Any, second: Any) -> ContextResearchFindings:
    """Retain first-pass work and let a completion pass refine by identity."""

    values: dict[str, Any] = {}
    for kind in (
        "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
    ):
        merged = {_finding_identity(kind, item): item for item in getattr(first, kind)}
        merged.update({_finding_identity(kind, item): item for item in getattr(second, kind)})
        values[kind] = tuple(merged.values())
    diagnostics = dict(getattr(first, "diagnostics", {}) or {})
    diagnostics.update(dict(getattr(second, "diagnostics", {}) or {}))
    values["diagnostics"] = diagnostics
    return ContextResearchFindings.model_validate(values)


def _target_candidate(repairs: ContextResearchFindings, target: Any) -> Any | None:
    collection, id_field = _FINDING_COLLECTIONS[target.finding_type]
    for item in getattr(repairs, collection):
        if str(getattr(item, id_field)) != target.finding_id:
            continue
        if target.finding_type != "event_chain" or item.sequence == target.sequence:
            return item
    return None


def apply_targeted_repairs(
    findings: ContextResearchFindings,
    repairs: ContextResearchFindings,
    packet: RepairPacket,
) -> ContextResearchFindings:
    """Copy only packet-authorized fields from matching repair objects."""

    replacements: dict[tuple[str, str, int | None], Any] = {}
    for target in packet.targets:
        if target.classification != "repairable" or target.finding_type == "system":
            continue
        candidate = _target_candidate(repairs, target)
        if candidate is None:
            continue
        updates: dict[str, Any] = {}
        for field in target.allowed_fields:
            root = field.split(".", 1)[0]
            if root == "source_item_ids":
                continue
            if root == "evidence":
                updates["evidence"] = candidate.evidence
            elif hasattr(candidate, root):
                updates[root] = getattr(candidate, root)
        collection, id_field = _FINDING_COLLECTIONS[target.finding_type]
        replacements[(target.finding_type, target.finding_id, target.sequence)] = (
            collection, id_field, updates
        )
    values = findings.model_dump()
    for target_key, (collection, id_field, updates) in replacements.items():
        if not updates:
            continue
        patched = []
        for item in getattr(findings, collection):
            identity_matches = str(getattr(item, id_field)) == target_key[1]
            sequence_matches = target_key[0] != "event_chain" or item.sequence == target_key[2]
            patched.append(item.model_copy(update=updates) if identity_matches and sequence_matches else item)
        values[collection] = tuple(patched)
    return ContextResearchFindings.model_validate(values)


__all__ = ["apply_targeted_repairs", "merge_findings"]
