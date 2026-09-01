"""Build bounded, source-grounded repair packets for context research.

This module is deliberately a policy boundary.  It does not call a provider,
rewrite a finding, or decide what a repaired result should say.  It turns the
compiler's diagnostics into a small list of failed objects and the fields and
source IDs a future repair caller is allowed to inspect.  Valid findings are
never copied into the packet and are explicitly protected by the packet
contract.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_research_contract import ContextAnalysisRequest
from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_repair_models import (
    CoverageAssessment,
    CoverageDisposition,
    CoverageKind,
    FailureClass,
    FindingType,
    MAX_REPAIR_ATTEMPTS,
    RepairPacket,
    RepairTarget,
)
from scripts.core.services.context_research_repair_scope import (
    _FINDING_SPECS,
    TargetIdentity,
    coerce_findings as _coerce_findings,
    compiler_diagnostics as _compiler_diagnostics,
    index_findings as _index_findings,
    source_snapshot as _source_snapshot,
    unique_strings as _unique_strings,
)


_REPAIRABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "rejected_source_item_ids": ("evidence.source_item_ids",),
    "rejected_local_unit_ids": ("local_unit_ids",),
    "rejected_asset_local_unit_ids": ("local_unit_id",),
    "unknown_archive_context_links": ("archive_context_ids",),
    "unknown_entity_links": ("entity_ids",),
}

_DISCARD_ONLY_CODES = frozenset({
    "dropped_dynamic_entity_links",
    "rejected_dynamic_entity_candidates",
    "dropped_duplicate_findings",
    "dropped_ungrounded_findings",
    "rejected_entity_evidence_ids",
    "dropped_resolved_unit_routes",
    "embedded_event_uncertainties",
})

_SYSTEMIC_CODES = frozenset({
    "invalid_json", "schema_validation", "contract_validation", "validation_error",
    "systemic_corruption", "malformed_output", "invalid_diagnostics",
})

_NON_FAILURE_CODES = frozenset({
    "schema_version", "published_counts", "uncovered_source_item_ids",
    "coverage_dispositions", "coverage", "model", "inferred_local_unit_ids",
})

_FINDING_SPECS = (
    ("archive_narratives", "archive_narrative", "narrative_id"),
    ("entities", "entity", "entity_id"),
    ("event_chains", "event_chain", "chain_id"),
    ("reference_assets", "reference_asset", "asset_id"),
    ("unresolved", "unresolved", "unresolved_id"),
)


def build_repair_packet(
    compiler_diagnostics: Mapping[str, Any] | Any,
    original_findings: ContextResearchFindings | Mapping[str, Any] | Any,
    *,
    attempt: int = 0,
    key_shards: Sequence[str] = (),
    request: ContextAnalysisRequest | None = None,
    known_source_item_ids: Sequence[str] = (),
    local_units: Sequence[LocalTextUnit] = (),
) -> RepairPacket:
    """Build a bounded packet without changing or copying valid findings.

    ``request`` is the preferred source boundary.  The explicit ID/unit
    arguments are for callers that have already materialized an equivalent
    immutable snapshot.  Diagnostics are never trusted to expand that
    boundary; in particular a hallucinated source ID can only be discarded.
    """

    known_ids, snapshot_units = _source_snapshot(
        request, known_source_item_ids, local_units,
    )

    if not isinstance(compiler_diagnostics, Mapping):
        return _systemic_packet(attempt, key_shards, "invalid_diagnostics")
    try:
        findings = _coerce_findings(original_findings)
    except Exception:
        return _systemic_packet(attempt, key_shards, "invalid_findings")
    compiler = _compiler_diagnostics(compiler_diagnostics)
    finding_index = _index_findings(findings)
    invalid_sources = _invalid_source_ids(compiler)
    targets, systemic_codes = _failure_targets(
        compiler, finding_index, invalid_sources, known_ids, snapshot_units,
    )
    coverage, coverage_error = _build_coverage(compiler, key_shards)
    if coverage_error:
        systemic_codes.append(coverage_error)
    if systemic_codes:
        targets = _add_systemic_target(targets, systemic_codes)
    return _packet(attempt, targets, coverage)


def _invalid_source_ids(diagnostics: Mapping[str, Any]) -> frozenset[str]:
    records = _as_values(diagnostics.get("rejected_source_item_ids"))
    return frozenset(
        str(item.get("source_item_id"))
        for item in records
        if isinstance(item, Mapping) and item.get("source_item_id")
    )


def _failure_targets(
    diagnostics: Mapping[str, Any],
    finding_index: Mapping[TargetIdentity, Any],
    invalid_sources: frozenset[str],
    known_source_ids: frozenset[str],
    local_units: Sequence[LocalTextUnit],
) -> tuple[list[RepairTarget], list[str]]:
    records: OrderedDict[TargetIdentity, dict[str, Any]] = OrderedDict()
    systemic_codes: list[str] = []
    for code, raw_records in diagnostics.items():
        if code in _NON_FAILURE_CODES or not raw_records:
            continue
        details = list(_as_values(raw_records))
        if not isinstance(raw_records, list) and code not in _SYSTEMIC_CODES:
            systemic_codes.append(f"malformed_{code}")
        for detail in details:
            if not isinstance(detail, Mapping):
                systemic_codes.append(f"malformed_{code}")
                continue
            identity = _resolve_identity(detail, finding_index)
            classification = _class_for_code(code, identity, finding_index)
            if classification == "systemic_corruption":
                systemic_codes.append(code)
            _merge_target(
                records, code, detail, identity, classification, invalid_sources,
                known_source_ids, local_units, finding_index,
            )
    return _target_models(records), systemic_codes


def _resolve_identity(
    detail: Mapping[str, Any],
    finding_index: Mapping[TargetIdentity, Any],
) -> TargetIdentity:
    finding_type = _normalize_finding_type(detail.get("finding_type"))
    if not finding_type and detail.get("chain_id"):
        finding_type = "event_chain"
    elif not finding_type and detail.get("entity_id"):
        finding_type = "entity"
    elif not finding_type and detail.get("asset_id"):
        finding_type = "reference_asset"
    identity = _first_value(
        detail.get("finding_id"), detail.get("identity"),
        detail.get("chain_id") if finding_type == "event_chain" else None,
        detail.get("entity_id") if finding_type == "entity" else None,
        detail.get("narrative_id") if finding_type == "archive_narrative" else None,
        detail.get("asset_id") if finding_type == "reference_asset" else None,
        detail.get("unresolved_id") if finding_type == "unresolved" else None,
    )
    if finding_type == "event_chain":
        identity, sequence = _event_identity(detail, identity)
        candidates = [
            key for key in finding_index
            if key[0] == "event_chain" and (not identity or key[1] == identity)
        ]
        if identity and sequence is not None:
            return finding_type, identity, sequence
        if len(candidates) == 1:
            return candidates[0]
        return "system", f"ambiguous_event_identity:{identity or 'unattributed'}", None
    if finding_type and identity:
        return finding_type, identity, None
    candidates = [key for key in finding_index if not finding_type or key[0] == finding_type]
    if len(candidates) == 1:
        return candidates[0]
    fallback_type = finding_type or "system"
    fallback_id = identity or _first_value(detail.get("source_item_id"), "unattributed")
    return fallback_type, fallback_id, None


def _event_identity(
    detail: Mapping[str, Any], identity: str | None,
) -> tuple[str | None, int | None]:
    raw_identity = detail.get("identity")
    if identity and isinstance(raw_identity, str) and raw_identity.startswith("("):
        try:
            parsed = ast.literal_eval(raw_identity)
        except (ValueError, SyntaxError):
            parsed = None
        if isinstance(parsed, tuple) and len(parsed) == 2:
            identity = _first_value(parsed[0])
            identity_sequence = parsed[1]
            if isinstance(identity_sequence, int) and not isinstance(identity_sequence, bool):
                return identity, identity_sequence
    raw_sequence = detail.get("sequence")
    if isinstance(raw_sequence, int) and not isinstance(raw_sequence, bool) and raw_sequence >= 0:
        return identity, raw_sequence
    return identity, None


def _normalize_finding_type(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold()
    aliases = {
        "archive": "archive_narrative", "narrative": "archive_narrative",
        "event": "event_chain", "chain": "event_chain", "asset": "reference_asset",
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {spec[1] for spec in _FINDING_SPECS} | {"system"}
    return normalized if normalized in allowed else None


def _class_for_code(
    code: str,
    identity: TargetIdentity,
    finding_index: Mapping[TargetIdentity, Any],
) -> FailureClass:
    # Explicit compiler-safe drops remain discard-only even when the
    # diagnostic is aggregate/unattributed and therefore has no finding ID.
    # Otherwise a harmless cleanup record is accidentally promoted to
    # systemic corruption merely because identity resolution falls back to
    # the system bucket.
    if code in _DISCARD_ONLY_CODES:
        return "discard_only"
    if identity[0] == "system":
        return "systemic_corruption"
    if code in _REPAIRABLE_FIELDS and identity in finding_index:
        return "repairable"
    return "systemic_corruption"


def _merge_target(
    records: OrderedDict[TargetIdentity, dict[str, Any]],
    code: str,
    detail: Mapping[str, Any],
    identity: TargetIdentity,
    classification: FailureClass,
    invalid_sources: frozenset[str],
    known_source_ids: frozenset[str],
    local_units: Sequence[LocalTextUnit],
    finding_index: Mapping[TargetIdentity, Any],
) -> None:
    record = records.setdefault(identity, {
        "finding_type": identity[0], "finding_id": identity[1], "sequence": identity[2],
        "failure_codes": [],
        "classification": "discard_only", "allowed_fields": [], "source_allow_list": [],
        "related_local_unit_ids": [],
    })
    record["failure_codes"].append(code)
    record["classification"] = _stronger_class(record["classification"], classification)
    if record["classification"] == "systemic_corruption":
        record["allowed_fields"] = []
    elif classification == "repairable":
        record["allowed_fields"].extend(_REPAIRABLE_FIELDS.get(code, ()))
    source_ids = _finding_source_ids(finding_index.get(identity), known_source_ids)
    record["source_allow_list"].extend(
        source_id for source_id in source_ids if source_id not in invalid_sources
    )
    record["source_allow_list"].extend(
        source_id for source_id in _detail_source_ids(detail, invalid_sources)
        if source_id in known_source_ids
    )
    known_unit_ids = {str(unit.unit_id) for unit in local_units}
    related_units = _unique_strings((
        *_detail_local_units(detail),
        *_finding_local_units(finding_index.get(identity)),
    ))
    record["related_local_unit_ids"].extend(
        unit_id for unit_id in related_units if unit_id in known_unit_ids
    )
    record["source_allow_list"].extend(
        source_id
        for source_id in _local_unit_source_ids(
            record["related_local_unit_ids"], local_units, known_source_ids,
        )
        if source_id not in invalid_sources
    )


def _stronger_class(current: FailureClass, candidate: FailureClass) -> FailureClass:
    rank = {"discard_only": 0, "repairable": 1, "systemic_corruption": 2}
    return candidate if rank[candidate] > rank[current] else current


def _finding_source_ids(item: Any, known_source_ids: frozenset[str]) -> tuple[str, ...]:
    if item is None:
        return ()
    values = list(_as_values(getattr(item, "source_item_ids", ())))
    for evidence in _as_values(getattr(item, "evidence", ())):
        values.extend(_as_values(getattr(evidence, "source_item_ids", ())))
    return _unique_strings(value for value in values if value in known_source_ids)


def _detail_source_ids(detail: Mapping[str, Any], invalid: frozenset[str]) -> tuple[str, ...]:
    values = [detail.get("source_item_id"), *_as_values(detail.get("source_item_ids"))]
    return _unique_strings(value for value in values if value and str(value) not in invalid)


def _finding_local_units(item: Any) -> tuple[str, ...]:
    if item is None:
        return ()
    return _unique_strings((
        *_as_values(getattr(item, "local_unit_ids", ())),
        getattr(item, "local_unit_id", None),
    ))


def _detail_local_units(detail: Mapping[str, Any]) -> tuple[str, ...]:
    return _unique_strings((*_as_values(detail.get("local_unit_ids")), detail.get("local_unit_id")))


def _as_values(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _local_unit_source_ids(
    local_unit_ids: Sequence[str],
    local_units: Sequence[LocalTextUnit],
    known_source_ids: frozenset[str],
) -> tuple[str, ...]:
    units_by_id = {str(unit.unit_id): unit for unit in local_units}
    return _unique_strings(
        item.source_item_id
        for unit_id in local_unit_ids
        for item in units_by_id.get(str(unit_id), LocalTextUnit("", "", ())).items
        if item.source_item_id in known_source_ids
    )


def _unique_strings(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _target_models(records: OrderedDict[TargetIdentity, dict[str, Any]]) -> list[RepairTarget]:
    output = []
    for record in records.values():
        output.append(RepairTarget(
            finding_type=record["finding_type"], finding_id=record["finding_id"],
            sequence=record["sequence"],
            failure_codes=tuple(dict.fromkeys(record["failure_codes"])),
            classification=record["classification"],
            allowed_fields=tuple(dict.fromkeys(record["allowed_fields"])),
            source_allow_list=_unique_strings(record["source_allow_list"]),
            related_local_unit_ids=_unique_strings(record["related_local_unit_ids"]),
        ))
    return output


def _add_systemic_target(targets: list[RepairTarget], codes: Sequence[str]) -> list[RepairTarget]:
    if any(item.finding_id == "diagnostics" for item in targets):
        return targets
    targets.append(RepairTarget(
        finding_type="system", finding_id="diagnostics",
        failure_codes=tuple(dict.fromkeys(codes)), classification="systemic_corruption",
    ))
    return targets


def _build_coverage(
    diagnostics: Mapping[str, Any], key_shards: Sequence[str],
) -> tuple[CoverageAssessment, str | None]:
    raw = diagnostics.get("coverage_dispositions", diagnostics.get("coverage", ()))
    if isinstance(raw, Mapping):
        raw = [
            {"shard_id": shard_id, "disposition": disposition}
            for shard_id, disposition in raw.items()
        ]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        raw = list(raw)
    else:
        raw = []
    key_ids = {str(item) for item in key_shards}
    records: list[CoverageDisposition] = []
    error = None
    for raw_item in raw:
        if not isinstance(raw_item, Mapping):
            error = "invalid_coverage_disposition"
            continue
        values = dict(raw_item)
        shard_id = str(values.get("shard_id") or "")
        values["key_shard"] = bool(values.get("key_shard")) or shard_id in key_ids
        try:
            records.append(CoverageDisposition.model_validate(values))
        except ValueError:
            error = "invalid_coverage_disposition"
    uncovered = _as_values(diagnostics.get("uncovered_source_item_ids"))
    disposed_source_ids = {
        source_id
        for item in records
        for source_id in item.source_item_ids
        if item.disposition != "uninspected"
    }
    known = {item.shard_id for item in records}
    for source_id in uncovered:
        shard_id = str(source_id)
        if shard_id in known or shard_id in disposed_source_ids:
            continue
        records.append(CoverageDisposition(
            shard_id=shard_id, disposition="uninspected", key_shard=shard_id in key_ids,
            source_item_ids=(shard_id,), reason="Compiler reported this source as uncovered.",
        ))
    blocking = tuple(
        item.shard_id for item in records
        if item.key_shard and item.disposition == "uninspected"
    )
    return CoverageAssessment(
        dispositions=tuple(records), blocking_uninspected_shards=blocking,
        blocks_key_shard_gate=bool(blocking),
    ), error


def _packet(attempt: int, targets: Sequence[RepairTarget], coverage: CoverageAssessment) -> RepairPacket:
    if not isinstance(attempt, int) or not 0 <= attempt <= MAX_REPAIR_ATTEMPTS:
        raise ValueError("repair attempt must be between zero and two")
    systemic = any(item.classification == "systemic_corruption" for item in targets)
    repairable = [item for item in targets if item.classification == "repairable"]
    valid_source_allow_list = _unique_strings(
        source_id for item in targets for source_id in item.source_allow_list
    )
    return RepairPacket(
        attempt=attempt, remaining_attempts=max(0, MAX_REPAIR_ATTEMPTS - attempt),
        targets=tuple(targets),
        valid_source_allow_list=valid_source_allow_list,
        related_local_unit_ids=_unique_strings(
            unit_id for item in targets for unit_id in item.related_local_unit_ids
        ),
        coverage=coverage,
        model_call_allowed=bool(
            repairable
            and all(item.source_allow_list for item in repairable)
            and valid_source_allow_list
        )
        and not systemic and attempt < MAX_REPAIR_ATTEMPTS,
        systemic_corruption=systemic,
    )


def _systemic_packet(attempt: int, key_shards: Sequence[str], code: str) -> RepairPacket:
    coverage, _ = _build_coverage({}, key_shards)
    return _packet(attempt, [RepairTarget(
        finding_type="system", finding_id="diagnostics", failure_codes=(code,),
        classification="systemic_corruption",
    )], coverage)


def _first_value(*values: Any) -> str | None:
    return next((str(value) for value in values if value not in (None, "")), None)


__all__ = [
    "CoverageAssessment", "CoverageDisposition", "CoverageKind", "FailureClass",
    "RepairPacket", "RepairTarget", "build_repair_packet",
]
