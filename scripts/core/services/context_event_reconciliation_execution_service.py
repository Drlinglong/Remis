"""Checkpointed and concurrent execution of two-stage event reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import StructuredNeologismExtraction
from scripts.core.services.context_analysis_checkpoint_service import (
    ContextAnalysisCheckpointService,
)
from scripts.core.services.context_event_reconciliation_service import (
    ContextAssignmentBatchingPolicy,
    ContextEventReconciliationService,
    EventAssignmentBatchResult,
    EventChainCatalogResult,
    EventReconciliationResult,
)
from scripts.core.services.context_parallel_execution_service import (
    ContextParallelResult,
    map_context_calls_ordered,
)


@dataclass(frozen=True)
class _PendingAssignmentBatch:
    plan_index: int
    units: list[LocalTextUnit]


class ContextEventReconciliationExecutionService:
    """Coordinate catalog barrier, bounded assignments, and durable recovery."""

    def __init__(
        self,
        *,
        handler_factory: Callable[..., Any],
        reconciler_factory: Callable[[Any], Any],
        checkpoints: ContextAnalysisCheckpointService,
        status_service: Any,
        usage_ledger: Any | None = None,
    ) -> None:
        self.handler_factory = handler_factory
        self.reconciler_factory = reconciler_factory
        self.checkpoints = checkpoints
        self.status_service = status_service
        self.usage_ledger = usage_ledger

    def execute(
        self,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        *,
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
        api_provider: str,
        model_name: str | None,
        description_language: str,
        concurrency: int,
    ) -> EventReconciliationResult:
        units = list(local_units)
        assignment_batches = ContextAssignmentBatchingPolicy.batches(units)
        all_source_ids = self._source_ids(units)
        self.status_service.begin_stage(
            project_id,
            task_id,
            "aggregating",
            1 + len(assignment_batches),
            source_item_ids=all_source_ids,
        )
        catalog = self._catalog(
            units,
            extractions,
            project_id=project_id,
            task_id=task_id,
            analysis_run=analysis_run,
            api_provider=api_provider,
            model_name=model_name,
            description_language=description_language,
        )
        results = self._assignment_results(
            assignment_batches,
            catalog,
            project_id=project_id,
            task_id=task_id,
            analysis_run=analysis_run,
            api_provider=api_provider,
            model_name=model_name,
            description_language=description_language,
            concurrency=concurrency,
        )
        reconciled = ContextEventReconciliationService.finalize(
            units, catalog, results
        )
        self.status_service.complete_stage(
            project_id, task_id, "aggregating"
        )
        return reconciled

    def _catalog(
        self,
        units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        **context: Any,
    ) -> EventChainCatalogResult:
        source_ids = self._source_ids(units)
        saved = self.checkpoints.restore_catalog(context["analysis_run"], source_ids)
        if saved is not None:
            self._record(
                context, "aggregating:catalog", True, source_ids, resumed=True
            )
            return saved
        try:
            service = self._service(context["api_provider"], context["model_name"])
            try:
                catalog = service.build_catalog(
                    units,
                    extractions,
                    description_language=context["description_language"],
                )
            finally:
                if self.usage_ledger is not None:
                    self.usage_ledger.capture(getattr(service, "handler", None), "event_catalog")
            self.checkpoints.save_catalog(context["analysis_run"], source_ids, catalog)
        except Exception as error:
            self.checkpoints.save_aggregation_failure(
                context["analysis_run"], 0, source_ids, error
            )
            self._record(context, "aggregating:catalog", False, source_ids, error=error)
            raise
        self._record(context, "aggregating:catalog", True, source_ids)
        return catalog

    def _assignment_results(
        self,
        batches: Sequence[Sequence[LocalTextUnit]],
        catalog: EventChainCatalogResult,
        **context: Any,
    ) -> list[EventAssignmentBatchResult]:
        results: list[EventAssignmentBatchResult | None] = [None] * len(batches)
        pending: list[_PendingAssignmentBatch] = []
        for index, batch in enumerate(batches):
            source_ids = self._source_ids(batch)
            saved = self.checkpoints.restore_assignment_batch(
                context["analysis_run"], index, source_ids
            )
            if saved is None:
                pending.append(_PendingAssignmentBatch(index, list(batch)))
                continue
            results[index] = saved
            self._record(
                context,
                self._assignment_batch_id(index),
                True,
                source_ids,
                resumed=True,
            )

        def worker(item: _PendingAssignmentBatch) -> EventAssignmentBatchResult:
            service = self._service(context["api_provider"], context["model_name"])
            try:
                return service.assign_batch(
                    item.units,
                    catalog,
                    description_language=context["description_language"],
                )
            finally:
                if self.usage_ledger is not None:
                    self.usage_ledger.capture(getattr(service, "handler", None), "event_assignment")

        persistence_errors: list[BaseException] = []

        def completed(outcome: ContextParallelResult[Any, Any]) -> None:
            plan_index = outcome.item.plan_index
            source_ids = self._source_ids(outcome.item.units)
            try:
                if outcome.error is not None:
                    self.checkpoints.save_aggregation_failure(
                        context["analysis_run"], plan_index + 1, source_ids, outcome.error
                    )
                    self._record(
                        context,
                        self._assignment_batch_id(plan_index),
                        False,
                        source_ids,
                        error=outcome.error,
                    )
                    return
                self.checkpoints.save_assignment_batch(
                    context["analysis_run"], plan_index, source_ids, outcome.value
                )
                self._record(
                    context,
                    self._assignment_batch_id(plan_index),
                    True,
                    source_ids,
                )
                results[plan_index] = outcome.value
            except BaseException as persistence_error:
                persistence_errors.append(persistence_error)

        outcomes = map_context_calls_ordered(
            pending,
            worker,
            max_workers=context["concurrency"],
            on_completed=completed,
        )
        errors = [outcome.error for outcome in outcomes if outcome.error is not None]
        if errors:
            raise errors[0]
        if persistence_errors:
            raise persistence_errors[0]
        if any(result is None for result in results):
            raise RuntimeError("Event assignment barrier completed with missing batch results")
        return [result for result in results if result is not None]

    def _service(self, api_provider: str, model_name: str | None) -> Any:
        handler = self.handler_factory(api_provider, model_name=model_name)
        return self.reconciler_factory(handler)

    def _record(
        self,
        context: dict[str, Any],
        batch_id: str,
        success: bool,
        source_ids: list[str],
        *,
        resumed: bool = False,
        error: BaseException | None = None,
    ) -> None:
        self.status_service.record_batch(
            context["project_id"],
            context["task_id"],
            "aggregating",
            batch_id,
            success=success,
            source_item_ids=source_ids,
            resumed=resumed,
            error=str(error) if error is not None else None,
        )

    @staticmethod
    def _source_ids(units: Sequence[LocalTextUnit]) -> list[str]:
        return [str(item.source_item_id) for unit in units for item in unit.items]

    @staticmethod
    def _assignment_batch_id(index: int) -> str:
        return f"aggregating:assignment:{index + 1}"
