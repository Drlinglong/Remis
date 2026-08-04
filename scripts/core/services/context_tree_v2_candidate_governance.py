"""Candidate-governance service for the context-archive tree v2 slice.

Pure alias, coverage and semantic-merge mechanics live in
``context_tree_v2_candidate_rules``.  This service owns the integration
boundary and the report describing which program rules were applied.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.neologism_extraction import SourceItem, StructuredNeologismExtraction
from scripts.core.services.context_tree_v2_candidate_rules import (
    CandidateAggregate,
    canonical_name,
    collect_aggregates,
    evidence_ids,
    grade_for_coverage,
    merge_candidate_group,
    merge_groups,
    normalize_overrides,
    ordered_group_ids,
    ordered_ids,
    ordered_local_ids,
    override_for,
    resolved_kind,
    scan_aliases,
    scan_source_items,
    unit_index,
    validate_merges,
)
from scripts.schemas.context_tree_v2_candidates import (
    SemanticEntityMerge,
    TreeCandidate,
    TreeCandidateGrade,
    TreeCandidateGovernanceResult,
)


class ContextTreeV2CandidateGovernanceService:
    """Build v2 candidates from grounded extraction batches."""

    def __init__(self, source_language: str = "en") -> None:
        self.source_language = source_language

    def govern(
        self,
        extractions: Sequence[StructuredNeologismExtraction | Mapping[str, Any]],
        source_items: Sequence[SourceItem | Mapping[str, Any]],
        local_units: Sequence[LocalTextUnit] | None = None,
        *,
        event_group_ids_by_unit: Mapping[str, Sequence[str] | str] | None = None,
        manual_grade_overrides: Mapping[str, TreeCandidateGrade | str] | None = None,
    ) -> TreeCandidateGovernanceResult:
        """Build aliases and assign A/B/C from distinct local-unit coverage."""

        items = self._coerce_source_items(source_items)
        units = tuple(local_units) if local_units is not None else ContextLocalUnitBuilder.build(items)
        source_lookup = {item.source_item_id: item for item in items}
        aggregates, dropped = collect_aggregates(extractions, source_lookup, self.source_language)
        overrides, invalid_overrides = normalize_overrides(manual_grade_overrides or {})
        candidates = tuple(
            self._build_candidate(
                aggregate,
                items,
                source_lookup,
                unit_index(units),
                event_group_ids_by_unit or {},
                overrides,
            )
            for aggregate in sorted(aggregates.values(), key=lambda item: item.candidate_id)
        )
        return TreeCandidateGovernanceResult(
            candidates=candidates,
            source_language=self.source_language,
            report=self._report(candidates, dropped, invalid_overrides),
        )

    def apply_semantic_merges(
        self,
        result: TreeCandidateGovernanceResult,
        merges: Sequence[SemanticEntityMerge | Mapping[str, Any]],
    ) -> TreeCandidateGovernanceResult:
        """Apply safe semantic merges and recalculate coverage grades."""

        candidates_by_id = {candidate.candidate_id: candidate for candidate in result.candidates}
        accepted, rejected = validate_merges(merges, candidates_by_id)
        if not accepted:
            return result.model_copy(update={
                "report": self._merge_report(result.report, accepted, rejected, False),
            })
        groups = merge_groups(accepted)
        merged_ids = {member for group in groups.values() for member in group}
        output: list[TreeCandidate] = []
        emitted: set[str] = set()
        for candidate in result.candidates:
            if candidate.candidate_id not in merged_ids:
                output.append(candidate)
                continue
            canonical_id = next(
                root for root, members in groups.items() if candidate.candidate_id in members
            )
            if canonical_id in emitted:
                continue
            output.append(merge_candidate_group(
                canonical_id,
                [candidates_by_id[item_id] for item_id in groups[canonical_id]],
            ))
            emitted.add(canonical_id)
        output.sort(key=lambda candidate: candidate.candidate_id)
        return result.model_copy(update={
            "candidates": tuple(output),
            "report": self._merge_report(result.report, accepted, rejected, True, len(output)),
        })

    def _build_candidate(
        self,
        aggregate: CandidateAggregate,
        items: Sequence[SourceItem],
        source_lookup: Mapping[str, SourceItem],
        source_to_units: Mapping[str, tuple[str, ...]],
        event_group_ids_by_unit: Mapping[str, Sequence[str] | str],
        overrides: Mapping[str, TreeCandidateGrade],
    ) -> TreeCandidate:
        aliases = tuple(dict.fromkeys(item.surface for item in aggregate.contributions))
        literal_aliases = scan_aliases(aliases, self.source_language)
        source_ids, mention_count = scan_source_items(items, literal_aliases)
        source_ids = ordered_ids(
            items,
            (*source_ids, *evidence_ids(aggregate, source_lookup, literal_aliases)),
        )
        local_ids = ordered_local_ids(source_ids, source_to_units)
        override = override_for(
            aggregate.candidate_id,
            aggregate.contributions,
            overrides,
            self.source_language,
        )
        automatic_grade = grade_for_coverage(len(local_ids))
        return TreeCandidate(
            candidate_id=aggregate.candidate_id,
            canonical_name=canonical_name(aliases),
            aliases=aliases,
            kind=resolved_kind(aggregate.contributions),
            local_unit_ids=local_ids,
            source_item_ids=source_ids,
            event_group_ids=ordered_group_ids(local_ids, event_group_ids_by_unit),
            local_descriptions=tuple(dict.fromkeys(
                item.description.strip()
                for item in aggregate.contributions
                if item.description and item.description.strip()
            )),
            mention_count=mention_count,
            local_unit_coverage=len(local_ids),
            automatic_grade=automatic_grade,
            grade=override or automatic_grade,
            grade_source="manual" if override else "automatic",
            manual_grade_override=override,
        )

    @staticmethod
    def _coerce_source_items(
        source_items: Sequence[SourceItem | Mapping[str, Any]],
    ) -> tuple[SourceItem, ...]:
        items = tuple(
            item if isinstance(item, SourceItem) else SourceItem.model_validate(item)
            for item in source_items
        )
        ids = [item.source_item_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Source item identities must be unique for v2 candidate governance")
        return items

    @staticmethod
    def _report(
        candidates: Sequence[TreeCandidate],
        dropped: Sequence[Mapping[str, Any]],
        invalid_overrides: Sequence[Mapping[str, str]],
    ) -> dict[str, Any]:
        return {
            "coverage_authority": "program_distinct_local_units",
            "grade_rule": {"A": ">=3 local units", "B": "2 local units", "C": "1 local unit"},
            "mention_count_role": "display_only",
            "candidate_count": len(candidates),
            "literal_alias_merge_count": sum(max(len(candidate.aliases) - 1, 0) for candidate in candidates),
            "dropped_contributions": list(dropped),
            "invalid_manual_grade_overrides": list(invalid_overrides),
        }

    @staticmethod
    def _merge_report(
        report: Mapping[str, Any],
        accepted: Sequence[SemanticEntityMerge],
        rejected: Sequence[Mapping[str, Any]],
        recomputed: bool,
        candidate_count: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            **report,
            "semantic_merges_accepted": [merge.model_dump(mode="json") for merge in accepted],
            "semantic_merges_rejected": list(rejected),
            "grades_recomputed": recomputed,
        }
        if candidate_count is not None:
            payload["post_semantic_candidate_count"] = candidate_count
        return payload


# Concise aliases for callers migrating from the v10 service naming pattern.
ContextCandidateGovernanceV2Service = ContextTreeV2CandidateGovernanceService
