from types import SimpleNamespace

from scripts.core.context_local_units import DeliveryAssignment
from scripts.core.neologism_extraction import EventChainContribution, SourceEvidence
from scripts.core.services.context_analysis_checkpoint_service import (
    ContextAnalysisCheckpointService,
)
from scripts.core.services.context_event_reconciliation_service import (
    EventAssignmentBatchResult,
    EventChainCatalogResult,
    EventChainDefinition,
    EventReconciliationResult,
    LocalChainDisposition,
    ParentStoryDefinition,
)
from scripts.schemas.context import GeneratedSynthesis


class _Repository:
    def __init__(self):
        self.saved = None
        self.batches = {}

    def save_batch(
        self,
        run_id,
        phase,
        batch_index,
        source_item_ids,
        payload,
    ):
        self.saved = SimpleNamespace(
            run_id=run_id,
            phase=phase,
            batch_index=batch_index,
            source_item_ids=tuple(source_item_ids),
            payload=payload,
            status="succeeded",
        )
        self.batches[(run_id, phase, batch_index)] = self.saved

    def get_batch(self, run_id, phase, batch_index):
        return self.batches.get((run_id, phase, batch_index))


def _reconciliation(assignment_count=95, event_count=55):
    evidence = [SourceEvidence(source_item_id="source-0")]
    return EventReconciliationResult(
        events=[
            EventChainContribution(
                chain_id=f"chain-{index}",
                event=f"Event {index}",
                sequence=index,
                evidence=evidence,
            )
            for index in range(event_count)
        ],
        delivery_assignments=[
            DeliveryAssignment(
                local_unit_id=f"unit_{index}",
                assignment_state="unassigned",
                source_item_ids=[f"source-{index}"],
            )
            for index in range(assignment_count)
        ],
        diagnostics={"repair_count": 0},
    )


def test_global_aggregation_checkpoint_is_not_limited_by_local_extraction_batch():
    repository = _Repository()
    service = ContextAnalysisCheckpointService(repository)
    run = SimpleNamespace(run_id="run-1")
    source_ids = [f"source-{index}" for index in range(95)]

    service.save_aggregation(run, source_ids, _reconciliation())
    restored = service.restore_aggregation(run, source_ids)

    assert "reconciliation" in repository.saved.payload
    assert len(restored.events) == 55
    assert len(restored.delivery_assignments) == 95
    assert restored.diagnostics == {"repair_count": 0}


def test_catalog_and_assignment_batches_have_independent_checkpoint_slots():
    repository = _Repository()
    service = ContextAnalysisCheckpointService(repository)
    run = SimpleNamespace(run_id="run-1")
    catalog = EventChainCatalogResult(
        parent_stories=[ParentStoryDefinition(
            story_id="story-1",
            story_scope="parent_story",
            summary="One surviving child after deterministic ownership normalization.",
            child_chain_ids=["chain-1"],
            evidence_unit_ids=["unit_0"],
        )],
        final_chains=[EventChainDefinition(
            chain_id="chain-1",
            story_scope="concrete_child_quest",
            parent_story_id="story-1",
            event="A bounded chain.",
            sequence=0,
            evidence_unit_ids=["unit_0"],
        )],
        proposal_resolutions=[LocalChainDisposition(
            proposal_id="b0_c0",
            resolution="merge_into",
            final_chain_ids=["chain-1"],
        )],
        local_chain_cards=[{"proposal_id": "b0_c0"}],
    )
    assignment = EventAssignmentBatchResult(assignments=[DeliveryAssignment(
        local_unit_id="unit_0",
        assignment_state="unassigned",
        source_item_ids=["source-0"],
    )])

    service.save_catalog(run, ["source-0", "source-1"], catalog)
    service.save_assignment_batch(run, 0, ["source-0"], assignment)

    assert service.restore_catalog(run, ["source-0", "source-1"]) == catalog
    assert service.restore_assignment_batch(run, 0, ["source-0"]) == assignment
    assert set(repository.batches) == {
        ("run-1", "aggregation", 0),
        ("run-1", "aggregation", 1),
    }


def test_legacy_event_catalog_checkpoints_are_not_resumed():
    repository = _Repository()
    service = ContextAnalysisCheckpointService(repository)
    run = SimpleNamespace(run_id="run-1")
    repository.save_batch(
        run.run_id,
        "aggregation",
        0,
        ["source-0"],
        {"catalog": {"final_chains": [], "proposal_resolutions": []}},
    )
    repository.save_batch(
        run.run_id,
        "aggregation",
        1,
        ["source-0"],
        {"assignment_batch": {"assignments": []}},
    )

    assert service.restore_catalog(run, ["source-0"]) is None
    assert service.restore_assignment_batch(run, 0, ["source-0"]) is None


def test_synthesis_batch_round_trips_without_another_model_call():
    repository = _Repository()
    service = ContextAnalysisCheckpointService(repository)
    run = SimpleNamespace(run_id="run-1")
    syntheses = [GeneratedSynthesis(
        synthesis_id="synthesis-1",
        aggregate_id="aggregate-1",
        context_key="entity:republic",
        content={"summary": "A durable summary."},
    )]

    service.save_synthesis(run, 0, ["source-1"], syntheses)
    restored = service.restore_synthesis(run, 0, ["source-1"])

    assert restored == syntheses
    assert repository.saved.phase == "synthesis"
