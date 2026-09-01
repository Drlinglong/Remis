"""Deterministic frequency grades for Context Research entities.

The research model may judge plot importance, but it does not own the A/B/C
frequency grade.  Remis scans literal aliases after semantic entity merging,
counts raw mentions for display, and grades distinct local-unit coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_tree_v2_candidate_rules import (
    non_overlapping_matches,
    scan_aliases,
)


EntityFrequencyGrade = Literal["A", "B", "C"]


@dataclass(frozen=True, slots=True)
class EntityFrequencyMetrics:
    """Program-owned mention and distinct-unit coverage metrics."""

    mention_count: int
    local_unit_ids: tuple[str, ...]
    local_unit_coverage: int
    source_files: tuple[str, ...]
    file_spread: int
    frequency_grade: EntityFrequencyGrade


def grade_for_local_unit_coverage(coverage: int) -> EntityFrequencyGrade:
    """Return the original Tree v2 A/B/C grade."""

    if coverage >= 3:
        return "A"
    if coverage == 2:
        return "B"
    return "C"


def calculate_entity_frequency(
    name: str,
    aliases: Sequence[str],
    local_units: Mapping[str, LocalTextUnit] | Sequence[LocalTextUnit],
    *,
    source_language: str = "en",
) -> EntityFrequencyMetrics:
    """Scan the request corpus once per entity using merged literal aliases."""

    units = tuple(local_units.values()) if isinstance(local_units, Mapping) else tuple(local_units)
    surfaces = scan_aliases(tuple(dict.fromkeys((name, *aliases))), source_language)
    mention_count = 0
    matched_unit_ids: list[str] = []
    matched_files: list[str] = []
    for unit in units:
        unit_matches = 0
        for source in unit.items:
            source_matches = len(non_overlapping_matches(source.source_text, surfaces))
            unit_matches += source_matches
            if source_matches and source.relative_path not in matched_files:
                matched_files.append(source.relative_path)
        if unit_matches:
            mention_count += unit_matches
            matched_unit_ids.append(unit.unit_id)
    coverage = len(matched_unit_ids)
    return EntityFrequencyMetrics(
        mention_count=mention_count,
        local_unit_ids=tuple(matched_unit_ids),
        local_unit_coverage=coverage,
        source_files=tuple(matched_files),
        file_spread=len(matched_files),
        frequency_grade=grade_for_local_unit_coverage(coverage),
    )


__all__ = [
    "EntityFrequencyGrade",
    "EntityFrequencyMetrics",
    "calculate_entity_frequency",
    "grade_for_local_unit_coverage",
]
