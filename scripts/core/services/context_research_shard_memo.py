"""Typed child memos and deterministic shard ownership collection.

Child agents return bounded findings for deterministic shards. Core units own
findings; overlap is context only. This module reduces those typed findings
before the domain compiler, so Lead never repeats a full findings document.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scripts.core.services.context_research_compiler import (
    ArchiveNarrativeFinding,
    ContextResearchFindings,
    EventChainFinding,
    ReferenceAssetFinding,
    ResearchEntityFinding,
    UnresolvedFinding,
)
from scripts.core.services.context_research_ids import ShortIdRegistry


MemoDisposition = Literal[
    "modeled", "intentionally_unmodeled", "excluded_by_policy", "uninspected",
]
MemoOwnership = Literal["core", "overlap"]
ContentRole = Literal[
    "event_narrative", "background_narrative", "static_reference", "utility_or_noise",
]
DeliveryRoute = Literal["event", "reference", "none"]
AssessmentConfidence = Literal["low", "medium", "high"]
# Compatibility aliases for code that only imports the old type names. They are
# deliberately absent from the new model schema and prompt contract.
RouteCandidate = Literal[
    "event_chain", "archive_narrative", "reference_asset", "entity", "unresolved",
]
CandidateRoute = RouteCandidate
RouteStatus = Literal["decided", "uncertain", "unresolved", "not_applicable"]
RouteConfidence = AssessmentConfidence
FindingKind = Literal[
    "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
]
_KINDS: tuple[str, ...] = (
    "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
)
_SCALAR_FIELDS = {
    "archive_narratives": ("summary",),
    "entities": ("name", "entity_type", "summary", "importance"),
    "event_chains": ("event", "chain_id", "sequence"),
    "reference_assets": ("name", "description"),
    "unresolved": (
        "reference_type", "relation_source_id", "relation_target_id", "reason",
        "repair_attempts", "repair_detail",
    ),
}


class UnitContentFindings(BaseModel):
    """Unit-scoped semantic findings excluding the independent entity axis."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    archive_narratives: tuple[ArchiveNarrativeFinding, ...] = Field(default=(), max_length=100)
    event_chains: tuple[EventChainFinding, ...] = Field(default=(), max_length=100)
    reference_assets: tuple[ReferenceAssetFinding, ...] = Field(default=(), max_length=100)
    unresolved: tuple[UnresolvedFinding, ...] = Field(default=(), max_length=100)
    diagnostics: Mapping[str, Any] = Field(default_factory=dict)


class ShardUnitMemo(BaseModel):
    """Three-axis observation for one leased local unit.

    ``content_role`` describes the text, ``delivery_route`` governs translation
    context delivery, and ``entity_mentions`` remains independent of both.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    local_unit_id: str = Field(min_length=1, max_length=200)
    ownership: MemoOwnership
    disposition: MemoDisposition
    content_role: ContentRole
    delivery_route: DeliveryRoute
    findings: UnitContentFindings = Field(default_factory=UnitContentFindings)
    entity_mentions: tuple[ResearchEntityFinding, ...] = Field(default=(), max_length=100)
    confidence: AssessmentConfidence | None = None
    notes: str | None = Field(default=None, max_length=2_000)
    evidence: tuple[str, ...] = Field(default=(), max_length=100)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_route_shape(cls, value: Any) -> Any:
        """Read old persisted memos without advertising the obsolete route API."""

        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        findings = dict(payload.get("findings") or {})
        legacy_entities = findings.pop("entities", ())
        if "entity_mentions" not in payload:
            payload["entity_mentions"] = legacy_entities
        payload["findings"] = findings
        if "content_role" not in payload or "delivery_route" not in payload:
            content_role, delivery_route = _legacy_axes(payload, findings)
            payload.setdefault("content_role", content_role)
            payload.setdefault("delivery_route", delivery_route)
        for field in ("candidate_routes", "preferred_route", "route_status"):
            payload.pop(field, None)
        return payload


class ShardMemo(BaseModel):
    """A child result for exact shards with coverage, not final route resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    role: str = Field(min_length=1, max_length=80)
    shard_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    core_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)
    overlap_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)
    units: tuple[ShardUnitMemo, ...] = Field(default=(), max_length=500)

    def __str__(self) -> str:
        """Give the Harness parent a compact audit view, not Python repr text."""

        return self.model_dump_json()

    @model_validator(mode="after")
    def _validate_membership(self) -> "ShardMemo":
        for values, label in (
            (self.shard_ids, "memo shard_ids"),
            (self.core_local_unit_ids, "memo core_local_unit_ids"),
            (self.overlap_local_unit_ids, "memo overlap_local_unit_ids"),
        ):
            _unique(values, label)
        if set(self.core_local_unit_ids) & set(self.overlap_local_unit_ids):
            raise ValueError("a local unit cannot be both core and overlap in one memo")
        core_reports: defaultdict[str, int] = defaultdict(int)
        for unit in self.units:
            if unit.ownership == "core" and unit.local_unit_id in self.core_local_unit_ids:
                core_reports[unit.local_unit_id] += 1
        missing_reports = set(self.core_local_unit_ids) - set(core_reports)
        duplicate_reports = {
            unit_id for unit_id, count in core_reports.items() if count != 1
        }
        if missing_reports or duplicate_reports:
            invalid = sorted(missing_reports | duplicate_reports)
            raise ValueError(
                "memo must contain exactly one core unit report for each delegated "
                f"core unit: {invalid!r}"
            )
        return self


