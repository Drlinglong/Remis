"""Workflow-facing coordination for durable context-analysis batches."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceItem,
    StructuredNeologismExtraction,
)


class ContextAnalysisCheckpointService:
    """Keep SQLite checkpoint mechanics out of the main workflow orchestrator."""

    def __init__(self, repository: Any | None):
        self.repository = repository

    def start(
        self,
        project_id: str,
        task_id: str | None,
        source_snapshot_hash: str,
        scope: AnalysisScope,
        config: Mapping[str, Any],
    ) -> Any | None:
        if self.repository is None:
            return None
        return self.repository.start_or_resume_run(
            project_id,
            task_id,
            source_snapshot_hash,
            {"mode": AnalysisScope(scope).value},
            dict(config),
        )

    def restore_extraction(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
    ) -> StructuredNeologismExtraction | None:
        if self.repository is None or run is None:
            return None
        saved = self.repository.get_batch(run.run_id, "extraction", batch_index)
        if saved is None or saved.status != "succeeded":
            return None
        if tuple(source_item_ids) != saved.source_item_ids:
            raise ValueError("Saved extraction batch does not match the current source items")
        return StructuredNeologismExtraction.model_validate(saved.payload["extraction"])

    def save_extraction(
        self,
        run: Any | None,
        batch_index: int,
        source_items: Sequence[SourceItem],
        extraction: StructuredNeologismExtraction,
    ) -> None:
        if self.repository is None or run is None:
            return
        self.repository.save_batch(
            run.run_id,
            "extraction",
            batch_index,
            [item.source_item_id for item in source_items],
            {
                "extraction": extraction.model_dump(),
                "source_items": [item.model_dump() for item in source_items],
            },
        )

    def save_extraction_failure(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
        error: Exception,
    ) -> None:
        if self.repository is None or run is None:
            return
        self.repository.save_batch(
            run.run_id,
            "extraction",
            batch_index,
            source_item_ids,
            {"extraction": {}},
            status="failed",
            error={"type": type(error).__name__, "message": str(error)[:1000]},
        )

    def mark_failed(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_failed(run.run_id)

    def mark_published(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_published(run.run_id)
