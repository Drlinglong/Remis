from __future__ import annotations

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import (
    EntityContribution,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.core.services.context_tree_v2_candidate_governance import (
    ContextTreeV2CandidateGovernanceService,
)
from scripts.schemas.context_tree_v2_candidates import TreeCandidateGrade


def _item(index: int, text: str, key: str | None = None) -> SourceItem:
    return SourceItem(
        source_item_id=f"source-{index}",
        relative_path="localisation/events.yml",
        item_key=key or f"event.{index}.desc",
        source_order=index,
        source_text=text,
    )


def _entity(name: str, source_ids: list[str], description: str | None = None) -> EntityContribution:
    return EntityContribution(
        name=name,
        entity_type="person",
        description=description,
        evidence=[SourceEvidence(source_item_id=source_id) for source_id in source_ids],
    )


def _term(name: str, source_ids: list[str]) -> TermContribution:
    return TermContribution(
        original=name,
        category="concept",
        evidence=[SourceEvidence(source_item_id=source_id) for source_id in source_ids],
    )


def _candidate(result, suffix: str):
    return next(item for item in result.candidates if item.candidate_id == f"entity:{suffix}")


def test_literal_aliases_merge_and_distinct_local_units_drive_grade_not_mentions():
    items = [
        _item(0, "The Horizon Signal appears. The Horizon Signal appears again."),
        _item(1, "Horizon Signal returns."),
        _item(2, "THE HORIZON SIGNAL is recorded."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    result = ContextTreeV2CandidateGovernanceService().govern(
        [StructuredNeologismExtraction(entities=[
            _entity("Horizon Signal", ["source-0"]),
            _entity("The Horizon Signal", ["source-1"]),
        ])],
        items,
        units,
        event_group_ids_by_unit={units[0].unit_id: "group-a", units[1].unit_id: "group-b", units[2].unit_id: "group-c"},
    )

    candidate = _candidate(result, "horizon signal")
    assert candidate.aliases == ("Horizon Signal", "The Horizon Signal")
    assert candidate.local_unit_coverage == 3
    assert candidate.grade is TreeCandidateGrade.A
    assert candidate.automatic_grade is TreeCandidateGrade.A
    assert candidate.mention_count == 4
    assert candidate.event_group_ids == ("group-a", "group-b", "group-c")
    assert result.report["mention_count_role"] == "display_only"


def test_repeated_mentions_in_one_unit_do_not_promote_and_manual_grade_wins():
    items = [
        _item(0, "Transient Doctrine appears three times: Transient Doctrine, Transient Doctrine."),
        _item(1, "Named Doctrine appears once."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    service = ContextTreeV2CandidateGovernanceService()
    result = service.govern(
        [StructuredNeologismExtraction(terms=[
            _term("Transient Doctrine", ["source-0"]),
            _term("Named Doctrine", ["source-1"]),
        ])],
        items,
        units,
        manual_grade_overrides={"Transient Doctrine": "A"},
    )

    transient = next(item for item in result.candidates if item.canonical_name == "Transient Doctrine")
    named = next(item for item in result.candidates if item.canonical_name == "Named Doctrine")
    assert transient.local_unit_coverage == 1
    assert transient.mention_count == 3
    assert transient.automatic_grade is TreeCandidateGrade.C
    assert transient.grade is TreeCandidateGrade.A
    assert transient.grade_source == "manual"
    assert named.grade is TreeCandidateGrade.C


def test_semantic_merge_recomputes_union_coverage_and_rejects_non_entity_members():
    items = [
        _item(0, "The Red Archivist arrives."),
        _item(1, "Red Archivist speaks."),
        _item(2, "The Ledger-Breaker leaves."),
        _item(3, "The Accord remains."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    service = ContextTreeV2CandidateGovernanceService()
    result = service.govern(
        [StructuredNeologismExtraction(
            entities=[
                _entity("Red Archivist", ["source-0", "source-1"]),
                _entity("The Ledger-Breaker", ["source-2"]),
            ],
            terms=[_term("Accord", ["source-3"])],
        )],
        items,
        units,
    )

    merged = service.apply_semantic_merges(result, [{
        "canonical_candidate_id": "entity:red archivist",
        "member_candidate_ids": ("entity:red archivist", "entity:ledger-breaker"),
        "reason": "same named person",
    }, {
        "canonical_candidate_id": "entity:red archivist",
        "member_candidate_ids": ("entity:red archivist", "entity:accord"),
    }])

    candidate = merged.candidate_for("entity:red archivist")
    assert candidate is not None
    assert candidate.local_unit_coverage == 3
    assert candidate.automatic_grade is TreeCandidateGrade.A
    assert candidate.grade is TreeCandidateGrade.A
    assert "entity:ledger-breaker" not in {item.candidate_id for item in merged.candidates}
    assert "unsafe_merge_members" in {item["reason"] for item in merged.report["semantic_merges_rejected"]}
    assert merged.report["grades_recomputed"] is True


def test_ungrounded_evidence_does_not_extend_source_or_local_coverage():
    items = [
        _item(0, "This item does not mention the candidate."),
        _item(1, "Horizon Signal is present."),
    ]
    result = ContextTreeV2CandidateGovernanceService().govern(
        [StructuredNeologismExtraction(entities=[_entity("Horizon Signal", ["source-0"])])],
        items,
        ContextLocalUnitBuilder.build(items),
    )

    candidate = _candidate(result, "horizon signal")
    assert candidate.source_item_ids == ("source-1",)
    assert candidate.local_unit_ids == ("unit_1",)
    assert candidate.local_unit_coverage == 1
