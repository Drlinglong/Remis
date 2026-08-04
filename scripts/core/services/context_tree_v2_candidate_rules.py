"""Pure alias, coverage and merge rules for context-tree v2 candidates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Iterable, Mapping, Sequence

from pydantic import ValidationError

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import (
    EntityContribution,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.schemas.context_candidate import (
    CandidateKind,
    candidate_aggregate_key,
    normalized_match_key,
)
from scripts.schemas.context_tree_v2_candidates import (
    SemanticEntityMerge,
    TreeCandidate,
    TreeCandidateGrade,
    TreeCandidateKind,
)


_WORD_OR_HYPHEN = r"[\w-]"
_MAX_V2_CANDIDATE_ID_LENGTH = 180


@dataclass(frozen=True)
class CandidateContribution:
    """Normalized contribution retained while aggregates are collected."""

    surface: str
    kind: TreeCandidateKind
    evidence_source_ids: tuple[str, ...]
    description: str | None = None


@dataclass
class CandidateAggregate:
    """Mutable collection used only inside one governance call."""

    candidate_id: str
    contributions: list[CandidateContribution] = field(default_factory=list)


def unit_index(units: Sequence[LocalTextUnit]) -> dict[str, tuple[str, ...]]:
    """Index source items to local units while preserving source order."""

    source_to_units: dict[str, list[str]] = defaultdict(list)
    seen_units: set[str] = set()
    for unit in units:
        if unit.unit_id in seen_units:
            raise ValueError(f"Local unit identities must be unique: {unit.unit_id}")
        seen_units.add(unit.unit_id)
        for item in unit.items:
            source_to_units[str(item.source_item_id)].append(unit.unit_id)
    return {source_id: tuple(unit_ids) for source_id, unit_ids in source_to_units.items()}


def collect_aggregates(
    extractions: Sequence[StructuredNeologismExtraction | Mapping[str, Any]],
    source_lookup: Mapping[str, SourceItem],
    language: str,
) -> tuple[dict[str, CandidateAggregate], list[dict[str, Any]]]:
    """Collect grounded term/entity surfaces using deterministic aliases."""

    aggregates: dict[str, CandidateAggregate] = {}
    dropped: list[dict[str, Any]] = []
    for batch_index, raw_extraction in enumerate(extractions):
        try:
            extraction = (
                raw_extraction
                if isinstance(raw_extraction, StructuredNeologismExtraction)
                else StructuredNeologismExtraction.model_validate(raw_extraction)
            )
        except ValidationError as error:
            dropped.append({"batch_index": batch_index, "reason": "invalid_extraction", "detail": str(error)[:500]})
            continue
        for contribution in (*extraction.terms, *extraction.entities):
            item = to_contribution(contribution, source_lookup)
            if item is None:
                dropped.append({"batch_index": batch_index, "reason": "empty_or_ungrounded_candidate"})
                continue
            candidate_id = bounded_candidate_id(item.surface, language)
            aggregates.setdefault(candidate_id, CandidateAggregate(candidate_id)).contributions.append(item)
    return aggregates, dropped


def bounded_candidate_id(surface: str, language: str) -> str:
    """Leave room for digest segment suffixes in the 200-char storage IDs."""

    raw = candidate_aggregate_key(surface, language)
    if len(raw) <= _MAX_V2_CANDIDATE_ID_LENGTH:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    prefix = raw[: _MAX_V2_CANDIDATE_ID_LENGTH - len(digest) - 1].rstrip()
    return f"{prefix}:{digest}"


def to_contribution(
    contribution: TermContribution | EntityContribution,
    source_lookup: Mapping[str, SourceItem],
) -> CandidateContribution | None:
    """Normalize one extraction contribution without assigning a grade."""

    surface = contribution.original if isinstance(contribution, TermContribution) else contribution.name
    if not str(surface).strip():
        return None
    evidence_ids = tuple(dict.fromkeys(
        evidence.source_item_id
        for evidence in contribution.evidence
        if evidence.source_item_id in source_lookup
    ))
    if not evidence_ids:
        return None
    declared_kind = getattr(contribution, "candidate_kind", None)
    category = getattr(contribution, "category", "other")
    is_entity = isinstance(contribution, EntityContribution) or declared_kind is CandidateKind.ENTITY
    if isinstance(contribution, TermContribution) and category in {"person", "place", "faction"}:
        is_entity = True
    description = getattr(contribution, "description", None) or getattr(contribution, "reasoning", None)
    return CandidateContribution(
        surface=str(surface),
        kind=TreeCandidateKind.ENTITY if is_entity else TreeCandidateKind.TERM,
        evidence_source_ids=evidence_ids,
        description=description,
    )


def scan_aliases(aliases: Sequence[str], language: str) -> tuple[str, ...]:
    """Expand only literal aliases and the safe English article variant."""

    expanded: list[str] = []
    for alias in aliases:
        cleaned = normalized_match_key(str(alias), language)
        if cleaned and cleaned not in expanded:
            expanded.append(cleaned)
        words = cleaned.split(maxsplit=1)
        if len(words) == 2 and words[0].casefold() in {"a", "an", "the"}:
            article_free = words[1]
            if article_free not in expanded:
                expanded.append(article_free)
    return tuple(expanded)


def non_overlapping_matches(text: str, aliases: Sequence[str]) -> list[tuple[int, int]]:
    """Find literal, case-insensitive alias occurrences without double-counting."""

    text = re.sub(r"\$name_([^$]+)\$", lambda match: match.group(1).replace("_", " "), text, flags=re.IGNORECASE)
    text = re.sub(r"§[A-Za-z!]", "", text)
    matches: list[tuple[int, int]] = []
    for alias in aliases:
        tokens = [token for token in re.split(r"\s+", alias) if token]
        if not tokens:
            continue
        pattern = rf"(?<!{_WORD_OR_HYPHEN})" + r"\s+".join(re.escape(token) for token in tokens) + rf"(?!{_WORD_OR_HYPHEN})"
        matches.extend((match.start(), match.end()) for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    selected: list[tuple[int, int]] = []
    for start, end in sorted(matches, key=lambda span: (span[0], -(span[1] - span[0]))):
        if not any(start < right and end > left for left, right in selected):
            selected.append((start, end))
    return selected


def scan_source_items(
    items: Sequence[SourceItem],
    aliases: Sequence[str],
) -> tuple[tuple[str, ...], int]:
    """Return source IDs and display-only mention count in source order."""

    source_ids: list[str] = []
    mention_count = 0
    for item in items:
        matches = non_overlapping_matches(item.source_text, aliases)
        if matches:
            source_ids.append(item.source_item_id)
            mention_count += len(matches)
    return tuple(source_ids), mention_count


def evidence_ids(
    aggregate: CandidateAggregate,
    source_lookup: Mapping[str, SourceItem],
    aliases: Sequence[str],
) -> tuple[str, ...]:
    """Keep evidence only when the source text literally contains an alias."""

    return tuple(dict.fromkeys(
        source_id
        for contribution in aggregate.contributions
        for source_id in contribution.evidence_source_ids
        if source_id in source_lookup
        and non_overlapping_matches(source_lookup[source_id].source_text, aliases)
    ))


def ordered_ids(items: Sequence[SourceItem], source_ids: Iterable[str]) -> tuple[str, ...]:
    selected = set(source_ids)
    return tuple(item.source_item_id for item in items if item.source_item_id in selected)


def ordered_local_ids(
    source_ids: Sequence[str],
    source_to_units: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    selected = {unit_id for source_id in source_ids for unit_id in source_to_units.get(source_id, ())}
    ordered: list[str] = []
    for unit_ids in source_to_units.values():
        for unit_id in unit_ids:
            if unit_id in selected and unit_id not in ordered:
                ordered.append(unit_id)
    return tuple(ordered)


def ordered_group_ids(
    local_ids: Sequence[str],
    groups_by_unit: Mapping[str, Sequence[str] | str],
) -> tuple[str, ...]:
    groups: list[str] = []
    for unit_id in local_ids:
        raw = groups_by_unit.get(unit_id, ())
        values = (raw,) if isinstance(raw, str) else raw
        for group_id in values:
            if str(group_id) and str(group_id) not in groups:
                groups.append(str(group_id))
    return tuple(groups)


def canonical_name(aliases: Sequence[str]) -> str:
    return min(
        aliases,
        key=lambda value: (
            int(str(value).casefold().startswith(("a ", "an ", "the "))),
            len(str(value)),
            str(value).casefold(),
            str(value),
        ),
    )


def resolved_kind(contributions: Sequence[CandidateContribution]) -> TreeCandidateKind:
    return (
        TreeCandidateKind.ENTITY
        if any(item.kind is TreeCandidateKind.ENTITY for item in contributions)
        else TreeCandidateKind.TERM
    )


def grade_for_coverage(local_unit_coverage: int) -> TreeCandidateGrade:
    if local_unit_coverage >= 3:
        return TreeCandidateGrade.A
    if local_unit_coverage == 2:
        return TreeCandidateGrade.B
    return TreeCandidateGrade.C


def normalize_overrides(
    overrides: Mapping[str, TreeCandidateGrade | str],
) -> tuple[dict[str, TreeCandidateGrade], list[dict[str, str]]]:
    normalized: dict[str, TreeCandidateGrade] = {}
    invalid: list[dict[str, str]] = []
    for key, value in overrides.items():
        try:
            normalized[str(key)] = TreeCandidateGrade(value)
        except (TypeError, ValueError):
            invalid.append({"candidate": str(key), "value": str(value)})
    return normalized, invalid


def override_for(
    candidate_id: str,
    contributions: Sequence[CandidateContribution],
    overrides: Mapping[str, TreeCandidateGrade],
    language: str,
) -> TreeCandidateGrade | None:
    keys = [candidate_id, candidate_id.split(":", 1)[-1]]
    keys.extend(normalized_match_key(item.surface, language) for item in contributions)
    keys.extend(item.surface for item in contributions)
    return next((overrides[key] for key in keys if key in overrides), None)


def validate_merges(
    merges: Sequence[SemanticEntityMerge | Mapping[str, Any]],
    candidates_by_id: Mapping[str, TreeCandidate],
) -> tuple[list[SemanticEntityMerge], list[dict[str, Any]]]:
    accepted: list[SemanticEntityMerge] = []
    rejected: list[dict[str, Any]] = []
    for raw in merges:
        try:
            merge = raw if isinstance(raw, SemanticEntityMerge) else SemanticEntityMerge.model_validate(raw)
        except ValidationError as error:
            rejected.append({"reason": "invalid_merge", "detail": str(error)[:500]})
            continue
        members = set(merge.member_candidate_ids)
        members.add(merge.canonical_candidate_id)
        unknown = sorted(member for member in members if member not in candidates_by_id)
        non_entities = sorted(
            member for member in members
            if member in candidates_by_id and candidates_by_id[member].kind is not TreeCandidateKind.ENTITY
        )
        if unknown or non_entities or merge.canonical_candidate_id not in merge.member_candidate_ids:
            rejected.append({
                "reason": "unsafe_merge_members",
                "canonical_candidate_id": merge.canonical_candidate_id,
                "unknown_candidate_ids": unknown,
                "non_entity_candidate_ids": non_entities,
            })
            continue
        accepted.append(merge)
    return accepted, rejected


def merge_groups(merges: Sequence[SemanticEntityMerge]) -> dict[str, tuple[str, ...]]:
    groups: dict[str, list[str]] = {}
    for merge in merges:
        canonical = merge.canonical_candidate_id
        group = groups.setdefault(canonical, [])
        for member in merge.member_candidate_ids:
            if member not in group:
                group.append(member)
        for other_canonical, other_members in list(groups.items()):
            if other_canonical == canonical:
                continue
            if canonical in other_members or any(member in other_members for member in group):
                for member in other_members:
                    if member not in group:
                        group.append(member)
                groups.pop(other_canonical, None)
    return {canonical: tuple(members) for canonical, members in groups.items()}


def merge_candidate_group(
    canonical_id: str,
    candidates: Sequence[TreeCandidate],
) -> TreeCandidate:
    ordered = sorted(candidates, key=lambda candidate: candidate.candidate_id)
    canonical = next(candidate for candidate in ordered if candidate.candidate_id == canonical_id)
    aliases = tuple(dict.fromkeys(alias for candidate in ordered for alias in candidate.aliases))
    local_ids = tuple(dict.fromkeys(unit_id for candidate in ordered for unit_id in candidate.local_unit_ids))
    source_ids = tuple(dict.fromkeys(source_id for candidate in ordered for source_id in candidate.source_item_ids))
    group_ids = tuple(dict.fromkeys(group_id for candidate in ordered for group_id in candidate.event_group_ids))
    descriptions = tuple(dict.fromkeys(description for candidate in ordered for description in candidate.local_descriptions))
    manual = next(
        (candidate.manual_grade_override for candidate in ordered if candidate.manual_grade_override is not None),
        None,
    )
    automatic = grade_for_coverage(len(local_ids))
    return canonical.model_copy(update={
        "aliases": aliases,
        "local_unit_ids": local_ids,
        "source_item_ids": source_ids,
        "event_group_ids": group_ids,
        "local_descriptions": descriptions,
        "mention_count": sum(candidate.mention_count for candidate in ordered),
        "local_unit_coverage": len(local_ids),
        "automatic_grade": automatic,
        "grade": manual or automatic,
        "grade_source": "manual" if manual else "automatic",
        "manual_grade_override": manual,
    })
