"""Deterministic entity-resolution for compiled Context Research findings.

The compiler first creates blocking candidates from source-grounded normalized
names and aliases. It then makes an auditable pair decision using source
overlap, type compatibility, and alias overlap. Accepted pairs are merged with
complete-linkage protection so a weak transitive bridge cannot create a
mega-entity. No provider call is made here.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_research_contract import (
    EvidenceReference,
    EventChain,
    ResearchEntity,
)
from scripts.core.services.context_research_entity_grading import (
    calculate_entity_frequency,
)
from scripts.core.services.context_tree_v2_candidate_rules import (
    non_overlapping_matches,
    scan_aliases,
)
from scripts.schemas.context_candidate import normalized_match_key


_IMPORTANCE_RANK = {"background": 0, "supporting": 1, "primary": 2}


def normalize_compiled_entities(
    entities: Sequence[ResearchEntity],
    events: Sequence[EventChain],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
    *,
    source_language: str = "en",
) -> tuple[tuple[ResearchEntity, ...], tuple[EventChain, ...], dict[str, Any]]:
    """Resolve source-grounded entity duplicates with pairwise evidence."""

    units = _coerce_units(local_units)
    source_texts = {
        str(item.source_item_id): str(item.source_text)
        for unit in units.values()
        for item in unit.items
    }
    grounded_keys = {
        entity.entity_id: _grounded_match_keys(entity, source_texts, source_language)
        for entity in entities
    }
    candidates = _blocking_pairs(entities, grounded_keys)
    pair_decisions = [
        _pair_decision(first, second, grounded_keys, source_language)
        for first, second in candidates
    ]
    accepted = {
        frozenset((decision["entity_a"], decision["entity_b"]))
        for decision in pair_decisions
        if decision["accepted"]
    }
    groups, transitive_blocks = _complete_linkage_groups(entities, accepted)
    replacements: dict[str, str] = {}
    normalized: list[ResearchEntity] = []
    merged_groups: list[dict[str, Any]] = []
    evidence_conflicts: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: _entity_sort_key(entities[item[0]])):
        members = tuple(sorted((entities[index] for index in group), key=_entity_sort_key))
        if len(members) == 1:
            normalized.append(members[0])
            continue
        merged, provenance, conflicts_for_group = _merge_group(
            members, grounded_keys, source_texts, units, source_language,
        )
        normalized.append(merged)
        replacements.update({item.entity_id: merged.entity_id for item in members})
        merged_groups.append(provenance)
        evidence_conflicts.extend(conflicts_for_group)

    rewritten_events = tuple(
        event.model_copy(update={
            "entity_ids": _sorted_unique(
                replacements.get(entity_id, entity_id) for entity_id in event.entity_ids
            ),
        })
        if any(entity_id in replacements for entity_id in event.entity_ids)
        else event
        for event in events
    )
    diagnostics = {
        "schema_version": "context-research-entity-normalizer-v2",
        "blocking_candidate_count": len(candidates),
        "pair_decisions": pair_decisions,
        "accepted_pair_count": len(accepted),
        "automatic_merge_count": len(merged_groups),
        "merged_groups": merged_groups,
        "blocked_complete_linkage_merges": transitive_blocks,
        "blocked_type_conflicts": [
            {
                "match_entity_ids": [item["entity_a"], item["entity_b"]],
                "entity_types": sorted({item["type_a"], item["type_b"]}),
                "reason": "incompatible concrete entity types share a grounded alias",
            }
            for item in pair_decisions
            if not item["type_compatible"]
        ],
        "rejected_pairs": [item for item in pair_decisions if not item["accepted"]],
        "evidence_conflicts": evidence_conflicts,
        "rewritten_event_link_count": sum(
            entity_id != replacements.get(entity_id, entity_id)
            for event in events
            for entity_id in event.entity_ids
        ),
    }
    return tuple(normalized), rewritten_events, diagnostics


def _coerce_units(
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
) -> dict[str, LocalTextUnit]:
    if isinstance(local_units, Mapping):
        return {str(key): value for key, value in local_units.items()}
    return {str(unit.unit_id): unit for unit in local_units}


def _grounded_match_keys(
    entity: ResearchEntity,
    source_texts: Mapping[str, str],
    source_language: str,
) -> frozenset[str]:
    keys: set[str] = set()
    for surface in (entity.name, *entity.aliases):
        key = normalized_match_key(surface, source_language)
        if not key:
            continue
        aliases = scan_aliases((surface,), source_language)
        if any(
            non_overlapping_matches(source_texts[source_id], aliases)
            for source_id in entity.source_item_ids
            if source_id in source_texts
        ):
            keys.add(key)
    return frozenset(keys)


def _blocking_pairs(
    entities: Sequence[ResearchEntity],
    grounded_keys: Mapping[str, frozenset[str]],
) -> list[tuple[ResearchEntity, ResearchEntity]]:
    """Generate pairs only inside a shared normalized-name blocking bucket."""

    buckets: defaultdict[str, list[ResearchEntity]] = defaultdict(list)
    for entity in entities:
        for key in grounded_keys.get(entity.entity_id, ()):
            buckets[key].append(entity)
    pairs: dict[tuple[str, str], tuple[ResearchEntity, ResearchEntity]] = {}
    for key in sorted(buckets):
        members = sorted(buckets[key], key=_entity_sort_key)
        for first, second in combinations(members, 2):
            pair_key = tuple(sorted((first.entity_id, second.entity_id)))
            pairs[pair_key] = (first, second)
    return [pairs[key] for key in sorted(pairs)]


def _pair_decision(
    first: ResearchEntity,
    second: ResearchEntity,
    grounded_keys: Mapping[str, frozenset[str]],
    source_language: str,
) -> dict[str, Any]:
    overlap = sorted(
        grounded_keys.get(first.entity_id, frozenset())
        & grounded_keys.get(second.entity_id, frozenset())
    )
    shared_sources = sorted(set(first.source_item_ids) & set(second.source_item_ids))
    type_compatible = _types_compatible(first.entity_type, second.entity_type)
    costs: list[str] = []
    if not shared_sources:
        costs.append("no_shared_source_evidence")
    if not type_compatible:
        costs.append("incompatible_entity_types")
    if not overlap:
        costs.append("no_grounded_alias_overlap")
    accepted = bool(overlap) and type_compatible
    return {
        "entity_a": first.entity_id,
        "entity_b": second.entity_id,
        "alias_overlap_keys": overlap,
        "shared_source_item_ids": shared_sources,
        "type_a": first.entity_type,
        "type_b": second.entity_type,
        "type_compatible": type_compatible,
        "evidence_strength": _evidence_strength(shared_sources, type_compatible, overlap),
        "costs": costs,
        "accepted": accepted,
        "reason": (
            "grounded_alias_overlap_and_compatible_type"
            if accepted else "pair_evidence_insufficient_or_type_conflict"
        ),
        "source_language": source_language,
    }


def _evidence_strength(
    shared_sources: Sequence[str], type_compatible: bool, overlap: Sequence[str],
) -> str:
    if not type_compatible:
        return "rejected_type_conflict"
    if shared_sources and overlap:
        return "strong"
    if overlap:
        return "grounded_alias"
    return "none"


def _types_compatible(first: str, second: str) -> bool:
    return first == second or first == "other" or second == "other"


def _complete_linkage_groups(
    entities: Sequence[ResearchEntity],
    accepted_pairs: set[frozenset[str]],
) -> tuple[list[tuple[int, ...]], list[dict[str, Any]]]:
    """Union only when every cross-pair in the resulting group was accepted."""

    parent = list(range(len(entities)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def members(root: int) -> list[int]:
        return [index for index in range(len(entities)) if find(index) == root]

    blocked: list[dict[str, Any]] = []
    ordered_pairs = sorted(accepted_pairs, key=lambda pair: tuple(sorted(pair)))
    entity_index = {entity.entity_id: index for index, entity in enumerate(entities)}
    for pair in ordered_pairs:
        first_id, second_id = sorted(pair)
        first_root = find(entity_index[first_id])
        second_root = find(entity_index[second_id])
        if first_root == second_root:
            continue
        first_members, second_members = members(first_root), members(second_root)
        missing = [
            (entities[left].entity_id, entities[right].entity_id)
            for left in first_members
            for right in second_members
            if frozenset((entities[left].entity_id, entities[right].entity_id))
            not in accepted_pairs
        ]
        if missing:
            blocked.append({
                "candidate_pair": [first_id, second_id],
                "reason": "complete_linkage_pair_missing",
                "missing_pairs": [list(item) for item in missing],
            })
            continue
        parent[second_root] = first_root
    groups: defaultdict[int, list[int]] = defaultdict(list)
    for index in range(len(entities)):
        groups[find(index)].append(index)
    return [tuple(values) for values in groups.values()], blocked


def _merge_group(
    members: Sequence[ResearchEntity],
    grounded_keys: Mapping[str, frozenset[str]],
    source_texts: Mapping[str, str],
    units: Mapping[str, LocalTextUnit],
    source_language: str,
) -> tuple[ResearchEntity, dict[str, Any], list[dict[str, Any]]]:
    surfaces = _surface_records(members, source_texts, source_language)
    canonical_surface = min(
        surfaces,
        key=lambda item: (
            -item["frequency"], len(item["normalized"]),
            item["normalized"], item["surface"],
        ),
    )["surface"]
    canonical_key = normalized_match_key(canonical_surface, source_language)
    matching_members = [
        member for member in members
        if canonical_key in grounded_keys.get(member.entity_id, frozenset())
    ]
    canonical = min(matching_members or list(members), key=_entity_sort_key)
    all_surfaces = _sorted_surfaces(
        (surface for member in members for surface in (member.name, *member.aliases)),
        source_language,
    )
    aliases = tuple(surface for surface in all_surfaces if surface != canonical_surface)[:20]
    frequency = calculate_entity_frequency(
        canonical_surface, aliases, units, source_language=source_language,
    )
    source_ids = _sorted_unique(
        source_id for member in members for source_id in member.source_item_ids
    )
    evidence, conflicts = _merge_evidence(members)
    entity_type = next(
        (member.entity_type for member in members if member.entity_type != "other"),
        "other",
    )
    importance = max(
        (member.importance for member in members),
        key=lambda value: (_IMPORTANCE_RANK[value], value),
    )
    merged = canonical.model_copy(update={
        "name": canonical_surface,
        "entity_type": entity_type,
        "aliases": aliases,
        "importance": importance,
        "mention_count": frequency.mention_count,
        "local_unit_ids": frequency.local_unit_ids,
        "local_unit_coverage": frequency.local_unit_coverage,
        "source_files": frequency.source_files,
        "file_spread": frequency.file_spread,
        "source_item_ids": source_ids,
        "evidence": evidence,
        "frequency_grade": frequency.frequency_grade,
    })
    provenance = {
        "canonical_entity_id": canonical.entity_id,
        "canonical_display_name": canonical_surface,
        "merged_entity_ids": [member.entity_id for member in members if member is not canonical],
        "match_keys": sorted({
            key for member in members for key in grounded_keys.get(member.entity_id, ())
        }),
        "entity_type": entity_type,
        "source_item_ids": list(source_ids),
    }
    return merged, provenance, conflicts


def _surface_records(
    members: Sequence[ResearchEntity],
    source_texts: Mapping[str, str],
    source_language: str,
) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    source_ids = {
        source_id for member in members for source_id in member.source_item_ids
    }
    for surface in (
        surface for member in members for surface in (member.name, *member.aliases)
    ):
        normalized = normalized_match_key(surface, source_language)
        if not normalized:
            continue
        aliases = scan_aliases((surface,), source_language)
        frequency = sum(
            len(non_overlapping_matches(source_texts[source_id], aliases))
            for source_id in source_ids
            if source_id in source_texts
        )
        record = records.setdefault(surface, {"surface": surface, "normalized": normalized})
        record["frequency"] = max(int(record.get("frequency", 0)), frequency)
    return list(records.values()) or [{
        "surface": members[0].name,
        "normalized": normalized_match_key(members[0].name, source_language),
        "frequency": 0,
    }]


def _merge_evidence(
    members: Sequence[ResearchEntity],
) -> tuple[tuple[EvidenceReference, ...], list[dict[str, Any]]]:
    by_source_ids: defaultdict[tuple[str, ...], list[EvidenceReference]] = defaultdict(list)
    for member in members:
        for evidence in member.evidence:
            key = tuple(sorted(set(evidence.source_item_ids)))
            by_source_ids[key].append(evidence)
    output: list[EvidenceReference] = []
    conflicts: list[dict[str, Any]] = []
    for source_ids in sorted(by_source_ids):
        options = sorted(by_source_ids[source_ids], key=_evidence_sort_key)
        selected = options[0]
        output.append(selected.model_copy(update={"source_item_ids": source_ids}))
        snippets = {option.snippet for option in options}
        if len(snippets) > 1:
            conflicts.append({
                "source_item_ids": list(source_ids),
                "snippets": sorted(snippet or "" for snippet in snippets),
            })
    return tuple(output), conflicts


def _sorted_surfaces(values: Sequence[str] | Any, source_language: str = "en") -> tuple[str, ...]:
    unique = {str(value) for value in values if str(value).strip()}
    return tuple(sorted(unique, key=lambda value: (
        normalized_match_key(value, source_language), value.casefold(), value,
    )))


def _sorted_unique(values: Sequence[str] | Any) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _entity_sort_key(entity: ResearchEntity) -> tuple[str, str]:
    return entity.entity_id.casefold(), entity.entity_id


def _evidence_sort_key(evidence: EvidenceReference) -> tuple[str, str, str]:
    return evidence.snippet or "", evidence.relative_path or "", evidence.item_key or ""


__all__ = ["normalize_compiled_entities"]
