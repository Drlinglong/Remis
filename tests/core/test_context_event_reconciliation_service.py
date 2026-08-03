import json

import pytest

from scripts.core.context_local_units import ContextLocalUnitBuilder, DeliveryAssignment, DeliveryLink
from scripts.core.neologism_extraction import (
    EventChainContribution,
    NeologismMiningError,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    StructuredNeologismExtractor,
)
from scripts.core.services.context_event_reconciliation_service import (
    ContextAssignmentBatchingPolicy,
    ContextEventReconciliationService,
    EventReconciliationResult,
)
from scripts.core.services.context_analysis_report_service import ContextAnalysisReportService


class FakeHandler:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.schemas = []

    def generate_structured_with_messages(self, messages, *, schema, schema_name, temperature=0.0):
        self.calls.append(messages)
        self.schemas.append((schema, schema_name))
        return next(self.responses)


def _units(count=4, *, text_size=20):
    items = [
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="localisation/a.yml",
            item_key=f"story.{index}.title",
            source_order=index,
            source_text=(f"Narrative text {index}." + "x" * text_size),
        )
        for index in range(count)
    ]
    return ContextLocalUnitBuilder.build(items)


def _extraction(units):
    return StructuredNeologismExtraction(
        events=[
            EventChainContribution(
                chain_id="local-knight",
                event="The knight seeks aid.",
                sequence=1,
                evidence=[SourceEvidence(source_item_id="source-0")],
            ),
            EventChainContribution(
                chain_id="LOCAL-KNIGHT",
                event="The knight returns.",
                sequence=2,
                evidence=[SourceEvidence(source_item_id="source-1")],
            ),
        ],
        delivery_assignments=[
            DeliveryAssignment(
                local_unit_id=unit.unit_id,
                assignment_state="assigned",
                links=[DeliveryLink(
                    event_chain_id="local-knight",
                    relation="primary_member",
                    confidence=0.9,
                )],
            )
            for unit in units[:2]
        ],
    )


def _catalog_response(units):
    return {
        "final_chains": [{
            "chain_id": "knight_returns",
            "event": "A hunted knight seeks aid and returns.",
            "sequence": 0,
            "participants": ["knight"],
            "consequence": "The knight survives.",
            "evidence_unit_ids": [units[0].unit_id],
        }],
        "proposal_resolutions": [{
            "proposal_id": "b0_c0",
            "resolution": "merge_into",
            "final_chain_ids": ["knight_returns"],
        }],
    }


def _assignment_response(units):
    return {
        "assignments": [
            {
                "local_unit_id": unit.unit_id,
                "assignment_state": "assigned" if index < 2 else "unassigned",
                "links": [{
                    "event_chain_id": "knight_returns",
                    "relation": "primary_member",
                    "confidence": 0.97,
                }] if index < 2 else [],
            }
            for index, unit in enumerate(units)
        ]
    }


def test_reconcile_folds_same_batch_chain_steps_then_assigns_all_units():
    units = _units()
    handler = FakeHandler([
        json.dumps(_catalog_response(units)),
        json.dumps(_assignment_response(units)),
    ])

    result = ContextEventReconciliationService(handler).reconcile(
        units, [_extraction(units)], description_language="zh-cn"
    )

    cards = result.diagnostics["local_chain_cards"]
    assert len(cards) == 1
    assert cards[0]["proposal_id"] == "b0_c0"
    assert [step["sequence"] for step in cards[0]["steps"]] == [1, 2]
    assert cards[0]["primary_unit_ids"] == ["unit_0", "unit_1"]
    assert cards[0]["evidence_unit_ids"] == ["unit_0", "unit_1"]
    assert [event.chain_id for event in result.events] == ["knight_returns"]
    assert len(result.delivery_assignments) == len(units)
    assert result.delivery_assignments[0].source_item_ids == ["source-0"]
    assert [name for _, name in handler.schemas] == [
        "remis_event_chain_catalog",
        "remis_event_chain_assignments",
    ]
    assignment_schema = handler.schemas[1][0]
    assert "reasoning" not in assignment_schema["$defs"]["_ModelLink"]["properties"]
    assert "source_item_ids" not in assignment_schema["$defs"]["_ModelAssignment"]["properties"]


