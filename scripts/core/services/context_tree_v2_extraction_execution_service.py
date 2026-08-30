"""Concurrent, checkpointed execution for context tree v2 extraction."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from scripts.core.neologism_extraction import AnalysisScope
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_parallel_execution_service import (
    ContextParallelResult,
    map_context_calls_ordered,
)
from scripts.core.services.context_tree_v2_contract import ContextTreeV2Extraction
from scripts.core.services.context_tree_v2_extraction_service import (
    ContextTreeV2ExtractionService,
)
from scripts.core.services.provider_runtime import (
    ProviderRuntimeSnapshot,
    handler_from_runtime,
)


class ContextTreeV2ExtractionExecutionService:
    """Run independent v2 extraction batches without losing stable ordering."""

    def __init__(
        self,
        *,
        handler_factory: Callable[..., Any],
        checkpoints: Any,
        status_service: Any,
        usage_ledger: Any,
    ) -> None:
        self.handler_factory = handler_factory
        self.checkpoints = checkpoints
        self.status_service = status_service
        self.usage_ledger = usage_ledger

    def execute(
        self,
        chunks: Sequence[ContextUnitChunk],
        *,
        scope: AnalysisScope,
        game_name: str,
        project_id: str,
        task_id: str | None,
        target_language: str,
        reasoning_language: str,
        analysis_run: Any | None,
        api_provider: str,
        model_name: str | None,
        concurrency: int,
        runtime: ProviderRuntimeSnapshot | None = None,
    ) -> tuple[ContextTreeV2Extraction, ...]:
        self.status_service.begin_stage(
            project_id, task_id, "extracting", len(chunks),
        )
        results: list[ContextTreeV2Extraction | None] = [None] * len(chunks)
        pending = self._restore_completed(
            chunks, results, project_id, task_id, analysis_run,
        )

        def worker(item: tuple[int, ContextUnitChunk]) -> ContextTreeV2Extraction:
            _, chunk = item
            handler = self._handler(api_provider, model_name, runtime)
            try:
                return ContextTreeV2ExtractionService(handler).extract_structured(
                    list(chunk.source_items),
                    scope=scope,
                    game_name=game_name,
                    target_language=target_language,
                    reasoning_language=reasoning_language,
                    core_units=chunk.core_units,
                    edge_units=chunk.edge_units,
                    chunk_edge_metadata=chunk.edge_metadata,
                )
            finally:
                self.usage_ledger.capture(handler, "tree_v2_extraction")

        outcomes = map_context_calls_ordered(
            pending,
            worker,
            max_workers=concurrency,
            on_completed=lambda outcome: self._record_completion(
                outcome, results, project_id, task_id, analysis_run,
            ),
        )
        errors = [outcome.error for outcome in outcomes if outcome.error is not None]
        if errors:
            raise errors[0]
        if any(result is None for result in results):
            raise RuntimeError("Context tree v2 extraction produced an incomplete batch set")
        self.status_service.complete_stage(project_id, task_id, "extracting")
        return tuple(result for result in results if result is not None)

    def _handler(
        self,
        api_provider: str,
        model_name: str | None,
        runtime: ProviderRuntimeSnapshot | None,
    ) -> Any:
        if runtime is None:
            return self.handler_factory(api_provider, model_name=model_name)
        return handler_from_runtime(runtime, self.handler_factory)

    def _restore_completed(
        self,
        chunks: Sequence[ContextUnitChunk],
        results: list[ContextTreeV2Extraction | None],
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
    ) -> list[tuple[int, ContextUnitChunk]]:
        pending = []
        for index, chunk in enumerate(chunks):
            source_ids = self._source_ids(chunk)
            restored = self.checkpoints.restore_extraction(
                analysis_run, index, source_ids,
            )
            if restored is None:
                pending.append((index, chunk))
                continue
            results[index] = restored
            self._record_status(
                project_id, task_id, index, source_ids,
                success=True, resumed=True,
            )
        return pending

    def _record_completion(
        self,
        outcome: ContextParallelResult[tuple[int, ContextUnitChunk], ContextTreeV2Extraction],
        results: list[ContextTreeV2Extraction | None],
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
    ) -> None:
        index, chunk = outcome.item
        source_ids = self._source_ids(chunk)
        if outcome.error is not None:
            self._record_status(
                project_id, task_id, index, source_ids,
                success=False, error=str(outcome.error),
            )
            return
        if outcome.value is None:
            return
        results[index] = outcome.value
        self.checkpoints.save_extraction(
            analysis_run, index, source_ids, outcome.value,
        )
        self._record_status(
            project_id, task_id, index, source_ids, success=True,
        )

    def _record_status(
        self,
        project_id: str,
        task_id: str | None,
        index: int,
        source_item_ids: list[str],
        *,
        success: bool,
        resumed: bool = False,
        error: str | None = None,
    ) -> None:
        self.status_service.record_batch(
            project_id,
            task_id,
            "extracting",
            f"tree-v2-extraction-{index}",
            success=success,
            source_item_ids=source_item_ids,
            resumed=resumed,
            error=error,
        )

    @staticmethod
    def _source_ids(chunk: ContextUnitChunk) -> list[str]:
        return [item.source_item_id for item in chunk.source_items]


__all__ = ["ContextTreeV2ExtractionExecutionService"]
