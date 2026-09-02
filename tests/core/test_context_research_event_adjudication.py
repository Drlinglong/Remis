from types import SimpleNamespace

import pytest

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_chain_consolidation import consolidate_event_steps
from scripts.core.services.context_research_compiler import (
    ContextResearchFindings,
    ContextResearchDraftCompiler,
)
from scripts.core.services.context_research_contract import (
    ContextAnalysisRequest,
    EvidenceReference,
    EventChain,
)
from scripts.core.services.context_research_event_adjudication import (
    apply_event_chain_adjudications,
    build_event_adjudication_packet,
    event_adjudication_prompt,
)
from scripts.core.services.context_research_harness_run import (
    ContextResearchRunCoordinator,
    DelegationTracker,
)
from scripts.core.services.context_research_lead_decisions import (
    EventChainAdjudicationResult,
)


def _units(branch=False):
    return tuple(
        LocalTextUnit(
            unit_id=f"unit_{index}",
            unit_key=f"events/demo.yml::{('branch_a' if index == 0 else 'branch_b') if branch else 'crisis'}.{index + 1}",
            items=(SourceItem(
                source_item_id=f"source-{index}",
                relative_path="events/demo.yml",
                item_key=f"{('branch_a' if index == 0 else 'branch_b') if branch else 'crisis'}.{index + 1}.desc",
                source_order=index,
                source_text=(
                    f"The crisis chooses branch A. Step {index + 1}." if branch
                    else f"The crisis continues at step {index + 1}."
                ),
            ),),
        )
        for index in range(2)
    )


def _events(entity="entity-crisis"):
    return (
        EventChain(
            chain_id="fragment-a", sequence=0, event="The crisis begins.",
            local_unit_ids=("unit_0",), entity_ids=(entity,), source_item_ids=("source-0",),
            evidence=(EvidenceReference(source_item_ids=("source-0",)),),
        ),
        EventChain(
            chain_id="fragment-b", sequence=1, event="The crisis continues.",
            local_unit_ids=("unit_1",), entity_ids=(entity,), source_item_ids=("source-1",),
            evidence=(EvidenceReference(source_item_ids=("source-1",)),),
        ),
    )


def test_packet_contains_both_chain_units_and_filters_hard_negative_edges():
    events = _events()
    _, diagnostics = consolidate_event_steps(events, _units())
    packet = build_event_adjudication_packet(events, _units(), diagnostics)

    assert packet["candidate_count"] == 1
    assert packet["eligible_candidate_count"] == 1
    edge = packet["eligible_edges"][0]
    assert edge["event_a"]["units"][0]["items"][0]["source_item_id"] == "source-0"
    assert edge["event_b"]["units"][0]["items"][0]["source_item_id"] == "source-1"
    assert edge["deterministic"]["positive_signals"] == [
        "adjacent_local_units", "narrative_continuity", "shared_entities",
    ]

    branch_events = _events()
    _, branch_diagnostics = consolidate_event_steps(branch_events, _units(branch=True))
    branch_packet = build_event_adjudication_packet(
        branch_events, _units(branch=True), branch_diagnostics,
    )
    assert branch_packet["eligible_candidate_count"] == 0
    assert branch_packet["hard_rejected_candidate_count"] == 1


def test_compiler_applies_one_valid_batch_decision_without_collapsing_steps():
    events = _events()
    _, consolidation = consolidate_event_steps(events, _units())
    packet = build_event_adjudication_packet(events, _units(), consolidation)
    edge = packet["eligible_edges"][0]
    result = EventChainAdjudicationResult.model_validate({
        "decisions": [{
            "candidate_id": edge["candidate_id"],
            "decision": "merge",
            "evidence_source_item_ids": ["source-0", "source-1"],
            "positive_signals": edge["deterministic"]["positive_signals"],
            "reason": "same crisis and adjacent steps",
        }],
    })

    merged, diagnostics = apply_event_chain_adjudications(
        events, result, packet, _units(),
    )

    assert [(event.chain_id, event.sequence) for event in merged] == [
        ("fragment-a", 0), ("fragment-a", 1),
    ]
    assert diagnostics["accepted_edge_count"] == 1
    assert diagnostics["canonical_chain_groups"][0]["preserved_event_count"] == 2


