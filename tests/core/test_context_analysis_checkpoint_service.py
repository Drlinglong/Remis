from types import SimpleNamespace

from scripts.core.context_local_units import DeliveryAssignment
from scripts.core.neologism_extraction import EventChainContribution, SourceEvidence
from scripts.core.services.context_analysis_checkpoint_service import (
    ContextAnalysisCheckpointService,
)
from scripts.core.services.context_event_reconciliation_service import EventReconciliationResult


class _Repository:
    def __init__(self):
        self.saved = None

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

    def get_batch(self, run_id, phase, batch_index):
        if self.saved is None:
            return None
        assert (run_id, phase, batch_index) == (
            self.saved.run_id,
            self.saved.phase,
            self.saved.batch_index,
        )
        return self.saved


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
