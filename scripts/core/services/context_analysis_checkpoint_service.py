"""Workflow-facing coordination for durable context-analysis batches."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.core.context_local_units import DeliveryAssignment

from scripts.core.neologism_extraction import (
    AnalysisScope,
    EventChainContribution,
    SourceItem,
    StructuredNeologismExtraction,
)
from scripts.core.services.context_event_reconciliation_service import EventReconciliationResult
from scripts.core.services.context_event_reconciliation_service import (
    EventAssignmentBatchResult,
    EventChainCatalogResult,
)
from scripts.schemas.context import GeneratedSynthesis


class _AggregationCheckpoint(BaseModel):
    """Durable global result, independent from per-chunk extraction limits."""

    model_config = ConfigDict(extra="forbid")

    events: list[EventChainContribution] = Field(default_factory=list, max_length=80)
    delivery_assignments: list[DeliveryAssignment] = Field(default_factory=list, max_length=500)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class _CatalogCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["event-catalog-v3"]
    catalog: EventChainCatalogResult


class _AssignmentCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["event-catalog-v3"]
    assignment_batch: EventAssignmentBatchResult


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

    def restore_aggregation(
        self,
        run: Any | None,
        source_item_ids: Sequence[str],
    ) -> EventReconciliationResult | None:
        if self.repository is None or run is None:
            return None
        saved = self.repository.get_batch(run.run_id, "aggregation", 0)
        if saved is None or saved.status != "succeeded":
            return None
        if tuple(source_item_ids) != saved.source_item_ids:
            raise ValueError("Saved aggregation does not match the current local units")
        payload = saved.payload.get("reconciliation") or saved.payload.get("extraction")
        if payload is None:
            return None
        checkpoint = _AggregationCheckpoint.model_validate(payload)
        return EventReconciliationResult(
            events=checkpoint.events,
            delivery_assignments=checkpoint.delivery_assignments,
            diagnostics=checkpoint.diagnostics,
        )

    def save_aggregation(
        self,
        run: Any | None,
        source_item_ids: Sequence[str],
        reconciliation: EventReconciliationResult,
    ) -> None:
        if self.repository is None or run is None:
            return
        checkpoint = _AggregationCheckpoint(
            events=reconciliation.events,
            delivery_assignments=reconciliation.delivery_assignments,
            diagnostics=reconciliation.diagnostics,
        )
        self.repository.save_batch(
            run.run_id,
            "aggregation",
            0,
            source_item_ids,
            {"reconciliation": checkpoint.model_dump()},
        )

    def restore_catalog(
        self,
        run: Any | None,
        source_item_ids: Sequence[str],
    ) -> EventChainCatalogResult | None:
        saved = self._successful_aggregation_batch(run, 0, source_item_ids)
        if saved is None or "catalog" not in saved.payload:
            return None
        try:
            return _CatalogCheckpoint.model_validate(saved.payload).catalog
        except ValidationError:
            return None

    def save_catalog(
        self,
        run: Any | None,
        source_item_ids: Sequence[str],
        catalog: EventChainCatalogResult,
    ) -> None:
        self._save_aggregation_batch(
            run,
            0,
            source_item_ids,
            _CatalogCheckpoint(
                contract_version="event-catalog-v3", catalog=catalog
            ).model_dump(),
        )

    def restore_assignment_batch(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
    ) -> EventAssignmentBatchResult | None:
        saved = self._successful_aggregation_batch(
            run, batch_index + 1, source_item_ids
        )
        if saved is None or "assignment_batch" not in saved.payload:
            return None
        try:
            return _AssignmentCheckpoint.model_validate(saved.payload).assignment_batch
        except ValidationError:
            return None

    def save_assignment_batch(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
        result: EventAssignmentBatchResult,
    ) -> None:
        self._save_aggregation_batch(
            run,
            batch_index + 1,
            source_item_ids,
            _AssignmentCheckpoint(
                contract_version="event-catalog-v3", assignment_batch=result
            ).model_dump(),
        )

    def save_aggregation_failure(
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
            "aggregation",
            batch_index,
            source_item_ids,
            {},
            status="failed",
            error={"type": type(error).__name__, "message": str(error)[:1500]},
        )

    def restore_synthesis(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
    ) -> list[GeneratedSynthesis] | None:
        if self.repository is None or run is None:
            return None
        saved = self.repository.get_batch(run.run_id, "synthesis", batch_index)
        if saved is None or saved.status != "succeeded":
            return None
        if tuple(source_item_ids) != saved.source_item_ids:
            raise ValueError("Saved synthesis batch does not match the current source items")
        return [
            GeneratedSynthesis.model_validate(item)
            for item in saved.payload.get("syntheses", [])
        ]

    def save_synthesis(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
        syntheses: Sequence[GeneratedSynthesis],
    ) -> None:
        if self.repository is None or run is None:
            return
        self.repository.save_batch(
            run.run_id,
            "synthesis",
            batch_index,
            source_item_ids,
            {"syntheses": [item.model_dump() for item in syntheses]},
        )

    def save_synthesis_failure(
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
            "synthesis",
            batch_index,
            source_item_ids,
            {},
            status="failed",
            error={"type": type(error).__name__, "message": str(error)[:1500]},
        )

    def _successful_aggregation_batch(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
    ) -> Any | None:
        if self.repository is None or run is None:
            return None
        saved = self.repository.get_batch(run.run_id, "aggregation", batch_index)
        if saved is None or saved.status != "succeeded":
            return None
        if tuple(source_item_ids) != saved.source_item_ids:
            raise ValueError("Saved aggregation batch does not match the current local units")
        return saved

    def _save_aggregation_batch(
        self,
        run: Any | None,
        batch_index: int,
        source_item_ids: Sequence[str],
        payload: Mapping[str, Any],
    ) -> None:
        if self.repository is None or run is None:
            return
        self.repository.save_batch(
            run.run_id,
            "aggregation",
            batch_index,
            source_item_ids,
            payload,
        )

    def mark_failed(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_failed(run.run_id)

    def mark_complete(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_complete(run.run_id)

    def mark_analysis_ready(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_analysis_ready(run.run_id)

    def mark_published(self, run: Any | None) -> None:
        if self.repository is not None and run is not None:
            self.repository.mark_published(run.run_id)
