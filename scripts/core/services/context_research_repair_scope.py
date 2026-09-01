"""Trusted source and finding scope helpers for repair policy.

These helpers establish the immutable request boundary before compiler
diagnostics are interpreted.  Diagnostics may narrow that boundary but never
expand it with invented source IDs.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_contract import ContextAnalysisRequest


_FINDING_SPECS = (
    ("archive_narratives", "archive_narrative", "narrative_id"),
    ("entities", "entity", "entity_id"),
    ("event_chains", "event_chain", "chain_id"),
    ("reference_assets", "reference_asset", "asset_id"),
    ("unresolved", "unresolved", "unresolved_id"),
)

TargetIdentity = tuple[str, str, int | None]


def source_snapshot(
    request: ContextAnalysisRequest | None,
    known_source_item_ids: Sequence[str],
    local_units: Sequence[LocalTextUnit],
) -> tuple[frozenset[str], tuple[LocalTextUnit, ...]]:
    """Return the request-owned source IDs and local units used by policy."""

    if request is not None:
        return request.known_source_item_ids, request.local_units
    known = frozenset(unique_strings(known_source_item_ids))
    return known, tuple(local_units)


def coerce_findings(value: Any) -> ContextResearchFindings:
    """Validate a mapping into the compiler's findings contract."""

    if isinstance(value, ContextResearchFindings):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("original_findings must be a ContextResearchFindings or mapping")
    return ContextResearchFindings.model_validate(value)


def compiler_diagnostics(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Flatten the supported compiler/model diagnostic envelope."""

    nested = value.get("compiler")
    if not isinstance(nested, Mapping):
        return value
    merged = dict(nested)
    model = value.get("model")
    if isinstance(model, Mapping):
        for key in ("coverage_dispositions", "coverage"):
            if key in model:
                merged[key] = model[key]
    return merged


def index_findings(findings: ContextResearchFindings) -> dict[TargetIdentity, Any]:
    """Index findings by stable repair identity."""

    index: dict[TargetIdentity, Any] = {}
    for attribute, finding_type, id_field in _FINDING_SPECS:
        for item in getattr(findings, attribute, ()):
            identity = str(getattr(item, id_field, ""))
            if identity:
                sequence = getattr(item, "sequence", None) if finding_type == "event_chain" else None
                index[(finding_type, identity, sequence)] = item
    return index


def unique_strings(values: Sequence[Any]) -> tuple[str, ...]:
    """Normalize and de-duplicate non-empty IDs while preserving order."""

    return tuple(dict.fromkeys(str(value) for value in values if value))


__all__ = [
    "TargetIdentity", "_FINDING_SPECS", "coerce_findings", "compiler_diagnostics",
    "index_findings", "source_snapshot", "unique_strings",
]