@pytest.mark.parametrize("mutation, detail", [
    (lambda data: data["proposal_resolutions"].clear(), "missing="),
    (lambda data: data["proposal_resolutions"].append(data["proposal_resolutions"][0]), "duplicate="),
    (lambda data: data["proposal_resolutions"][0].update(proposal_id="unknown"), "unexpected="),
])
def test_catalog_repairs_invalid_folded_card_disposition_once(mutation, detail):
    units = _units()
    invalid = _catalog_response(units)
    mutation(invalid)
    handler = FakeHandler([json.dumps(invalid), json.dumps(_catalog_response(units))])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert catalog.repair_reason == "coverage_validation"
    assert catalog.repair_detail
    assert detail in handler.calls[1][-1]["content"]


@pytest.mark.parametrize("resolution", ["promote_to_parent_story", "unresolved"])
def test_non_delivery_dispositions_cannot_reference_delivery_chains(resolution):
    units = _units()
    invalid = _catalog_response(units)
    invalid["proposal_resolutions"][0]["resolution"] = resolution
    handler = FakeHandler([
        json.dumps(invalid),
        json.dumps(_catalog_response(units)),
    ])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert "conflict with their final_chain_ids" in handler.calls[1][-1]["content"]


def test_static_project_cannot_create_an_orphan_delivery_chain():
    units = _units()
    invalid = {
        "final_chains": _catalog_response(units)["final_chains"],
        "proposal_resolutions": [],
    }
    valid = {"final_chains": [], "proposal_resolutions": []}
    handler = FakeHandler([json.dumps(invalid), json.dumps(valid)])

    catalog = ContextEventReconciliationService(handler).build_catalog(units, [])

    assert catalog.final_chains == []
    assert catalog.repair_count == 1
    assert "require a local chain-card source" in handler.calls[1][-1]["content"]


def test_assignment_repair_is_limited_to_the_failed_unit_batch():
    units = _units()
    invalid = _assignment_response(units)
    invalid["assignments"].pop()
    handler = FakeHandler([
        json.dumps(_catalog_response(units)),
        json.dumps(invalid),
        json.dumps(_assignment_response(units)),
    ])
    service = ContextEventReconciliationService(handler)
    catalog = service.build_catalog(units, [_extraction(units)])

    result = service.assign_batch(units, catalog)

    assert result.repair_count == 1
    assert result.repair_reason == "coverage_validation"
    assert "missing=" in result.repair_detail
    assert "Assignment coverage invalid" in handler.calls[2][-1]["content"]
    assert len(handler.calls[2][0]["content"]) < len(handler.calls[0][0]["content"]) + 3000


def test_invalid_assignment_after_one_repair_reports_validation_detail():
    units = _units()
    catalog_handler = FakeHandler([json.dumps(_catalog_response(units))])
    catalog = ContextEventReconciliationService(catalog_handler).build_catalog(
        units, [_extraction(units)]
    )
    invalid = _assignment_response(units)
    invalid["assignments"].pop()
    handler = FakeHandler([json.dumps(invalid), json.dumps(invalid)])

    with pytest.raises(NeologismMiningError, match=r"coverage_validation.*missing="):
        ContextEventReconciliationService(handler).assign_batch(units, catalog)


def test_one_unit_cannot_assign_two_relations_to_the_same_chain():
    units = _units()
    catalog_handler = FakeHandler([json.dumps(_catalog_response(units))])
    catalog = ContextEventReconciliationService(catalog_handler).build_catalog(
        units, [_extraction(units)]
    )
    invalid = _assignment_response(units)
    invalid["assignments"][0]["links"].append({
        "event_chain_id": "knight_returns",
        "relation": "theme_related",
        "confidence": 0.5,
    })
    handler = FakeHandler([json.dumps(invalid), json.dumps(_assignment_response(units))])

    result = ContextEventReconciliationService(handler).assign_batch(units, catalog)

    assert result.repair_count == 1
    assert "Duplicate delivery links" in handler.calls[1][-1]["content"]


