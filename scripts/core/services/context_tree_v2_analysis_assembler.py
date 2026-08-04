"""Assemble v2 model results into the immutable archive-tree storage contract."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Mapping, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_tree_v2_contract import ContextTreeV2Extraction
from scripts.core.services.context_tree_v2_candidate_rules import bounded_candidate_id
from scripts.schemas.context_tree_v2 import (
    ChunkEdgeMetadata,
    EntityAliasDescription,
    EntityDigest,
    EntityDigestSegment,
    EntityEvidenceReference,
    LocalFragmentCard,
    ReadTreeResponse,
    SiblingGroup,
    SourceEvidenceReference,
    Story,
    UnitRoute,
    UnresolvedReference,
)


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value))


def _stable_id(prefix: str, *parts: str) -> str:
    material = ":".join(str(part) for part in parts)
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, material).hex}"


class ContextTreeV2AnalysisAssembler:
    """Keep workflow, candidate and persistence models decoupled."""

    @classmethod
    def assemble(
        cls,
        *,
        project_id: str,
        tree_id: str,
        source_snapshot_hash: str,
        project_title: str,
        source_items: Sequence[SourceItem],
        local_units: Sequence[LocalTextUnit],
        chunks: Sequence[ContextUnitChunk],
        extractions: Sequence[ContextTreeV2Extraction],
        workflow_result: Any,
        governance: Any,
        entity_digest_result: Any,
        term_result: Any,
    ) -> ReadTreeResponse:
        item_lookup = {item.source_item_id: item for item in source_items}
        unit_lookup = {unit.unit_id: unit for unit in local_units}
        unit_batch = cls._unit_batches(chunks)
        fragment_cards = cls._fragments(
            extractions, chunks, unit_lookup, item_lookup,
        )
        catalog = workflow_result.catalog.catalog
        group_story = {
            group_id: story.story_id
            for story in catalog.stories
            for group_id in story.group_ids
        }
        fragment_summary = {item.fragment_id: item.summary for item in fragment_cards}
        stories = tuple(
            Story(
                story_id=story.story_id,
                group_ids=tuple(story.group_ids),
                title=story.story_id,
            )
            for story in catalog.stories
        )
        groups = tuple(
            SiblingGroup(
                group_id=group.group_id,
                story_id=group_story.get(group.group_id),
                fragment_ids=tuple(group.fragment_ids),
                title=group.group_id,
                summary="\n".join(
                    f"- {fragment_summary[fragment_id]}"
                    for fragment_id in group.fragment_ids
                    if fragment_id in fragment_summary
                ) or None,
            )
            for group in catalog.groups
        )
        projection = workflow_result.projection
        routes = tuple(
            UnitRoute(
                local_unit_id=route.local_unit_id,
                route=route.route,
                fragment_ids=tuple(route.fragment_ids),
            )
            for route in projection.unit_routes
        )
        evidence, digests = cls._entity_payloads(
            governance.candidates,
            entity_digest_result,
            unit_lookup,
            unit_batch,
        )
        merges_by_candidate = cls._semantic_merges(entity_digest_result)
        raw_contributions = cls._raw_candidate_contributions(
            extractions, governance.source_language,
        )
        return ReadTreeResponse(
            project_id=project_id,
            tree_id=tree_id,
            source_snapshot_hash=source_snapshot_hash,
            schema_version="context-tree-v2",
            prompt_version="context-archive-tree-v2",
            project_title=project_title,
            project_summary=entity_digest_result.project_overview.text,
            local_fragments=fragment_cards,
            unit_routes=routes,
            stories=stories,
            groups=groups,
            unresolved_references=cls._unresolved(extractions, projection),
            entity_evidence=evidence,
            entity_digests=digests,
            candidates=tuple(
                cls._candidate_payload(
                    item,
                    merges_by_candidate.get(item.candidate_id, ()),
                    raw_contributions.get(item.candidate_id, ()),
                )
                for item in governance.candidates
            ),
            term_variants=tuple(
                item.model_dump(mode="json") for item in term_result.terms
            ),
        )

    @staticmethod
    def _unit_batches(chunks: Sequence[ContextUnitChunk]) -> dict[str, int]:
        return {
            unit.unit_id: index
            for index, chunk in enumerate(chunks)
            for unit in chunk.core_units
        }

    @classmethod
    def _fragments(
        cls,
        extractions: Sequence[ContextTreeV2Extraction],
        chunks: Sequence[ContextUnitChunk],
        units: Mapping[str, LocalTextUnit],
        items: Mapping[str, SourceItem],
    ) -> tuple[LocalFragmentCard, ...]:
        cards: list[LocalFragmentCard] = []
        for batch_index, extraction in enumerate(extractions):
            metadata = chunks[batch_index].edge_metadata
            for fragment in extraction.local_fragments:
                refs = cls._fragment_evidence(fragment.unit_ids, units, items, batch_index)
                cards.append(LocalFragmentCard(
                    fragment_id=fragment.fragment_id,
                    summary=fragment.summary,
                    unit_ids=tuple(fragment.unit_ids),
                    continuation_clues=(fragment.continuation_cues,) if fragment.continuation_cues else (),
                    boundary_includes=fragment.boundary_includes,
                    boundary_excludes=fragment.boundary_excludes,
                    edge_metadata=ChunkEdgeMetadata(
                        chunk_id=f"chunk-{batch_index}",
                        touches_chunk_start=fragment.touches_chunk_start,
                        touches_chunk_end=fragment.touches_chunk_end,
                        previous_unit_ids=tuple(metadata.edge_before_unit_ids),
                        next_unit_ids=tuple(metadata.edge_after_unit_ids),
                    ),
                    source_evidence_refs=refs,
                ))
        return tuple(cards)

    @staticmethod
    def _fragment_evidence(
        unit_ids: Sequence[str],
        units: Mapping[str, LocalTextUnit],
        items: Mapping[str, SourceItem],
        batch_index: int,
    ) -> tuple[SourceEvidenceReference, ...]:
        refs: list[SourceEvidenceReference] = []
        for unit_id in unit_ids:
            for unit_item in units[unit_id].items:
                item = items[unit_item.source_item_id]
                refs.append(SourceEvidenceReference(
                    source_item_id=item.source_item_id,
                    source_ref=item.relative_path,
                    local_unit_id=unit_id,
                    item_key=item.item_key,
                    source_order=item.source_order,
                    excerpt=item.source_text[:2000],
                    full_source_text=item.source_text,
                    batch_id=f"chunk-{batch_index}",
                    batch_index=batch_index,
                    provenance="text_inferred",
                ))
        return tuple(refs)

    @classmethod
    def _entity_payloads(
        cls,
        candidates: Sequence[Any],
        result: Any,
        units: Mapping[str, LocalTextUnit],
        unit_batches: Mapping[str, int],
    ) -> tuple[tuple[EntityEvidenceReference, ...], tuple[EntityDigest, ...]]:
        digest_by_id = {item.candidate_id: item for item in result.digests}
        bundle_by_id = {item.candidate_id: item for item in result.evidence_bundles}
        evidence: list[EntityEvidenceReference] = []
        digests: list[EntityDigest] = []
        for candidate in candidates:
            if _enum(candidate.kind) != "entity":
                continue
            digest = digest_by_id.get(candidate.candidate_id)
            bundle = bundle_by_id.get(candidate.candidate_id)
            refs = cls._entity_evidence(candidate, digest, bundle, units, unit_batches)
            evidence.extend(refs)
            digests.append(cls._entity_digest(candidate, digest, refs))
        return tuple(evidence), tuple(digests)

    @staticmethod
    def _entity_evidence(
        candidate: Any,
        digest: Any | None,
        bundle: Any | None,
        units: Mapping[str, LocalTextUnit],
        unit_batches: Mapping[str, int],
    ) -> list[EntityEvidenceReference]:
        records = digest.full_evidence if digest is not None else getattr(bundle, "full_evidence", ())
        refs: list[EntityEvidenceReference] = []
        source_ids = set(candidate.source_item_ids)
        for record in records:
            unit = units.get(record.unit_id)
            if unit is None or not unit.items:
                continue
            grounded_items = [
                item for item in unit.items if item.source_item_id in source_ids
            ]
            for item in grounded_items:
                refs.append(EntityEvidenceReference(
                    evidence_id=_stable_id(
                        "evidence", candidate.candidate_id,
                        record.unit_id, item.source_item_id,
                    ),
                    entity_id=candidate.candidate_id,
                    source_item_id=item.source_item_id,
                    source_ref=item.relative_path,
                    local_unit_id=record.unit_id,
                    item_key=item.item_key,
                    source_order=item.source_order,
                    excerpt=item.source_text[:2000] or None,
                    full_source_text=item.source_text,
                    batch_id=f"chunk-{unit_batches.get(record.unit_id, 0)}",
                    batch_index=unit_batches.get(record.unit_id, 0),
                    included_in_digest=record.included_in_digest,
                    digest_segment_id=record.digest_segment_id,
                    digest_provenance=(
                        "final" if digest is not None and digest.digest_status == "complete"
                        else ("partial" if record.digest_segment_id else None)
                    ),
                    sampling_state=(
                        "included" if record.included_in_digest
                        else ("not_applicable" if digest is None else "excluded")
                    ),
                    metadata={
                        "digest_segment_ids": list(record.digest_segment_ids),
                        "unit_source_text": record.source_text,
                        "local_descriptions": list(record.local_descriptions),
                    },
                ))
        return refs

    @staticmethod
    def _entity_digest(candidate: Any, digest: Any | None, refs: Sequence[Any]) -> EntityDigest:
        level = _enum(candidate.grade)
        if level == "C":
            return EntityDigest(
                entity_id=candidate.candidate_id,
                canonical_name=candidate.canonical_name,
                level="C",
                alias_descriptions=tuple(
                    EntityAliasDescription(alias=alias) for alias in candidate.aliases
                ),
                evidence_ids=tuple(ref.evidence_id for ref in refs),
            )
        complete = digest is not None and digest.digest_status == "complete"
        partials = tuple(
            EntityDigestSegment(
                digest_segment_id=item.digest_segment_id,
                summary=item.summary,
                evidence_unit_ids=tuple(item.evidence_unit_ids),
                batch_indexes=tuple(item.batch_indexes),
            )
            for item in getattr(digest, "partial_digests", ())
        )
        segment_ids = tuple(dict.fromkeys(
            segment_id
            for ref in refs
            for segment_id in ref.metadata.get("digest_segment_ids", [])
        ))
        return EntityDigest(
            entity_id=candidate.candidate_id,
            canonical_name=candidate.canonical_name,
            level=level,
            summary=digest.final_digest if complete else None,
            final_digest=digest.final_digest if complete else None,
            mechanical_local_description=(digest.mechanical_local_description if digest else None),
            partial_digests=partials,
            alias_descriptions=tuple(
                EntityAliasDescription(
                    alias=alias,
                    description="; ".join(candidate.local_descriptions) or None,
                )
                for alias in candidate.aliases
            ),
            evidence_ids=tuple(ref.evidence_id for ref in refs),
            digest_segment_ids=segment_ids,
            source_batch_ids=tuple(dict.fromkeys(ref.batch_id for ref in refs if ref.batch_id)),
            digest_provenance="final" if complete else ("partial" if partials else "not_generated"),
        )

    @staticmethod
    def _candidate_payload(
        candidate: Any,
        merges: Sequence[Mapping[str, Any]],
        contributions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        level = _enum(candidate.grade)
        kind = _enum(candidate.kind)
        return {
            "candidate_id": candidate.candidate_id,
            "canonical_display_name": candidate.canonical_name,
            "aliases": list(candidate.aliases),
            "candidate_kind": kind,
            "tier": level,
            "mention_count": candidate.mention_count,
            "local_unit_coverage": candidate.local_unit_coverage,
            "event_group_coverage": len(candidate.event_group_ids),
            "local_unit_ids": list(candidate.local_unit_ids),
            "source_item_ids": list(candidate.source_item_ids),
            "event_group_ids": list(candidate.event_group_ids),
            "local_descriptions": list(candidate.local_descriptions),
            "semantic_merge_proposals": list(merges),
            "raw_chunk_contributions": list(contributions),
            "summary_eligible": kind == "entity" and level in {"A", "B"},
            "glossary_eligible": kind == "term" and level in {"A", "B"},
            "audit_only": level == "C",
        }

    @staticmethod
    def _semantic_merges(result: Any) -> dict[str, tuple[dict[str, Any], ...]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for merge in getattr(result, "semantic_merges", ()):
            payload = merge.model_dump(mode="json")
            involved = {
                merge.target_candidate_id,
                merge.source_candidate_id,
                *merge.member_candidate_ids,
            }
            for candidate_id in involved:
                grouped[candidate_id].append(payload)
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _raw_candidate_contributions(
        extractions: Sequence[Any], source_language: str,
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for batch_index, extraction in enumerate(extractions):
            for kind, values in (
                ("entity", extraction.entities), ("term", extraction.terms),
            ):
                for contribution in values:
                    surface = getattr(contribution, "name", None) or contribution.original
                    candidate_id = bounded_candidate_id(surface, source_language)
                    grouped[candidate_id].append({
                        "batch_index": batch_index,
                        "candidate_kind": kind,
                        "surface": surface,
                        "canonical_candidate": contribution.canonical_candidate,
                        "local_description": (
                            getattr(contribution, "description", None)
                            or getattr(contribution, "reasoning", None)
                        ),
                        "evidence": [
                            evidence.model_dump(mode="json")
                            for evidence in contribution.evidence
                        ],
                    })
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _unresolved(extractions: Sequence[Any], projection: Any) -> tuple[UnresolvedReference, ...]:
        rows: dict[tuple[str, str], UnresolvedReference] = {}
        unresolved = [
            item
            for extraction in extractions
            for item in extraction.unresolved_fragment_references
        ]
        unresolved.extend(projection.unresolved_fragment_references)
        for item in unresolved:
            key = (item.local_unit_id, item.fragment_id)
            rows[key] = UnresolvedReference(
                reference_id=_stable_id("unresolved", *key),
                reference_type="fragment",
                source_id=item.local_unit_id,
                target_id=item.fragment_id,
                reason=item.reason,
                repair_attempts=item.repair_attempts,
            )
        return tuple(rows.values())


__all__ = ["ContextTreeV2AnalysisAssembler"]
