import threading
import time
from types import SimpleNamespace

import pytest

from scripts.core.context_local_units import ContextLocalUnitBuilder, DeliveryAssignment, DeliveryLink
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_event_reconciliation_execution_service import (
    ContextEventReconciliationExecutionService,
)
from scripts.core.services.context_event_reconciliation_service import (
    EventAssignmentBatchResult,
    EventChainCatalogResult,
    EventChainDefinition,
)


class FakeCheckpoints:
    def __init__(self):
        self.catalog = None
        self.assignments = {}
        self.failures = []

    def restore_catalog(self, run, source_ids):
        del run, source_ids
        return self.catalog

    def save_catalog(self, run, source_ids, catalog):
        del run, source_ids
        self.catalog = catalog

    def restore_assignment_batch(self, run, index, source_ids):
        del run, source_ids
        return self.assignments.get(index)

    def save_assignment_batch(self, run, index, source_ids, result):
        del run, source_ids
        self.assignments[index] = result

    def save_aggregation_failure(self, run, index, source_ids, error):
        del run, source_ids
        self.failures.append((index, error))


class FakeStatus:
    def __init__(self):
        self.stage = None
        self.records = []

    def begin_stage(self, project_id, task_id, stage, total, *, source_item_ids):
        self.stage = (project_id, task_id, stage, total, source_item_ids)

    def record_batch(self, project_id, task_id, stage, batch_id, **fields):
        self.records.append((project_id, task_id, stage, batch_id, fields))

    def complete_stage(self, project_id, task_id, stage):
        self.completed = (project_id, task_id, stage)


class ConcurrentFakeReconciler:
    lock = threading.Lock()
    active = 0
    max_active = 0

    def __init__(self, handler):
        del handler

    def build_catalog(self, units, extractions, *, description_language):
        del extractions, description_language
        return EventChainCatalogResult(final_chains=[EventChainDefinition(
            chain_id="chain",
            event="A chain.",
            sequence=0,
            evidence_unit_ids=[units[0].unit_id],
        )])

    def assign_batch(self, units, catalog, *, description_language):
        del catalog, description_language
        with self.lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        time.sleep(0.02)
        with self.lock:
            type(self).active -= 1
        return EventAssignmentBatchResult(assignments=[
            DeliveryAssignment(
                local_unit_id=unit.unit_id,
                assignment_state="assigned" if unit.unit_id == "unit_0" else "unassigned",
                links=[DeliveryLink(
                    event_chain_id="chain",
                    relation="primary_member",
                    confidence=1.0,
                )] if unit.unit_id == "unit_0" else [],
                source_item_ids=[item.source_item_id for item in unit.items],
            )
            for unit in units
        ])


class FailOnceFakeReconciler(ConcurrentFakeReconciler):
    failed = False

    def assign_batch(self, units, catalog, *, description_language):
        if units[0].unit_id == "unit_40" and not type(self).failed:
            type(self).failed = True
            raise RuntimeError("bounded assignment failed")
        return super().assign_batch(
            units, catalog, description_language=description_language
        )


def _units(count):
    return ContextLocalUnitBuilder.build([
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="localisation/main.yml",
            item_key=f"story.{index}.title",
            source_order=index,
            source_text=f"Text {index}",
        )
        for index in range(count)
    ])


def test_execution_uses_catalog_barrier_parallel_assignment_batches_and_resume():
    ConcurrentFakeReconciler.active = 0
    ConcurrentFakeReconciler.max_active = 0
    checkpoints = FakeCheckpoints()
    status = FakeStatus()
    handler_calls = []
    executor = ContextEventReconciliationExecutionService(
        handler_factory=lambda provider, model_name=None: handler_calls.append(
            (provider, model_name)
        ),
        reconciler_factory=ConcurrentFakeReconciler,
        checkpoints=checkpoints,
        status_service=status,
    )
    units = _units(95)
    context = dict(
        project_id="project",
        task_id="task",
        analysis_run=SimpleNamespace(run_id="run"),
        api_provider="openrouter",
        model_name="openai/gpt-5.6-luna",
        description_language="zh-CN",
        concurrency=5,
    )

    first = executor.execute(units, [], **context)

    assert status.stage[3] == 4
    assert len(first.delivery_assignments) == 95
    assert status.completed == ("project", "task", "aggregating")
    assert set(checkpoints.assignments) == {0, 1, 2}
    assert ConcurrentFakeReconciler.max_active > 1
    assert status.records[0][3] == "aggregating:catalog"
    assert {record[3] for record in status.records[1:]} == {
        "aggregating:assignment:1",
        "aggregating:assignment:2",
        "aggregating:assignment:3",
    }
    assert len(handler_calls) == 4

    status.records.clear()
    second = executor.execute(units, [], **context)

    assert len(second.delivery_assignments) == 95
    assert len(handler_calls) == 4
    assert all(record[4]["resumed"] for record in status.records)


def test_retry_reuses_successful_assignment_batches_and_only_reruns_failure():
    FailOnceFakeReconciler.failed = False
    checkpoints = FakeCheckpoints()
    status = FakeStatus()
    handler_calls = []
    executor = ContextEventReconciliationExecutionService(
        handler_factory=lambda provider, model_name=None: handler_calls.append(
            (provider, model_name)
        ),
        reconciler_factory=FailOnceFakeReconciler,
        checkpoints=checkpoints,
        status_service=status,
    )
    units = _units(95)
    context = dict(
        project_id="project",
        task_id="task",
        analysis_run=SimpleNamespace(run_id="run"),
        api_provider="openrouter",
        model_name="openai/gpt-5.6-luna",
        description_language="zh-CN",
        concurrency=5,
    )

    with pytest.raises(RuntimeError, match="bounded assignment failed"):
        executor.execute(units, [], **context)

    assert set(checkpoints.assignments) == {0, 2}
    assert checkpoints.failures[0][0] == 2
    assert len(handler_calls) == 4

    result = executor.execute(units, [], **context)

    assert len(result.delivery_assignments) == 95
    assert len(handler_calls) == 5
    resumed = {
        record[3] for record in status.records if record[4].get("resumed")
    }
    assert resumed >= {
        "aggregating:catalog",
        "aggregating:assignment:1",
        "aggregating:assignment:3",
    }
