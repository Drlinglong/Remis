from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_chain_consolidation import (
    consolidate_event_steps,
    validate_event_merge_evidence,
)
from scripts.core.services.context_research_contract import EvidenceReference, EventChain


def _event(
    chain_id: str,
    sequence: int,
    unit_id: str,
    source_id: str,
    entity_ids=(),
    event: str | None = None,
) -> EventChain:
    return EventChain(
        chain_id=chain_id,
        sequence=sequence,
        event=event or f"{chain_id} event",
        local_unit_ids=(unit_id,),
        entity_ids=tuple(entity_ids),
        source_item_ids=(source_id,),
        evidence=(EvidenceReference(source_item_ids=(source_id,)),),
    )


def _units() -> tuple[LocalTextUnit, ...]:
    return tuple(
        LocalTextUnit(
            unit_id=f"unit_{index}",
            unit_key=f"events/demo.yml::remis_crisis.{index + 1}",
            items=(SourceItem(
                source_item_id=f"source-{index}",
                relative_path="events/demo.yml",
                item_key=f"remis_crisis.{index + 1}.desc",
                source_order=index,
                source_text=f"Step {index + 1}.",
            ),),
        )
        for index in range(2)
    )


def test_exact_coverage_duplicate_steps_merge_stably_and_union_links() -> None:
    events = (
        _event("chain-z", 0, "unit_0", "source-0", ("entity-z",)),
        _event("chain-a", 0, "unit_0", "source-0", ("entity-a",)),
        _event("chain-b", 1, "unit_1", "source-1"),
    )

    result, diagnostics = consolidate_event_steps(events, _units())

    assert [(event.chain_id, event.sequence) for event in result] == [
        ("chain-a", 0), ("chain-b", 1),
    ]
    assert result[0].entity_ids == ("entity-a", "entity-z")
    assert diagnostics["automatic_duplicate_merge_count"] == 1
    assert diagnostics["duplicate_groups"] == [{
        "coverage": ["unit_0"],
        "sequence": 0,
        "canonical_chain_id": "chain-a",
        "merged_chain_ids": ["chain-a", "chain-z"],
    }]


def test_different_sequences_are_not_merged_and_are_exposed_as_lead_candidates() -> None:
    events = (
        _event("fragment-a", 0, "unit_0", "source-0", ("entity-remis",)),
        _event("fragment-b", 1, "unit_1", "source-1", ("entity-remis",)),
    )

    result, diagnostics = consolidate_event_steps(events, _units())

    assert len(result) == 2
    assert diagnostics["automatic_duplicate_merge_count"] == 0
    assert diagnostics["candidate_edge_count"] == 1
    assert diagnostics["lead_review_candidates"] == [{
        "component_id": "chain-review-component-001",
        "member_chain_ids": ["fragment-a", "fragment-b"],
        "member_event_refs": ["fragment-a:0", "fragment-b:1"],
        "local_unit_ids": ["unit_0", "unit_1"],
        "key_families": ["remis_crisis"],
        "signals": ["adjacent_local_units", "same_file", "same_key_family", "shared_entities"],
        "candidate_edge_count": 1,
        "evidence_summary": [{
            "source_item_ids": ["source-0"], "snippet": None,
            "relative_path": None, "item_key": None,
        }, {
            "source_item_ids": ["source-1"], "snippet": None,
            "relative_path": None, "item_key": None,
        }],
        "shared_entity_ids": ["entity-remis"],
        "complete_linkage": True,
        "rejected_pairs": [],
        "requires_lead_decision": True,
    }]
    assert diagnostics["boundary_doubts"][0]["reason_codes"] == ["no_narrative_continuity"]


def test_multiple_edges_are_one_component_and_boundary_is_grouped() -> None:
    events = (
        _event("fragment-a", 0, "unit_0", "source-0", ("entity-remis",)),
        _event("fragment-b", 1, "unit_1", "source-1"),
        _event("fragment-c", 2, "unit_1", "source-1", ("entity-remis",)),
    )

    _, diagnostics = consolidate_event_steps(events, _units())

    assert diagnostics["candidate_edge_count"] == 1
    assert len(diagnostics["lead_review_components"]) == 1
    component = diagnostics["lead_review_components"][0]
    assert component["candidate_edge_count"] == 1
    assert component["member_event_refs"] == ["fragment-a:0", "fragment-c:2"]
    assert diagnostics["boundary_doubts"][0]["reason_codes"] == ["no_narrative_continuity"]


def test_single_signal_does_not_create_a_merge_candidate() -> None:
    events = (
        _event("fragment-a", 0, "unit_0", "source-0"),
        _event("fragment-b", 1, "unit_1", "source-1"),
    )

    _, diagnostics = consolidate_event_steps(events, _units())

    assert diagnostics["candidate_edge_count"] == 0
    assert diagnostics["lead_review_components"] == []


def test_negative_branch_evidence_rejects_an_otherwise_positive_pair() -> None:
    units = (
        LocalTextUnit(
            unit_id="unit_0",
            unit_key="events/demo.yml::crisis.branch_a.1",
            items=(SourceItem(
                source_item_id="source-0",
                relative_path="events/demo.yml",
                item_key="crisis.branch_a.1.desc",
                source_order=0,
                source_text="The crisis chooses branch A.",
            ),),
        ),
        LocalTextUnit(
            unit_id="unit_1",
            unit_key="events/demo.yml::crisis.branch_b.1",
            items=(SourceItem(
                source_item_id="source-1",
                relative_path="events/demo.yml",
                item_key="crisis.branch_b.1.desc",
                source_order=1,
                source_text="The crisis chooses branch B.",
            ),),
        ),
    )
    events = (
        _event("branch-a", 0, "unit_0", "source-0", ("entity-remis",)),
        _event("branch-b", 1, "unit_1", "source-1", ("entity-remis",)),
    )

    _, diagnostics = consolidate_event_steps(events, units)
    validation = validate_event_merge_evidence(events, units)

    assert diagnostics["candidate_edge_count"] == 1
    assert diagnostics["lead_review_components"][0]["complete_linkage"] is False
    assert validation["allowed"] is False
    assert validation["reason"] == "merge_rejected_by_negative_evidence"
    assert validation["rejected_pairs"][0]["negative_evidence"][0]["code"] == (
        "mutually_exclusive_branch"
    )