def test_each_link_keeps_its_own_relation_without_reasoning_output():
    units = _units(2)
    catalog = _catalog_response(units)
    catalog["final_chains"].append({
        "chain_id": "parent_scene",
        "event": "A related established scene.",
        "sequence": 1,
        "participants": [],
        "consequence": None,
        "evidence_unit_ids": [units[1].unit_id],
    })
    catalog["proposal_resolutions"][0].update(
        resolution="split_across",
        final_chain_ids=["knight_returns", "parent_scene"],
    )
    assignment = {"assignments": [
        {
            "local_unit_id": units[0].unit_id,
            "assignment_state": "assigned",
            "links": [
                {"event_chain_id": "knight_returns", "relation": "primary_member", "confidence": 0.9},
                {"event_chain_id": "parent_scene", "relation": "supporting_context", "confidence": 0.8},
            ],
        },
        {
            "local_unit_id": units[1].unit_id,
            "assignment_state": "assigned",
            "links": [
                {"event_chain_id": "parent_scene", "relation": "primary_member", "confidence": 0.9},
            ],
        },
    ]}
    handler = FakeHandler([json.dumps(catalog), json.dumps(assignment)])
    service = ContextEventReconciliationService(handler)
    built = service.build_catalog(units, [_extraction(units)])

    result = service.assign_batch(units, built)

    assert [link.relation for link in result.assignments[0].links] == [
        "primary_member", "supporting_context"
    ]


def test_adaptive_batching_scales_to_950_units_without_splitting_units():
    units = _units(950, text_size=0)

    batches = ContextAssignmentBatchingPolicy.batches(units)

    assert len(batches) == 24
    assert all(len(batch) <= 40 for batch in batches)
    assert [unit.unit_id for batch in batches for unit in batch] == [
        unit.unit_id for unit in units
    ]


def test_adaptive_batching_honours_char_budget_and_keeps_oversized_unit_whole():
    units = _units(3, text_size=0)
    units[0].items[0].source_text = "x" * 6
    units[1].items[0].source_text = "y" * 6
    units[2].items[0].source_text = "z" * 30

    batches = ContextAssignmentBatchingPolicy.batches(
        units, max_units=10, max_source_chars=10
    )

    assert [[unit.unit_id for unit in batch] for batch in batches] == [
        ["unit_0"], ["unit_1"], ["unit_2"]
    ]


def test_split_card_report_does_not_cross_join_every_unit_to_every_final_chain():
    units = _units(2)
    local = _extraction(units)
    final_assignments = [
        DeliveryAssignment(
            local_unit_id=units[0].unit_id,
            assignment_state="assigned",
            links=[DeliveryLink(
                event_chain_id="chain_a", relation="primary_member", confidence=1.0
            )],
            source_item_ids=["source-0"],
        ),
        DeliveryAssignment(
            local_unit_id=units[1].unit_id,
            assignment_state="assigned",
            links=[DeliveryLink(
                event_chain_id="chain_b", relation="primary_member", confidence=1.0
            )],
            source_item_ids=["source-1"],
        ),
    ]
    reconciled = EventReconciliationResult(
        events=[],
        delivery_assignments=final_assignments,
        diagnostics={
            "local_chain_cards": [{
                "proposal_id": "b0_c0",
                "batch_index": 0,
                "local_chain_id": "local-knight",
                "steps": [],
            }],
            "proposal_resolutions": [{
                "proposal_id": "b0_c0",
                "resolution": "split_across",
                "final_chain_ids": ["chain_a", "chain_b"],
            }],
        },
    )

    mapped = ContextAnalysisReportService._mapped_local_memberships(
        [local], reconciled
    )

    assert mapped == {
        ("unit_0", "chain_a", "primary_member"),
        ("unit_1", "chain_b", "primary_member"),
    }


def test_prompts_make_unassigned_normal_and_static_resources_non_originating():
    local_prompt = StructuredNeologismExtractor.SYSTEM_PROMPT
    assignment_prompt = ContextEventReconciliationService.ASSIGNMENT_SYSTEM_PROMPT

    assert "does NOT mean every unit belongs" in assignment_prompt
    assert "must not be forced into a chain" in assignment_prompt
    assert "A static resource may receive" in assignment_prompt
    assert "Do not skip step (2)" in assignment_prompt
    assert "Do not create a chain" in local_prompt
    assert "supporting_context" in assignment_prompt
    assert "inherits classification with that unit" in assignment_prompt
    assert "Never invent a" in local_prompt
    assert "Static resources must not originate" in local_prompt
    local_schema = StructuredNeologismExtractor._model_response_schema()
    assert "reasoning" not in local_schema["$defs"]["DeliveryLink"]["properties"]