class ShardManifestEntry(BaseModel):
    """The deterministic ownership portion of one corpus shard manifest."""

    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    shard_id: str = Field(min_length=1, max_length=200)
    core_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)
    overlap_local_unit_ids: tuple[str, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def _unique_units(self) -> "ShardManifestEntry":
        _unique(self.core_local_unit_ids, "manifest core_local_unit_ids")
        _unique(self.overlap_local_unit_ids, "manifest overlap_local_unit_ids")
        if set(self.core_local_unit_ids) & set(self.overlap_local_unit_ids):
            raise ValueError("manifest unit cannot be both core and overlap")
        return self


class CollectedShardUnit(BaseModel):
    """One core-owned unit after typed finding and overlap reduction."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    local_unit_id: str
    owner_shard_id: str
    owner_role: str
    disposition: MemoDisposition
    findings: ContextResearchFindings
    content_role: ContentRole
    delivery_route: DeliveryRoute
    confidence: AssessmentConfidence | None = None
    notes: str | None = None
    evidence: tuple[str, ...] = ()
    overlap_observed_in: tuple[str, ...] = ()


class ShardMemoCollection(BaseModel):
    """Stable intermediate input for domain reducers and the final compiler."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: ContextResearchFindings = Field(default_factory=ContextResearchFindings)
    units: tuple[CollectedShardUnit, ...] = ()
    missing_core_local_unit_ids: tuple[str, ...] = ()
    missing_shard_ids: tuple[str, ...] = ()
    duplicate_core_local_unit_ids: tuple[str, ...] = ()
    conflict_local_unit_ids: tuple[str, ...] = ()
    conflicting_finding_ids: tuple[str, ...] = ()
    evidence_conflicts: tuple[str, ...] = ()
    unknown_shard_ids: tuple[str, ...] = ()
    invalid_unit_ownership: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        """Whether coverage and manifest ownership are safe to publish.

        Finding-level disagreements are deliberately diagnostics only.  The
        intermediate memo is allowed to preserve competing observations and
        evidence wording; only missing/duplicate core coverage and
        manifest/ownership violations block collection completeness.
        """

        return not any((
            self.missing_core_local_unit_ids, self.duplicate_core_local_unit_ids,
            self.conflict_local_unit_ids, self.invalid_unit_ownership,
            self.unknown_shard_ids,
        ))


class ShardMemoCollector:
    """Collect core-owned typed findings and deterministically merge overlap."""

    def __init__(
        self,
        manifest: Sequence[ShardManifestEntry | Mapping[str, Any]],
        id_registry: ShortIdRegistry | None = None,
    ) -> None:
        self._manifest = tuple(_coerce_manifest(item) for item in manifest)
        self._id_registry = id_registry
        self._memos: list[ShardMemo] = []
        self._id_rejections: list[dict[str, Any]] = []

    def add(self, memo: ShardMemo | Mapping[str, Any]) -> None:
        """Add one memo; final output does not depend on arrival order."""

        payload = memo.model_dump(mode="python") if isinstance(memo, ShardMemo) else dict(memo)
        if self._id_registry is not None:
            payload, rejections = self._id_registry.normalize_memo_payload(payload)
            self._id_rejections.extend(item.as_dict() for item in rejections)
        self._id_rejections.extend(_sanitize_claims(payload, self._manifest))
        self._memos.append(ShardMemo.model_validate(payload))

    def collect(self) -> ShardMemoCollection:
        """Return aggregate typed findings and ownership diagnostics."""

        manifest = {item.shard_id: item for item in self._manifest}
        expected = _manifest_core_owners(self._manifest)
        memos = sorted(self._memos, key=_memo_sort_key)
        core, overlap, unknown, invalid = self._index_reports(memos, manifest)
        duplicate = {key for key, reports in core.items() if len(reports) > 1}
        missing = set(expected) - set(core)
        missing_shards = _missing_shard_ids(self._manifest, missing)
        conflicts = {key for key, owners in expected.items() if len(owners) > 1}
        units: list[CollectedShardUnit] = []
        finding_conflicts: set[str] = set()
        evidence_conflicts: set[str] = set()
        aggregate = ContextResearchFindings()
        for unit_id in sorted(set(expected) & set(core)):
            reports = core[unit_id]
            owner_memo, owner = reports[0]
            overlap_reports = overlap.get(unit_id, ())
            unit_findings = _merge_findings(reports, finding_conflicts, evidence_conflicts)
            unit_findings = _merge_overlap(
                unit_findings, overlap_reports, finding_conflicts, evidence_conflicts,
            )
            if len({item.disposition for _, item in reports}) > 1:
                conflicts.add(unit_id)
            aggregate = _merge_context_findings(
                (aggregate, unit_findings), finding_conflicts, evidence_conflicts,
            )
            units.append(CollectedShardUnit(
                local_unit_id=unit_id,
                owner_shard_id=expected[unit_id][0],
                owner_role=owner_memo.role,
                disposition=owner.disposition,
                findings=unit_findings,
                content_role=owner.content_role,
                delivery_route=owner.delivery_route,
                confidence=owner.confidence,
                notes=owner.notes,
                evidence=tuple(dict.fromkeys(owner.evidence)),
                overlap_observed_in=tuple(sorted({memo.role for memo, _ in overlap_reports})),
            ))
        if self._id_rejections:
            diagnostics = dict(aggregate.diagnostics or {})
            diagnostics["id_rejections"] = list(self._id_rejections)
            aggregate = aggregate.model_copy(update={"diagnostics": diagnostics})
        return ShardMemoCollection(
            findings=aggregate,
            units=tuple(units),
            missing_core_local_unit_ids=tuple(sorted(missing)),
            missing_shard_ids=tuple(sorted(missing_shards)),
            duplicate_core_local_unit_ids=tuple(sorted(duplicate)),
            conflict_local_unit_ids=tuple(sorted(conflicts | invalid)),
            conflicting_finding_ids=tuple(sorted(finding_conflicts)),
            evidence_conflicts=tuple(sorted(evidence_conflicts)),
            unknown_shard_ids=tuple(sorted(unknown)),
            invalid_unit_ownership=tuple(sorted(invalid)),
        )

    def _index_reports(self, memos, manifest):
        core: defaultdict[str, list[tuple[ShardMemo, ShardUnitMemo]]] = defaultdict(list)
        overlap: defaultdict[str, list[tuple[ShardMemo, ShardUnitMemo]]] = defaultdict(list)
        unknown: set[str] = set()
        invalid: set[str] = set()
        for memo in memos:
            unknown.update(shard for shard in memo.shard_ids if shard not in manifest)
            for unit in memo.units:
                if not _unit_allowed(unit, memo, manifest):
                    invalid.add(unit.local_unit_id)
                    continue
                (core if unit.ownership == "core" else overlap)[unit.local_unit_id].append((memo, unit))
        return core, overlap, unknown, invalid


def _merge_findings(reports, conflicts, evidence_conflicts):
    return _merge_context_findings(
        tuple(
            _unit_context_findings(unit)
            for _, unit in reports
            if unit.disposition == "modeled"
        ),
        conflicts,
        evidence_conflicts,
    )


def _merge_context_findings(findings, conflicts, evidence_conflicts):
    values: dict[str, list[Any]] = {kind: [] for kind in _KINDS}
    diagnostics: dict[str, Any] = {}
    for item in findings:
        for kind in _KINDS:
            values[kind].extend(getattr(item, kind))
        diagnostics = _merge_diagnostics(
            diagnostics, dict(item.diagnostics or {}), conflicts,
        )
    return ContextResearchFindings.model_validate({
        **{
            kind: _merge_kind(kind, values[kind], conflicts, evidence_conflicts)
            for kind in _KINDS
        },
        "diagnostics": diagnostics,
    })


def _merge_diagnostics(first, second, conflicts, prefix="diagnostics"):
    merged = dict(first)
    for key, value in second.items():
        label = f"{prefix}.{key}"
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_diagnostics(merged[key], value, conflicts, label)
        elif isinstance(merged[key], (list, tuple)) and isinstance(value, (list, tuple)):
            combined = (*merged[key], *value)
            unique: dict[str, Any] = {}
            for item in combined:
                marker = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
                unique.setdefault(marker, item)
            merged[key] = list(unique.values())
        elif merged[key] != value:
            conflicts.add(label)
    return merged


def _merge_overlap(base, reports, conflicts, evidence_conflicts):
    """Enrich core findings only; overlap cannot introduce a new finding."""

    if not reports:
        return base
    values = {kind: list(getattr(base, kind)) for kind in _KINDS}
    identities = {kind: {_finding_identity(kind, item) for item in items} for kind, items in values.items()}
    for _, unit in reports:
        if unit.disposition != "modeled":
            continue
        findings = _unit_context_findings(unit)
        for kind in _KINDS:
            values[kind].extend(
                item for item in getattr(findings, kind)
                if _finding_identity(kind, item) in identities[kind]
            )
    return ContextResearchFindings.model_validate({
        kind: _merge_kind(kind, values[kind], conflicts, evidence_conflicts)
        for kind in _KINDS
    })


def _merge_kind(kind, items, conflicts, evidence_conflicts):
    merged: dict[tuple[Any, ...], Any] = {}
    for item in items:
        identity = _finding_identity(kind, item)
        previous = merged.get(identity)
        merged[identity] = (
            item if previous is None
            else _merge_item(kind, previous, item, conflicts, evidence_conflicts)
        )
    return tuple(merged[key] for key in sorted(merged))


def _merge_item(kind, first, second, conflicts, evidence_conflicts):
    updates = {"evidence": _merge_evidence(first, second, evidence_conflicts)}
    if kind == "event_chains":
        updates.update({
            "local_unit_ids": _union(first.local_unit_ids, second.local_unit_ids),
            "archive_context_ids": _union(first.archive_context_ids, second.archive_context_ids),
            "entity_ids": _union(first.entity_ids, second.entity_ids),
        })
    elif kind == "entities":
        updates["aliases"] = _union(first.aliases, second.aliases)
    elif kind == "reference_assets" and first.local_unit_id != second.local_unit_id:
        conflicts.add(_finding_label(kind, first))
    for field in _SCALAR_FIELDS[kind]:
        if getattr(first, field) != getattr(second, field):
            conflicts.add(_finding_label(kind, first))
    return first.model_copy(update=updates)


def _merge_evidence(first, second, conflicts):
    records: dict[tuple[str, ...], Any] = {}
    for item in (*first.evidence, *second.evidence):
        key = tuple(item.source_item_ids)
        previous = records.get(key)
        if previous is not None and previous.snippet != item.snippet:
            conflicts.add("evidence:" + ",".join(key))
            continue
        records.setdefault(key, item)
    return tuple(records[key] for key in sorted(records))


def _finding_identity(kind, item):
    if kind == "event_chains":
        return item.chain_id, item.sequence
    field = {
        "archive_narratives": "narrative_id", "entities": "entity_id",
        "reference_assets": "asset_id", "unresolved": "unresolved_id",
    }[kind]
    return (getattr(item, field),)


def _findings_empty(findings: ContextResearchFindings) -> bool:
    return not any(getattr(findings, kind) for kind in _KINDS)


def _unit_context_findings(unit: ShardUnitMemo) -> ContextResearchFindings:
    return ContextResearchFindings(
        archive_narratives=unit.findings.archive_narratives,
        entities=unit.entity_mentions,
        event_chains=unit.findings.event_chains,
        reference_assets=unit.findings.reference_assets,
        unresolved=unit.findings.unresolved,
        diagnostics=unit.findings.diagnostics,
    )


def _legacy_axes(
    payload: Mapping[str, Any], findings: Mapping[str, Any],
) -> tuple[ContentRole, DeliveryRoute]:
    """Conservatively project the old mixed route contract into three axes."""

    routes = tuple(dict.fromkeys(str(item) for item in payload.get("candidate_routes", ())))
    preferred = str(payload.get("preferred_route") or "")
    has_event = bool(findings.get("event_chains")) or "event_chain" in routes
    has_background = bool(findings.get("archive_narratives")) or "archive_narrative" in routes
    has_reference = bool(findings.get("reference_assets")) or "reference_asset" in routes
    if has_event:
        content_role: ContentRole = "event_narrative"
    elif has_background:
        content_role = "background_narrative"
    elif has_reference:
        content_role = "static_reference"
    else:
        content_role = "utility_or_noise"
    if preferred == "event_chain":
        return content_role, "event"
    if preferred == "reference_asset":
        return content_role, "reference"
    delivery_candidates = {item for item in routes if item in {"event_chain", "reference_asset"}}
    if delivery_candidates == {"event_chain"}:
        return content_role, "event"
    if delivery_candidates == {"reference_asset"}:
        return content_role, "reference"
    if not delivery_candidates and has_event != has_reference:
        return content_role, "event" if has_event else "reference"
    return content_role, "none"


def _finding_label(kind, item):
    return f"{kind}:{':'.join(str(value) for value in _finding_identity(kind, item))}"


def _union(first, second):
    return tuple(dict.fromkeys((*first, *second)))


def _coerce_manifest(value):
    return value if isinstance(value, ShardManifestEntry) else ShardManifestEntry.model_validate(value)


def _manifest_core_owners(manifest):
    owners: defaultdict[str, list[str]] = defaultdict(list)
    for shard in manifest:
        for unit_id in shard.core_local_unit_ids:
            owners[unit_id].append(shard.shard_id)
    return {unit_id: tuple(sorted(shards)) for unit_id, shards in owners.items()}


def _missing_shard_ids(
    manifest: Sequence[ShardManifestEntry],
    missing_core_local_unit_ids: set[str],
) -> set[str]:
    """Map missing core coverage back to deterministic manifest shard IDs."""

    return {
        shard.shard_id
        for shard in manifest
        if set(shard.core_local_unit_ids) & missing_core_local_unit_ids
    }


def _memo_sort_key(memo):
    return memo.role.casefold(), tuple(sorted(memo.shard_ids)), memo.model_dump_json()


def _unit_allowed(unit, memo, manifest):
    allowed: set[str] = set()
    for shard_id in memo.shard_ids:
        shard = manifest.get(shard_id)
        if shard is None:
            continue
        allowed.update(
            shard.core_local_unit_ids if unit.ownership == "core"
            else shard.overlap_local_unit_ids
        )
    return unit.local_unit_id in allowed


def _unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _sanitize_claims(
    payload: dict[str, Any], manifest: Sequence[ShardManifestEntry],
) -> list[dict[str, Any]]:
    """Drop nested event/asset claims outside the memo's owned core units.

    A child may read overlap or external context, and may cite it as evidence,
    but only the leased core units can be asserted as a local-unit claim.
    """

    manifest_by_id = {item.shard_id: item for item in manifest}
    owned = {
        unit_id
        for shard_id in payload.get("shard_ids", ())
        for unit_id in manifest_by_id.get(str(shard_id), ShardManifestEntry(shard_id="_none")).core_local_unit_ids
    }
    rejected: list[dict[str, Any]] = []
    units = payload.get("units", ())
    for unit in units if isinstance(units, (list, tuple)) else ():
        if not isinstance(unit, dict):
            continue
        findings = unit.get("findings")
        if not isinstance(findings, dict):
            continue
        for finding in findings.get("event_chains", ()) if isinstance(findings.get("event_chains"), (list, tuple)) else ():
            if not isinstance(finding, dict):
                continue
            values = finding.get("local_unit_ids", ())
            retained = [value for value in values if value in owned] if isinstance(values, (list, tuple)) else []
            for value in values if isinstance(values, (list, tuple)) else ():
                if value not in retained:
                    rejected.append({
                        "kind": "unit_claim", "field": "event_chains.local_unit_ids",
                        "value": str(value), "code": "claim_outside_lease",
                        "message": "event claims may reference leased core units only",
                    })
            finding["local_unit_ids"] = retained
        for finding in findings.get("reference_assets", ()) if isinstance(findings.get("reference_assets"), (list, tuple)) else ():
            if not isinstance(finding, dict):
                continue
            value = finding.get("local_unit_id")
            if value is not None and value not in owned:
                rejected.append({
                    "kind": "unit_claim", "field": "reference_assets.local_unit_id",
                    "value": str(value), "code": "claim_outside_lease",
                    "message": "asset claims may reference leased core units only",
                })
                finding["local_unit_id"] = None
    return rejected


__all__ = [
    "AssessmentConfidence", "CandidateRoute", "CollectedShardUnit", "ContentRole",
    "DeliveryRoute", "FindingKind", "MemoDisposition", "MemoOwnership", "RouteCandidate",
    "RouteConfidence", "RouteStatus", "UnitContentFindings",
    "ShardManifestEntry", "ShardMemo", "ShardMemoCollection", "ShardMemoCollector",
    "ShardUnitMemo",
]
