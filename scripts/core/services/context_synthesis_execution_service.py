"""Checkpointed parallel execution for context archive synthesis batches."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from scripts.core.services.context_model_usage import ContextModelUsageLedger
from scripts.core.services.context_parallel_execution_service import (
    map_context_calls_ordered,
)
from scripts.core.services.provider_runtime import (
    ProviderRuntimeSnapshot,
    handler_from_runtime,
)


class ContextSynthesisExecutionService:
    """Plan, restore, execute, and persist archive synthesis batches."""

    def __init__(
        self,
        *,
        handler_factory: Callable[..., Any],
        synthesizer_factory: Callable[[Any], Any],
        checkpoints: Any,
        status_service: Any,
        release_assembler: Any,
        governance_flow: Any,
        usage_ledger: ContextModelUsageLedger,
    ) -> None:
        self.handler_factory = handler_factory
        self.synthesizer_factory = synthesizer_factory
        self.checkpoints = checkpoints
        self.status_service = status_service
        self.release_assembler = release_assembler
        self.governance_flow = governance_flow
        self.usage_ledger = usage_ledger

    def execute(
        self,
        aggregates: Sequence[Any],
        contributions: dict[str, Any],
        sources: dict[str, Any],
        governance: Any,
        description_language: str,
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
        api_provider: str,
        model_name: str | None,
        concurrency: int,
        source_item_ids: Sequence[str],
        runtime: ProviderRuntimeSnapshot | None = None,
    ) -> list[Any]:
        synthesizer = self.synthesizer_factory(
            self._handler(api_provider, model_name, runtime)
        )
        eligible = self.governance_flow.synthesis_eligible_aggregates(
            aggregates, governance,
        )
        batches = synthesizer.plan_batches(
            eligible, contributions, sources, description_language,
        )
        self.status_service.begin_stage(
            project_id, task_id, "synthesizing", len(batches),
            source_item_ids=source_item_ids,
        )
        return self.execute_batches(
            batches, contributions, sources, description_language,
            project_id, task_id, analysis_run, api_provider, model_name, concurrency,
            runtime=runtime,
        )

    def execute_batches(
        self,
        batches: Sequence[Sequence[Any]],
        contributions: dict[str, Any],
        sources: dict[str, Any],
        description_language: str,
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
        api_provider: str,
        model_name: str | None,
        concurrency: int,
        runtime: ProviderRuntimeSnapshot | None = None,
    ) -> list[Any]:
        indexed_batches = list(enumerate([list(batch) for batch in batches]))

        def worker(indexed_batch: tuple[int, list[Any]]) -> list[Any]:
            batch_index, batch = indexed_batch
            source_ids = self.release_assembler.aggregate_source_ids(
                batch, contributions,
            )
            restored = self.checkpoints.restore_synthesis(
                analysis_run, batch_index, source_ids,
            )
            if restored is not None:
                return restored
            handler = self._handler(api_provider, model_name, runtime)
            synthesizer = self.synthesizer_factory(handler)
            try:
                generated = synthesizer.synthesize(
                    batch, contributions, sources, description_language,
                    planned_batches=[batch],
                )
                self.checkpoints.save_synthesis(
                    analysis_run, batch_index, source_ids, generated,
                )
                return generated
            except Exception as exc:
                self.checkpoints.save_synthesis_failure(
                    analysis_run, batch_index, source_ids, exc,
                )
                raise
            finally:
                self.usage_ledger.capture(handler, "synthesis")

        def record_completion(outcome: Any) -> None:
            _, batch = outcome.item
            source_ids = self.release_assembler.aggregate_source_ids(
                batch, contributions,
            )
            self.status_service.record_batch(
                project_id, task_id, "synthesizing",
                f"synthesizing:{outcome.index + 1}",
                success=outcome.succeeded,
                source_item_ids=source_ids,
                error=str(outcome.error) if outcome.error else None,
            )

        outcomes = map_context_calls_ordered(
            indexed_batches,
            worker,
            max_workers=concurrency,
            on_completed=record_completion,
        )
        errors = [outcome.error for outcome in outcomes if outcome.error is not None]
        if errors:
            raise errors[0]
        return [item for outcome in outcomes for item in (outcome.value or [])]

    def _handler(
        self,
        api_provider: str,
        model_name: str | None,
        runtime: ProviderRuntimeSnapshot | None,
    ) -> Any:
        if runtime is None:
            return self.handler_factory(api_provider, model_name=model_name)
        return handler_from_runtime(runtime, self.handler_factory)