def test_compiler_rejects_unverifiable_lead_evidence_and_keeps_split():
    events = _events()
    _, consolidation = consolidate_event_steps(events, _units())
    packet = build_event_adjudication_packet(events, _units(), consolidation)
    edge = packet["eligible_edges"][0]
    result = {
        "decisions": [{
            "candidate_id": edge["candidate_id"],
            "decision": "merge",
            "evidence_source_item_ids": ["source-0", "invented-source"],
            "positive_signals": edge["deterministic"]["positive_signals"],
        }],
    }

    merged, diagnostics = apply_event_chain_adjudications(
        events, result, packet, _units(),
    )

    assert [event.chain_id for event in merged] == ["fragment-a", "fragment-b"]
    assert diagnostics["rejected_edges"] == [{
        "candidate_id": edge["candidate_id"],
        "reason": "lead_evidence_source_not_on_candidate_edge",
    }]


def test_prompt_is_one_batch_and_does_not_include_universal_context():
    packet = {
        "eligible_edges": [{"candidate_id": "event-merge-edge-001"}],
    }
    prompt = event_adjudication_prompt(packet, "zh-CN")
    assert "one decision for every eligible candidate_id" in prompt
    assert "universal_translation_context" not in prompt


@pytest.mark.asyncio
async def test_coordinator_runs_adjudication_before_repairs_and_persists_diagnostic():
    request = ContextAnalysisRequest(
        project_id="demo",
        source_items=tuple(SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/demo.yml",
            item_key=f"demo.{index + 1}.desc",
            source_order=index,
            source_text=f"The crisis step {index + 1} continues.",
        ) for index in range(2)),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": f"fragment-{index}",
            "sequence": index,
            "event": f"The crisis step {index + 1} continues.",
            "local_unit_ids": [f"unit_{index}"],
            "evidence": [{"source_item_ids": [f"source-{index}"]}],
        } for index in range(2)],
    })

    class Events:
        def emit(self, event, payload):
            del event, payload

    class Usage:
        def record(self, event, **metadata):
            del event, metadata

    class Agent:
        model = SimpleNamespace(model_name="lead-test")

    class InitialResult:
        output = findings

        def usage(self):
            return {"requests": 1}

        def new_messages(self):
            return []

    calls = []

    async def run_adjudication(prompt):
        calls.append(prompt)
        return SimpleNamespace(
            output=EventChainAdjudicationResult.model_validate({
                "decisions": [{
                    "candidate_id": "event-merge-edge-001",
                    "decision": "merge",
                    "evidence_source_item_ids": ["source-0", "source-1"],
                    "positive_signals": [
                        "adjacent_local_units", "narrative_continuity",
                    ],
                }],
            }),
            usage=lambda: {"requests": 1},
            new_messages=lambda: [],
        )

    context = SimpleNamespace(events=Events(), usage=Usage())
    draft = await ContextResearchRunCoordinator(
        ContextResearchDraftCompiler(), max_repair_attempts=0,
    ).finalize(
        initial_result=InitialResult(),
        agent=Agent(),
        bound_tools=SimpleNamespace(id_registry=None, local_units=request.local_units),
        tracker=DelegationTracker(Events()),
        request=request,
        execution_context=context,
        run_lead=lambda *args, **kwargs: None,
        run_adjudication=run_adjudication,
    )

    assert len(calls) == 1
    assert [event.chain_id for event in draft.event_chains] == ["fragment-0", "fragment-0"]
    assert draft.diagnostics["compiler"]["adjudication"]["accepted_edge_count"] == 1
