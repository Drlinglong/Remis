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
from scripts.core.services.context_event_catalog_contract import LocalChainDisposition
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
        "parent_stories": [],
        "final_chains": [{
            "chain_id": "knight_returns",
            "event": "A hunted knight seeks aid and returns.",
            "sequence": 0,
            "participants": ["knight"],
            "consequence": "The knight survives.",
            "boundary_includes": "The hunted knight seeks aid and returns.",
            "boundary_excludes": "Other knight quests and generic knight mechanics.",
            "anchor_unit_ids": [units[0].unit_id],
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
    assert result.events[0].boundary_excludes == (
        "Other knight quests and generic knight mechanics."
    )
    assert len(result.delivery_assignments) == len(units)
    assert result.delivery_assignments[0].source_item_ids == ["source-0"]
    assert [name for _, name in handler.schemas] == [
        "remis_event_chain_catalog",
        "remis_event_chain_assignments",
    ]
    assignment_schema = handler.schemas[1][0]
    assert "reasoning" not in assignment_schema["$defs"]["_ModelLink"]["properties"]
    assert "source_item_ids" not in assignment_schema["$defs"]["_ModelAssignment"]["properties"]


def test_catalog_normalizes_prose_tainted_evidence_ids_without_a_repair_call():
    units = _units(95)
    response = _catalog_response(units)
    base_chain = response["final_chains"][0]
    response["final_chains"] = [
        {**base_chain, "chain_id": "chain_56", "evidence_unit_ids": [
            "unit_56开始从这里提供，unit_57、unit_58、unit_59、unit_60。",
        ]},
        {**base_chain, "chain_id": "chain_75", "evidence_unit_ids": [
            "unit_75各项内容由unit_75提供，unit_76和unit_77提供。",
        ]},
        {**base_chain, "chain_id": "chain_92", "evidence_unit_ids": [
            "unit_92分析、unit_93、unit_94。",
        ]},
    ]
    response["proposal_resolutions"][0].update(
        resolution="split_across",
        final_chain_ids=["chain_56", "chain_75", "chain_92"],
    )
    handler = FakeHandler([json.dumps(response, ensure_ascii=False)])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.final_chains[0].evidence_unit_ids == [
        "unit_56", "unit_57", "unit_58", "unit_59", "unit_60",
    ]
    assert catalog.final_chains[1].evidence_unit_ids == ["unit_75", "unit_76", "unit_77"]
    assert catalog.final_chains[2].evidence_unit_ids == ["unit_92", "unit_93", "unit_94"]
    assert catalog.repair_count == 0


def test_catalog_schema_constrains_each_evidence_item_to_one_bare_unit_id():
    units = _units()
    handler = FakeHandler([json.dumps(_catalog_response(units))])

    ContextEventReconciliationService(handler).build_catalog(units, [_extraction(units)])

    evidence_schema = handler.schemas[0][0]["$defs"]["EventChainDefinition"]["properties"][
        "evidence_unit_ids"
    ]
    assert evidence_schema["items"]["pattern"] == r"^unit_\d+$"


def test_catalog_still_repairs_a_real_unknown_unit_after_normalization():
    units = _units()
    invalid = _catalog_response(units)
    invalid["final_chains"][0]["evidence_unit_ids"] = ["unit_0以及unit_999。"]
    handler = FakeHandler([json.dumps(invalid), json.dumps(_catalog_response(units))])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert catalog.repair_reason == "contract_validation"
    assert "unit_999" in catalog.repair_detail


def test_catalog_malformed_non_string_evidence_uses_normal_schema_repair():
    units = _units()
    invalid = _catalog_response(units)
    invalid["final_chains"][0]["evidence_unit_ids"] = [{"id": "unit_0"}]
    handler = FakeHandler([json.dumps(invalid), json.dumps(_catalog_response(units))])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert catalog.repair_reason == "schema_validation"


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


def test_parent_story_promotion_requires_parent_identity():
    units = _units()
    invalid = _catalog_response(units)
    invalid["proposal_resolutions"][0]["resolution"] = "promote_to_parent_story"
    handler = FakeHandler([
        json.dumps(invalid),
        json.dumps(_catalog_response(units)),
    ])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert "conflict with their final_chain_ids" in handler.calls[1][-1]["content"]


def test_disposition_resolution_normalizes_redundant_target_fields():
    delivery = LocalChainDisposition(
        proposal_id="delivery",
        resolution="merge_into",
        final_chain_ids=["quest_one"],
        parent_story_id="toxic_story",
    )
    parent = LocalChainDisposition(
        proposal_id="parent",
        resolution="promote_to_parent_story",
        final_chain_ids=["quest_one", "quest_two"],
        parent_story_id="toxic_story",
    )
    rejected = LocalChainDisposition(
        proposal_id="rejected",
        resolution="reject_non_event",
        final_chain_ids=["quest_one"],
        parent_story_id="toxic_story",
    )

    assert delivery.final_chain_ids == ["quest_one"]
    assert delivery.parent_story_id is None
    assert parent.final_chain_ids == []
    assert parent.parent_story_id == "toxic_story"
    assert rejected.final_chain_ids == []
    assert rejected.parent_story_id is None


@pytest.mark.parametrize(("resolution", "final_chain_ids"), [
    ("merge_into", []),
    ("keep_as_delivery_chain", ["knight_returns", "knight_returns"]),
    ("split_across", ["knight_returns"]),
])
def test_unsafe_delivery_cardinality_still_requires_repair(
    resolution, final_chain_ids,
):
    units = _units()
    invalid = _catalog_response(units)
    invalid["proposal_resolutions"][0].update(
        resolution=resolution,
        final_chain_ids=final_chain_ids,
    )
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


def test_parent_story_is_hierarchical_only_and_cannot_receive_assignments():
    units = _units()
    response = _catalog_response(units)
    base = response["final_chains"][0]
    response["final_chains"] = [
        {**base, "chain_id": "quest_one", "parent_story_id": "toxic_story"},
        {**base, "chain_id": "quest_two", "parent_story_id": "toxic_story"},
    ]
    response["parent_stories"] = [{
        "story_id": "toxic_story",
        "summary": "Several bounded knight quests form one origin story.",
        "child_chain_ids": ["quest_one", "quest_two"],
        "evidence_unit_ids": [units[0].unit_id],
    }]
    response["proposal_resolutions"][0].update(
        resolution="promote_to_parent_story",
        final_chain_ids=[],
        parent_story_id="toxic_story",
    )
    # Child delivery chains still need a local proposal source. Reuse the one
    # folded card through a split disposition and add a second broad card for
    # the parent-story promotion.
    extraction = _extraction(units)
    broad = EventChainContribution(
        chain_id="all-knight-quests",
        event="The order pursues its overall origin story.",
        sequence=0,
        evidence=[SourceEvidence(source_item_id="source-0")],
    )
    extraction.events.append(broad)
    response["proposal_resolutions"] = [
        {
            "proposal_id": "b0_c0",
            "resolution": "split_across",
            "final_chain_ids": ["quest_one", "quest_two"],
        },
        {
            "proposal_id": "b0_c1",
            "resolution": "promote_to_parent_story",
            "final_chain_ids": [],
            "parent_story_id": "toxic_story",
        },
    ]
    assignment = _assignment_response(units)
    assignment["assignments"][0]["links"][0]["event_chain_id"] = "toxic_story"
    valid_assignment = _assignment_response(units)
    for item in valid_assignment["assignments"]:
        for link in item["links"]:
            link["event_chain_id"] = "quest_one"
    valid_assignment["assignments"][0]["links"].append({
        "event_chain_id": "quest_two",
        "relation": "primary_member",
        "confidence": 0.96,
    })
    handler = FakeHandler([
        json.dumps(response),
        json.dumps(assignment),
        json.dumps(valid_assignment),
    ])
    service = ContextEventReconciliationService(handler)
    catalog = service.build_catalog(units, [extraction])

    assert [story.story_id for story in catalog.parent_stories] == ["toxic_story"]
    assert {chain.chain_id for chain in catalog.final_chains} == {"quest_one", "quest_two"}
    result = service.assign_batch(units, catalog)
    assert result.repair_count == 1
    assert "unknown chains" in handler.calls[2][-1]["content"]


def test_parent_story_can_be_grounded_by_child_chains_without_a_promotion_card():
    units = _units(2)
    response = _catalog_response(units)
    base = response["final_chains"][0]
    response["final_chains"] = [
        {
            **base,
            "chain_id": "quest_one",
            "parent_story_id": "toxic_story",
            "anchor_unit_ids": [units[0].unit_id],
            "evidence_unit_ids": [units[0].unit_id],
        },
        {
            **base,
            "chain_id": "quest_two",
            "parent_story_id": "toxic_story",
            "anchor_unit_ids": [units[1].unit_id],
            "evidence_unit_ids": [units[1].unit_id],
        },
    ]
    response["parent_stories"] = [{
        "story_id": "toxic_story",
        "summary": "Two bounded quests belong to one origin story.",
        "child_chain_ids": ["quest_one", "quest_two"],
        "evidence_unit_ids": [units[0].unit_id, units[1].unit_id],
    }]
    response["proposal_resolutions"] = [
        {
            "proposal_id": "b0_c0",
            "resolution": "split_across",
            "final_chain_ids": ["quest_one", "quest_two"],
            "parent_story_id": "toxic_story",
        },
    ]
    handler = FakeHandler([json.dumps(response)])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 0
    assert catalog.proposal_resolutions[0].parent_story_id is None
    assert [story.story_id for story in catalog.parent_stories] == ["toxic_story"]


def test_grounded_event_evidence_can_anchor_when_sparse_primary_hint_is_omitted():
    units = _units(3)
    extraction = _extraction(units)
    extraction.delivery_assignments = extraction.delivery_assignments[:1]
    response = _catalog_response(units)
    response["final_chains"][0]["anchor_unit_ids"] = [units[1].unit_id]
    handler = FakeHandler([json.dumps(response)])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [extraction]
    )

    assert catalog.repair_count == 0
    assert catalog.final_chains[0].anchor_unit_ids == [units[1].unit_id]
    assert catalog.local_chain_cards[0]["primary_unit_ids"] == [units[0].unit_id]
    assert units[1].unit_id in catalog.local_chain_cards[0]["evidence_unit_ids"]


def test_anchor_cannot_use_unrelated_valid_unit_outside_card_sources():
    units = _units(3)
    invalid = _catalog_response(units)
    invalid["final_chains"][0]["anchor_unit_ids"] = [units[2].unit_id]
    handler = FakeHandler([
        json.dumps(invalid),
        json.dumps(_catalog_response(units)),
    ])

    catalog = ContextEventReconciliationService(handler).build_catalog(
        units, [_extraction(units)]
    )

    assert catalog.repair_count == 1
    assert "primary hints or grounded event evidence" in handler.calls[1][-1]["content"]


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
        "boundary_includes": "The related established scene only.",
        "boundary_excludes": "The hunted knight's return and unrelated scenes.",
        "anchor_unit_ids": [units[1].unit_id],
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
