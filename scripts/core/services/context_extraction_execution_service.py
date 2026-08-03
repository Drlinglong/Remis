"""Concurrent, checkpointed execution for context extraction batches."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from scripts.core.neologism_extraction import AnalysisScope, StructuredNeologismExtraction
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_parallel_execution_service import map_context_calls_ordered


class ContextExtractionExecutionService:
    """Run independent extraction calls and persist each completion immediately."""

    def __init__(
        self,
        *,
        handler_factory: Callable[..., Any],
        miner_factory: Callable[[Any], Any],
        checkpoints: Any,
        status_service: Any,
        usage_ledger: Any | None = None,
    ) -> None:
        self.handler_factory = handler_factory
        self.miner_factory = miner_factory
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
    ) -> list[StructuredNeologismExtraction]:
        results: list[StructuredNeologismExtraction | None] = [None] * len(chunks)
        pending = self._restore_completed(
            chunks, results, project_id, task_id, analysis_run,
        )

        def worker(item: tuple[int, ContextUnitChunk]) -> StructuredNeologismExtraction:
            _, chunk = item
            handler = self.handler_factory(api_provider, model_name=model_name)
            miner = self.miner_factory(handler)
            try:
                return miner.extract_structured(
                    list(chunk.source_items),
                    scope=scope,
                    game_name=game_name,
                    target_language=target_language,
                    reasoning_language=reasoning_language,
                    core_units=chunk.core_units,
                    edge_units=chunk.edge_units,
                )
            finally:
                if self.usage_ledger is not None:
                    self.usage_ledger.capture(handler, "extraction")

        def record_completion(outcome: Any) -> None:
            index, chunk = outcome.item
            source_ids = [item.source_item_id for item in chunk.source_items]
            if outcome.error is not None:
                self.checkpoints.save_extraction_failure(
                    analysis_run, index, source_ids, outcome.error,
                )
                self._record_batch(
                    project_id, task_id, index, source_ids,
                    success=False, error=str(outcome.error),
                )
                return
            if outcome.value is None:
                return
            self.checkpoints.save_extraction(
                analysis_run, index, chunk.source_items, outcome.value,
            )
            self._record_batch(
                project_id, task_id, index, source_ids, success=True,
            )

        outcomes = map_context_calls_ordered(
            pending,
            worker,
            max_workers=concurrency,
            on_completed=record_completion,
        )
        for outcome in outcomes:
            if outcome.succeeded and outcome.value is not None:
                index, _ = outcome.item
                results[index] = outcome.value
        errors = [outcome.error for outcome in outcomes if outcome.error is not None]
        if errors:
            raise errors[0]
        return [result for result in results if result is not None]

    def _restore_completed(
        self,
        chunks: Sequence[ContextUnitChunk],
        results: list[StructuredNeologismExtraction | None],
        project_id: str,
        task_id: str | None,
        analysis_run: Any | None,
    ) -> list[tuple[int, ContextUnitChunk]]:
        pending = []
        for index, chunk in enumerate(chunks):
            source_ids = [item.source_item_id for item in chunk.source_items]
            restored = self.checkpoints.restore_extraction(
                analysis_run, index, source_ids,
            )
            if restored is None:
                pending.append((index, chunk))
                continue
            results[index] = restored
            self._record_batch(
                project_id, task_id, index, source_ids, success=True, resumed=True,
            )
        return pending

    def _record_batch(
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
            project_id, task_id, "extracting", f"extracting:{index + 1}",
            success=success, source_item_ids=source_item_ids,
            resumed=resumed, error=error,
        )
