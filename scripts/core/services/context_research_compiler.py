"""Compile permissive Agent findings into the strict Remis research contract.

The model-facing schema intentionally carries source evidence only once.  The
compiler owns derived indexes, request allow-list enforcement, cross-reference
cleanup, and final DTO validation.  It never invents evidence or repairs prose.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from scripts.core.services.context_research_contract import (
    ArchiveNarrative,
    ContextAnalysisRequest,
    ContextResearchDraft,
    EvidenceReference,
    EventChain,
    EntityImportance,
    EntityKind,
    ReferenceAsset,
    ResearchEntity,
    Unresolved,
    UnresolvedKind,
)
from scripts.core.services.context_research_ids import ShortIdRegistry
from scripts.core.services.context_research_chain_consolidation import (
    consolidate_event_steps,
)
from scripts.core.services.context_research_entity_grading import calculate_entity_frequency
from scripts.core.services.context_research_entity_normalization import (
    normalize_compiled_entities,
)
from scripts.core.services.context_research_universal_context import (
    build_universal_translation_context,
)


class FindingEvidence(BaseModel):
    """One model-proposed evidence reference, before request-bound validation."""

    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    source_item_ids: tuple[str, ...] = Field(default=(), max_length=50)
    snippet: str | None = Field(default=None, max_length=2_000)


class _Finding(BaseModel):
    """Shared permissive model boundary for one semantic finding."""

    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    evidence: tuple[FindingEvidence, ...] = Field(default=(), max_length=50)


class ArchiveNarrativeFinding(_Finding):
    narrative_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_200)


class ResearchEntityFinding(_Finding):
    entity_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    entity_type: EntityKind
    summary: str = Field(min_length=1, max_length=1_000)
    aliases: tuple[str, ...] = Field(default=(), max_length=20)
    importance: EntityImportance = Field(
        default="supporting",
        description="Plot importance only; Remis calculates the A/B/C frequency grade.",
    )


class EventChainFinding(_Finding):
    chain_id: str = Field(min_length=1, max_length=200)
    event: str = Field(min_length=1, max_length=1_000)
    sequence: int = Field(default=0, ge=0)
    local_unit_ids: tuple[str, ...] = Field(default=(), max_length=20)
    archive_context_ids: tuple[str, ...] = Field(default=(), max_length=80)
    entity_ids: tuple[str, ...] = Field(default=(), max_length=80)


class ReferenceAssetFinding(_Finding):
    asset_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1_000)
    local_unit_id: str | None = Field(default=None, max_length=200)


class UnresolvedFinding(_Finding):
    unresolved_id: str = Field(min_length=1, max_length=200)
    reference_type: UnresolvedKind
    relation_source_id: str = Field(
        min_length=1,
        max_length=200,
        validation_alias=AliasChoices("relation_source_id", "source_id"),
    )
    relation_target_id: str = Field(
        min_length=1,
        max_length=200,
        validation_alias=AliasChoices("relation_target_id", "target_id"),
    )
    reason: str = Field(min_length=1, max_length=500)
    repair_attempts: int = Field(default=0, ge=0, le=1)
    repair_detail: str | None = Field(default=None, max_length=500)


class ContextResearchFindings(BaseModel):
    """Model-facing semantic result with no derived source-ID indexes."""

    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    archive_narratives: tuple[ArchiveNarrativeFinding, ...] = Field(default=(), max_length=500)
    entities: tuple[ResearchEntityFinding, ...] = Field(default=(), max_length=500)
    event_chains: tuple[EventChainFinding, ...] = Field(default=(), max_length=500)
    reference_assets: tuple[ReferenceAssetFinding, ...] = Field(default=(), max_length=500)
    unresolved: tuple[UnresolvedFinding, ...] = Field(default=(), max_length=500)
    universal_translation_context: str = Field(default="", max_length=600)
    diagnostics: Mapping[str, Any] = Field(default_factory=dict)


class ContextResearchDraftCompiler:
    """Deterministically narrow Agent findings into a request-grounded draft."""

    schema_version = "context-research-compiler-v2"

    def compile(
        self,
        findings: ContextResearchFindings | Mapping[str, Any],
        request: ContextAnalysisRequest,
        *,
        id_registry: ShortIdRegistry | None = None,
    ) -> ContextResearchDraft:
        candidate = (
            findings
            if isinstance(findings, ContextResearchFindings)
            else ContextResearchFindings.model_validate(findings)
        )
        id_rejections = ()
        if id_registry is not None:
            payload, id_rejections = id_registry.normalize_findings_payload(
                candidate.model_dump(mode="python"),
            )
            candidate = ContextResearchFindings.model_validate(payload)
        known = request.known_source_item_ids
        source_metadata = {item.source_item_id: item for item in request.source_items}
        local_units = {unit.unit_id: unit for unit in request.local_units}
        diagnostics = self._new_diagnostics(candidate.diagnostics)
        reducer_diagnostics = candidate.diagnostics.get("reducer", {})
        if isinstance(reducer_diagnostics, Mapping):
            diagnostics["compiler"]["merge_evidence_rejections"] = list(
                reducer_diagnostics.get("merge_evidence_rejections", []) or []
            )
            diagnostics["compiler"]["merge_evidence_acceptances"] = list(
                reducer_diagnostics.get("merge_evidence_acceptances", []) or []
            )
        if id_rejections:
            diagnostics["compiler"]["id_rejections"] = [
                item.as_dict() for item in id_rejections
            ]

        narratives = self._compile_narratives(
            candidate.archive_narratives, known, source_metadata, diagnostics,
        )
        narrative_ids = {item.narrative_id for item in narratives}
        entities = self._compile_entities(
            candidate.entities, known, source_metadata, local_units, diagnostics,
        )
        entity_ids = {item.entity_id for item in entities}
        rejected_dynamic_entity_ids = {
            item["entity_id"]
            for item in diagnostics["compiler"]["rejected_dynamic_entity_candidates"]
        } - entity_ids
        events, generated_unresolved = self._compile_events(
            candidate.event_chains, narrative_ids, entity_ids, known, source_metadata,
            local_units, rejected_dynamic_entity_ids, diagnostics,
        )
        events, chain_diagnostics = consolidate_event_steps(events, local_units)
        entities, events, entity_diagnostics = normalize_compiled_entities(
            entities, events, local_units,
        )
        diagnostics["compiler"]["chain_consolidation"] = chain_diagnostics
        diagnostics["compiler"]["entity_normalization"] = entity_diagnostics
        entities = self._attach_event_participation(entities, events)
        assets = self._compile_assets(
            candidate.reference_assets, known, source_metadata, local_units, diagnostics,
        )
        unresolved = self._compile_unresolved(
            candidate.unresolved, known, source_metadata, events, diagnostics,
        )
        unresolved = self._deduplicate_unresolved(
            (*unresolved, *generated_unresolved), diagnostics,
        )
        universal_context = build_universal_translation_context(
            request,
            events,
            narratives,
            entities,
            proposed_text=candidate.universal_translation_context,
        )
        diagnostics["compiler"]["universal_translation_context"] = {
            "generation": universal_context.generation,
            "source_item_ids": list(universal_context.source_item_ids),
            "external_source_kinds": list(universal_context.external_source_kinds),
            "character_count": len(universal_context.text),
        }
        items = (*narratives, *entities, *events, *assets, *unresolved)
        source_item_ids = _ordered_unique(
            (
                source_id
                for item in items
                for source_id in item.source_item_ids
            )
        )
        source_item_ids = _ordered_unique(
            (
                *source_item_ids,
                *universal_context.source_item_ids,
            )
        )
        request_source_ids = request.source_item_ids or tuple(
            item.source_item_id for item in request.source_items
        )
        diagnostics["compiler"]["uncovered_source_item_ids"] = [
            source_id for source_id in request_source_ids if source_id not in source_item_ids
        ]
        diagnostics["compiler"]["published_counts"] = {
            "archive_narratives": len(narratives),
            "entities": len(entities),
            "event_chains": len(events),
            "reference_assets": len(assets),
            "unresolved": len(unresolved),
            "source_item_ids": len(source_item_ids),
        }
        draft = ContextResearchDraft(
            source_item_ids=source_item_ids,
            archive_narratives=narratives,
            entities=entities,
            event_chains=events,
            reference_assets=assets,
            unresolved=unresolved,
            universal_translation_context=universal_context,
            diagnostics=diagnostics,
        )
        return draft.validate_against(request)

    def _compile_narratives(self, findings, known, metadata, diagnostics):
        output = []
        seen = set()
        for item in findings:
            if not self._accept_identity("archive_narrative", item.narrative_id, seen, diagnostics):
                continue
            evidence, source_ids = self._compile_evidence(
                "archive_narrative", item.narrative_id, item.evidence,
                known, metadata, diagnostics,
            )
            if not source_ids:
                self._drop_ungrounded("archive_narrative", item.narrative_id, diagnostics)
                continue
            output.append(ArchiveNarrative(
                narrative_id=item.narrative_id,
                summary=item.summary,
                source_item_ids=source_ids,
                evidence=evidence,
                delivery_target=False,
            ))
        return tuple(output)

    def _compile_entities(self, findings, known, metadata, local_units, diagnostics):
        output = []
        seen = set()
        allowed_types = {
            "person", "place", "organization", "polity", "technology", "concept", "item", "other",
        }
        allowed_importance = {"primary", "supporting", "background"}
        for item in findings:
            if any(_is_dynamic_entity_name(value) for value in (item.name, *item.aliases)):
                diagnostics["compiler"]["rejected_dynamic_entity_candidates"].append({
                    "entity_id": item.entity_id,
                    "name": item.name,
                })
                continue
            if not self._accept_identity("entity", item.entity_id, seen, diagnostics):
                continue
            evidence, source_ids = self._compile_entity_evidence(
                item, known, metadata, local_units, diagnostics,
            )
            if not source_ids:
                self._drop_ungrounded("entity", item.entity_id, diagnostics)
                continue
            frequency = calculate_entity_frequency(item.name, item.aliases, local_units)
            output.append(ResearchEntity(
                entity_id=item.entity_id,
                name=item.name,
                entity_type=item.entity_type if item.entity_type in allowed_types else "other",
                summary=item.summary,
                aliases=_ordered_unique(item.aliases),
                importance=(
                    item.importance if item.importance in allowed_importance else "supporting"
                ),
                mention_count=frequency.mention_count,
                local_unit_ids=frequency.local_unit_ids,
                local_unit_coverage=frequency.local_unit_coverage,
                source_files=frequency.source_files,
                file_spread=frequency.file_spread,
                frequency_grade=frequency.frequency_grade,
                source_item_ids=source_ids,
                evidence=evidence,
            ))
        return tuple(output)

    @staticmethod
    def _attach_event_participation(entities, events):
        chains_by_entity: dict[str, list[str]] = {}
        for event in events:
            for entity_id in event.entity_ids:
                values = chains_by_entity.setdefault(entity_id, [])
                if event.chain_id not in values:
                    values.append(event.chain_id)
        return tuple(
            entity.model_copy(update={
                "event_chain_ids": tuple(chains_by_entity.get(entity.entity_id, ())),
                "event_participation_count": len(
                    chains_by_entity.get(entity.entity_id, ())
                ),
            })
            for entity in entities
        )

    def _compile_entity_evidence(self, item, known, metadata, local_units, diagnostics):
        surfaces = tuple(
            surface for surface in (
                _normalize_entity_surface(item.name),
                *(_normalize_entity_surface(alias) for alias in item.aliases),
            )
            if surface
        )
        unit_by_source = {
            source.source_item_id: unit
            for unit in local_units.values()
            for source in unit.items
        }
        output = []
        source_ids = []
        expanded_unit_ids = set()
        for reference_index, reference in enumerate(item.evidence):
            accepted = []
            for source_id in _ordered_unique(reference.source_item_ids):
                if source_id not in known:
                    diagnostics["compiler"]["rejected_source_item_ids"].append({
                        "finding_type": "entity",
                        "finding_id": item.entity_id,
                        "evidence_index": reference_index,
                        "source_item_id": source_id,
                    })
                    continue
                source = metadata.get(source_id)
                unit = unit_by_source.get(source_id)
                direct_match = _entity_surface_matches(source, surfaces)
                sibling_match = bool(unit) and any(
                    sibling.source_item_id != source_id
                    and _entity_surface_matches(sibling, surfaces)
                    for sibling in unit.items
                )
                if not direct_match and not sibling_match:
                    diagnostics["compiler"]["rejected_entity_evidence_ids"].append({
                        "entity_id": item.entity_id,
                        "source_item_id": source_id,
                    })
                    continue
                accepted.append(source_id)
                source_ids.append(source_id)
                if sibling_match and unit is not None:
                    expanded_unit_ids.add(unit.unit_id)
            if not accepted:
                continue
            relative_path, item_key = self._canonical_location(accepted, metadata)
            output.append(EvidenceReference(
                source_item_ids=tuple(accepted),
                snippet=reference.snippet,
                relative_path=relative_path,
                item_key=item_key,
            ))
        expanded_source_ids = _ordered_unique(
            source.source_item_id
            for unit_id in expanded_unit_ids
            for source in local_units[unit_id].items
        )
        return tuple(output), _ordered_unique((*source_ids, *expanded_source_ids))

    def _compile_events(
        self, findings, narrative_ids, entity_ids, known, metadata, local_units,
        rejected_dynamic_entity_ids, diagnostics,
    ):
        output = []
        generated_unresolved = []
        seen = set()
        for item in findings:
            identity = (item.chain_id, item.sequence)
            if not self._accept_identity("event_chain", identity, seen, diagnostics):
                continue
            evidence, source_ids = self._compile_evidence(
                "event_chain", item.chain_id, item.evidence,
                known, metadata, diagnostics,
            )
            explicit_unit_ids = tuple(
                unit_id for unit_id in _ordered_unique(item.local_unit_ids)
                if unit_id in local_units
            )
            rejected_unit_ids = tuple(
                unit_id for unit_id in _ordered_unique(item.local_unit_ids)
                if unit_id not in local_units
            )
            for unit_id in rejected_unit_ids:
                diagnostics["compiler"]["rejected_local_unit_ids"].append({
                    "chain_id": item.chain_id,
                    "sequence": item.sequence,
                    "local_unit_id": unit_id,
                })
            evidence_source_ids = set(source_ids)
            inferred_unit_ids = () if explicit_unit_ids else tuple(
                unit_id for unit_id, unit in local_units.items()
                if unit.items
                and {source.source_item_id for source in unit.items} <= evidence_source_ids
            )
            for unit_id in inferred_unit_ids:
                diagnostics["compiler"]["inferred_local_unit_ids"].append({
                    "chain_id": item.chain_id,
                    "sequence": item.sequence,
                    "local_unit_id": unit_id,
                })
            accepted_unit_ids = _ordered_unique((*explicit_unit_ids, *inferred_unit_ids))
            member_source_ids = _ordered_unique(
                source.source_item_id
                for unit_id in accepted_unit_ids
                for source in local_units[unit_id].items
            )
            if member_source_ids:
                source_ids = _ordered_unique((*member_source_ids, *source_ids))
            if not source_ids:
                self._drop_ungrounded("event_chain", item.chain_id, diagnostics)
                continue
            archive_ids = []
            for archive_id in _ordered_unique(item.archive_context_ids):
                if archive_id in narrative_ids:
                    archive_ids.append(archive_id)
                    continue
                diagnostics["compiler"]["unknown_archive_context_links"].append({
                    "chain_id": item.chain_id,
                    "sequence": item.sequence,
                    "archive_context_id": archive_id,
                })
                generated_unresolved.append(Unresolved(
                    unresolved_id=_link_unresolved_id(item.chain_id, archive_id),
                    reference_type="story",
                    source_id=item.chain_id,
                    target_id=archive_id,
                    reason="Event referenced an archive context that was not publishable.",
                    repair_attempts=0,
                    source_item_ids=source_ids,
                    evidence=evidence,
                ))
            accepted_entity_ids = []
            for entity_id in _ordered_unique(item.entity_ids):
                if entity_id in entity_ids:
                    accepted_entity_ids.append(entity_id)
                    continue
                if entity_id in rejected_dynamic_entity_ids:
                    diagnostics["compiler"]["dropped_dynamic_entity_links"].append({
                        "chain_id": item.chain_id,
                        "sequence": item.sequence,
                        "entity_id": entity_id,
                    })
                    continue
                diagnostics["compiler"]["unknown_entity_links"].append({
                    "chain_id": item.chain_id,
                    "sequence": item.sequence,
                    "entity_id": entity_id,
                })
                generated_unresolved.append(Unresolved(
                    unresolved_id=_entity_link_unresolved_id(item.chain_id, entity_id),
                    reference_type="fragment_edge",
                    source_id=item.chain_id,
                    target_id=entity_id,
                    reason="Event referenced an entity that was not publishable.",
                    repair_attempts=0,
                    source_item_ids=source_ids,
                    evidence=evidence,
                ))
            output.append(EventChain(
                chain_id=item.chain_id,
                event=item.event,
                sequence=item.sequence,
                local_unit_ids=accepted_unit_ids,
                archive_context_ids=tuple(archive_ids),
                entity_ids=tuple(accepted_entity_ids),
                source_item_ids=source_ids,
                evidence=evidence,
            ))
        return tuple(output), tuple(generated_unresolved)

    def _compile_assets(self, findings, known, metadata, local_units, diagnostics):
        output = []
        seen = set()
        for item in findings:
            if not self._accept_identity("reference_asset", item.asset_id, seen, diagnostics):
                continue
            evidence, source_ids = self._compile_evidence(
                "reference_asset", item.asset_id, item.evidence,
                known, metadata, diagnostics,
            )
            if not source_ids:
                self._drop_ungrounded("reference_asset", item.asset_id, diagnostics)
                continue
            local_unit_id = item.local_unit_id
            if local_unit_id is not None and local_unit_id not in local_units:
                diagnostics["compiler"]["rejected_asset_local_unit_ids"].append({
                    "asset_id": item.asset_id,
                    "local_unit_id": local_unit_id,
                })
                local_unit_id = None
            output.append(ReferenceAsset(
                asset_id=item.asset_id,
                name=item.name,
                description=item.description,
                local_unit_id=local_unit_id,
                receives_event_context=False,
                source_item_ids=source_ids,
                evidence=evidence,
            ))
        return tuple(output)

    def _compile_unresolved(self, findings, known, metadata, events, diagnostics):
        output = []
        for item in findings:
            raw_source_ids = _ordered_unique(
                source_id
                for reference in item.evidence
                for source_id in reference.source_item_ids
            )
            evidence, source_ids = self._compile_evidence(
                "unresolved", item.unresolved_id, item.evidence,
                known, metadata, diagnostics,
            )
            if not source_ids:
                self._drop_ungrounded("unresolved", item.unresolved_id, diagnostics)
                continue
            if (
                item.reference_type == "unit_route"
                and raw_source_ids
                and set(raw_source_ids) <= known
                and any(set(raw_source_ids) <= set(event.source_item_ids) for event in events)
            ):
                diagnostics["compiler"]["dropped_resolved_unit_routes"].append({
                    "unresolved_id": item.unresolved_id,
                    "source_item_ids": raw_source_ids,
                })
                continue
            covering_event = _find_covering_event(raw_source_ids, known, events)
            if covering_event is not None and _is_embedded_event_uncertainty(item):
                diagnostics["compiler"]["embedded_event_uncertainties"].append({
                    "unresolved_id": item.unresolved_id,
                    "reference_type": item.reference_type,
                    "source_id": item.relation_source_id,
                    "target_id": item.relation_target_id,
                    "reason": item.reason,
                    "source_item_ids": source_ids,
                    "evidence": [reference.model_dump() for reference in evidence],
                    "event_chain_id": covering_event.chain_id,
                    "event_sequence": covering_event.sequence,
                })
                continue
            output.append(Unresolved(
                unresolved_id=item.unresolved_id,
                reference_type=item.reference_type,
                source_id=item.relation_source_id,
                target_id=item.relation_target_id,
                reason=item.reason,
                repair_attempts=item.repair_attempts,
                repair_detail=item.repair_detail,
                source_item_ids=source_ids,
                evidence=evidence,
            ))
        return tuple(output)

    def _compile_evidence(
        self, finding_type, finding_id, references, known, metadata, diagnostics,
    ):
        output = []
        source_ids = []
        for reference_index, reference in enumerate(references):
            accepted = []
            for source_id in _ordered_unique(reference.source_item_ids):
                if source_id in known:
                    accepted.append(source_id)
                    source_ids.append(source_id)
                else:
                    diagnostics["compiler"]["rejected_source_item_ids"].append({
                        "finding_type": finding_type,
                        "finding_id": str(finding_id),
                        "evidence_index": reference_index,
                        "source_item_id": source_id,
                    })
            if not accepted:
                continue
            relative_path, item_key = self._canonical_location(accepted, metadata)
            output.append(EvidenceReference(
                source_item_ids=tuple(accepted),
                snippet=reference.snippet,
                relative_path=relative_path,
                item_key=item_key,
            ))
        return tuple(output), _ordered_unique(source_ids)

    @staticmethod
    def _canonical_location(source_ids, metadata):
        if len(source_ids) != 1 or source_ids[0] not in metadata:
            return None, None
        item = metadata[source_ids[0]]
        return item.relative_path, item.item_key

    @staticmethod
    def _accept_identity(kind, identity, seen, diagnostics):
        if identity not in seen:
            seen.add(identity)
            return True
        diagnostics["compiler"]["dropped_duplicate_findings"].append({
            "finding_type": kind,
            "identity": str(identity),
        })
        return False

    @staticmethod
    def _drop_ungrounded(kind, identity, diagnostics):
        diagnostics["compiler"]["dropped_ungrounded_findings"].append({
            "finding_type": kind,
            "identity": str(identity),
        })

    @staticmethod
    def _deduplicate_unresolved(items, diagnostics):
        output = []
        seen = set()
        for item in items:
            if item.unresolved_id in seen:
                diagnostics["compiler"]["dropped_duplicate_findings"].append({
                    "finding_type": "unresolved",
                    "identity": item.unresolved_id,
                })
                continue
            seen.add(item.unresolved_id)
            output.append(item)
        return tuple(output)

    def _new_diagnostics(self, model_diagnostics):
        return {
            "model": dict(model_diagnostics),
            "compiler": {
                "schema_version": self.schema_version,
                "rejected_source_item_ids": [],
                "dropped_ungrounded_findings": [],
                "dropped_duplicate_findings": [],
                "unknown_archive_context_links": [],
                "unknown_entity_links": [],
                "rejected_dynamic_entity_candidates": [],
                "dropped_dynamic_entity_links": [],
                "rejected_entity_evidence_ids": [],
                "rejected_local_unit_ids": [],
                "inferred_local_unit_ids": [],
                "rejected_asset_local_unit_ids": [],
                "dropped_resolved_unit_routes": [],
                "embedded_event_uncertainties": [],
                "merge_evidence_rejections": [],
                "merge_evidence_acceptances": [],
                "uncovered_source_item_ids": [],
                "chain_consolidation": {},
                "entity_normalization": {},
                "adjudication": dict(model_diagnostics.get("event_adjudication", {}) or {}),
            },
        }


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _normalize_entity_surface(value: str) -> str:
    """Normalize display text while preserving ordinary punctuation and spacing."""

    return re.sub(r"§(?:!|[A-Za-z0-9])", "", value).casefold()


def _is_dynamic_entity_name(value: str) -> bool:
    normalized = _normalize_entity_surface(value).strip()
    return bool(
        re.fullmatch(r"\[[a-z_]\w*\.[a-z_]\w*\]", normalized)
        or re.fullmatch(r"\$[a-z_]\w*\$", normalized)
        or any(marker in normalized for marker in (
            "动态姓名", "动态插值", "dynamic name", "dynamic interpolation",
            "runtime placeholder",
        ))
        or normalized in {"root polity", "root empire", "root country"}
    )


def _entity_surface_matches(source: Any, surfaces: tuple[str, ...]) -> bool:
    if source is None:
        return False
    source_text = _normalize_entity_surface(str(getattr(source, "source_text", "")))
    return bool(source_text) and any(surface in source_text for surface in surfaces)


def _find_covering_event(raw_source_ids, known, events):
    if not raw_source_ids or not set(raw_source_ids) <= known:
        return None
    source_ids = set(raw_source_ids)
    return next(
        (event for event in events if source_ids <= set(event.source_item_ids)),
        None,
    )


def _is_embedded_event_uncertainty(item: UnresolvedFinding) -> bool:
    """Recognize only entity-property uncertainty embedded in an event text."""

    return (
        item.reference_type == "source_evidence"
        and item.relation_source_id.casefold().startswith("entity_")
        and bool(re.fullmatch(r"\[[^\[\]]+\]", item.relation_target_id.strip()))
    )


def _link_unresolved_id(chain_id: str, archive_id: str) -> str:
    digest = hashlib.sha256(f"{chain_id}\0{archive_id}".encode("utf-8")).hexdigest()[:16]
    return f"compiler-archive-link-{digest}"


def _entity_link_unresolved_id(chain_id: str, entity_id: str) -> str:
    digest = hashlib.sha256(f"{chain_id}\0{entity_id}".encode("utf-8")).hexdigest()[:16]
    return f"compiler-entity-link-{digest}"


__all__ = [
    "ArchiveNarrativeFinding",
    "ContextResearchDraftCompiler",
    "ContextResearchFindings",
    "EventChainFinding",
    "FindingEvidence",
    "ReferenceAssetFinding",
    "ResearchEntityFinding",
    "UnresolvedFinding",
]
