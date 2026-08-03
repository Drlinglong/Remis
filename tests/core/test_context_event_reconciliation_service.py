import json

import pytest

from scripts.core.context_local_units import (
    ContextLocalUnitBuilder,
    DeliveryAssignment,
    DeliveryLink,
)
from scripts.core.neologism_extraction import (
    EventChainContribution,
    NeologismMiningError,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
)
from scripts.core.services.context_event_reconciliation_service import (
    ContextEventReconciliationService,
)


class FakeHandler:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.schemas = []

    def generate_structured_with_messages(self, messages, *, schema, schema_name, temperature=0.0):
        self.calls.append(messages)
        self.schemas.append((schema, schema_name))
        return next(self.responses)


def _units():
    source_items = [
        SourceItem(
            source_item_id="source-1", relative_path="localisation/a.yml",
            item_key="story.10.title", source_order=0, source_text="A knight asks for help.",
        ),
        SourceItem(
            source_item_id="source-2", relative_path="localisation/a.yml",
            item_key="story.10.desc", source_order=1, source_text="The Trickster is hunting the knight.",
        ),
        SourceItem(
            source_item_id="source-3", relative_path="localisation/a.yml",
            item_key="story.11.title", source_order=2, source_text="The knight returns victorious.",
        ),
        SourceItem(
            source_item_id="source-4", relative_path="localisation/a.yml",
            item_key="story.12.title", source_order=3, source_text="A separate council debate begins.",
        ),
    ]
    return ContextLocalUnitBuilder.build(source_items)


def _extraction(units):
    return StructuredNeologismExtraction(
        events=[EventChainContribution(
            chain_id="local-knight", event="A knight seeks aid.", sequence=0,
            evidence=[SourceEvidence(source_item_id="source-1")],
        )],
        delivery_assignments=[
            DeliveryAssignment(
                local_unit_id=units[0].unit_id, assignment_state="assigned",
                links=[DeliveryLink(
                    event_chain_id="local-knight", relation="primary_member", confidence=0.9,
                )],
            ),
            DeliveryAssignment(
                local_unit_id=units[1].unit_id, assignment_state="assigned",
                links=[DeliveryLink(
                    event_chain_id="local-knight", relation="primary_member", confidence=0.9,
                )],
            ),
        ],
    )


def _valid_response(units):
    return json.dumps({
        "final_chains": [{
            "chain_id": "knight_returns", "event": "A hunted knight seeks aid and returns.",
            "sequence": 0, "participants": ["knight", "Trickster"],
            "consequence": "The knight survives.", "evidence_unit_ids": [units[0].unit_id],
        }],
        "assignments": [
            {
                "local_unit_id": units[0].unit_id, "assignment_state": "assigned",
                "links": [{"event_chain_id": "knight_returns", "relation": "primary_member", "confidence": 0.97, "reasoning": "The plea begins the scene."}],
            },
            {
                "local_unit_id": units[1].unit_id, "assignment_state": "assigned",
                "links": [{"event_chain_id": "knight_returns", "relation": "primary_member", "confidence": 0.98, "reasoning": "It names the pursuit."}],
            },
            {"local_unit_id": units[2].unit_id, "assignment_state": "unassigned", "links": []},
        ],
        "proposal_resolutions": [{
            "proposal_id": "b0_e0",
            "resolution": "merge_into",
            "final_chain_ids": ["knight_returns"],
        }],
    })


def test_reconciliation_returns_final_events_and_expands_all_unit_source_ids():
    units = _units()
    handler = FakeHandler([_valid_response(units)])

    result = ContextEventReconciliationService(handler).reconcile(
        units, [_extraction(units)], description_language="zh-cn",
    )

    assert [event.chain_id for event in result.events] == ["knight_returns"]
    assert result.events[0].evidence[0].source_item_id == "source-1"
    assert [item.local_unit_id for item in result.delivery_assignments] == [
        unit.unit_id for unit in units
    ]
    assert result.delivery_assignments[0].source_item_ids == ["source-1", "source-2"]
    assert result.delivery_assignments[1].source_item_ids == ["source-3"]
    assert result.delivery_assignments[2].source_item_ids == ["source-4"]
    assert result.diagnostics["repair_count"] == 0
    assert result.diagnostics["proposal_resolutions"][0]["proposal_id"] == "b0_e0"
    schema = handler.schemas[0][0]
    assert "source_item_ids" not in schema["$defs"]["_ModelAssignment"]["properties"]
    request = json.loads(handler.calls[0][-1]["content"])
    assert request["description_language"] == "zh-cn"
    assert request["local_event_proposals"][0]["primary_unit_ids"] == [units[0].unit_id, units[1].unit_id]


@pytest.mark.parametrize("mutate, expected", [
    (lambda data: data["assignments"].pop(), "missing="),
    (lambda data: data["assignments"].append(data["assignments"][0]), "duplicate="),
    (lambda data: data["assignments"][0]["links"][0].update(event_chain_id="unknown"), "unknown chains"),
    (lambda data: data["final_chains"][0].update(evidence_unit_ids=["unit_2"]), "Evidence units"),
])
def test_invalid_membership_contract_is_repaired_once(mutate, expected):
    units = _units()
    invalid = json.loads(_valid_response(units))
    mutate(invalid)
    handler = FakeHandler([json.dumps(invalid), _valid_response(units)])

    result = ContextEventReconciliationService(handler).reconcile(units, [_extraction(units)])

    assert len(result.delivery_assignments) == len(units)
    assert len(handler.calls) == 2
    assert expected in handler.calls[1][-1]["content"]


def test_invalid_assignment_after_one_repair_fails_with_a_stable_error():
    units = _units()
    invalid = json.loads(_valid_response(units))
    invalid["assignments"].pop()
    handler = FakeHandler([json.dumps(invalid), json.dumps(invalid)])

    with pytest.raises(NeologismMiningError, match=r"after one repair \(assignment_coverage\)"):
        ContextEventReconciliationService(handler).reconcile(units, [_extraction(units)])

    assert len(handler.calls) == 2


def test_assigned_unassigned_invariants_are_repaired_once():
    units = _units()
    invalid = json.loads(_valid_response(units))
    invalid["assignments"][0]["assignment_state"] = "unassigned"
    handler = FakeHandler([json.dumps(invalid), _valid_response(units)])

    ContextEventReconciliationService(handler).reconcile(units, [_extraction(units)])

    assert len(handler.calls) == 2
    assert "Unassigned local units must have no delivery links" in handler.calls[1][-1]["content"]
