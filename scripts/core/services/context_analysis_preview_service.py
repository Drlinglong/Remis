"""Build a bounded, read-only preview from the latest persisted analysis run."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from scripts.core.repositories.context_analysis_batch_repository import (
    ContextAnalysisBatch,
    ContextAnalysisBatchRepository,
    ContextAnalysisRun,
)
from scripts.core.repositories.context_repository import ContextRepository
from scripts.schemas.context import ContextAggregate
from scripts.schemas.context_analysis_preview import (
    ContextAnalysisPreview,
    ContextAnalysisPreviewEntry,
    ContextAnalysisPreviewRun,
)


class ContextAnalysisPreviewService:
    """Expose persisted candidates and chains without creating a release."""

    def __init__(
        self,
        repository: ContextRepository,
        batch_repository: ContextAnalysisBatchRepository,
    ) -> None:
        self.repository = repository
        self.batch_repository = batch_repository

    def latest(self, project_id: str) -> ContextAnalysisPreview | None:
        aggregates = self.repository.list_aggregates(project_id)
        if not aggregates:
            return None
        run = self._latest_previewable_run(project_id)
        if run is None:
            return None
        batches = self.batch_repository.list_batches(run.run_id)
        summaries = self._summaries(batches)
        event_catalog = self._event_catalog(batches)
        event_coverage = self._event_coverage(batches)
        entries = self._entries(aggregates, summaries, event_catalog, event_coverage)
        if not entries:
            return None
        return ContextAnalysisPreview(
            project_id=project_id,
            run=self._run_preview(run),
            counts=self._counts(entries, summaries),
            entries=entries,
        )

    def _latest_previewable_run(self, project_id: str) -> ContextAnalysisRun | None:
        for run in self.batch_repository.list_runs(project_id):
            aggregation_ready = any(
                batch.status == "succeeded"
                for batch in self.batch_repository.list_batches(run.run_id, "aggregation")
            )
            synthesis_ready = any(
                batch.status == "succeeded"
                for batch in self.batch_repository.list_batches(run.run_id, "synthesis")
            )
            if aggregation_ready and synthesis_ready:
                return run
        return None

    @staticmethod
    def _run_preview(run: ContextAnalysisRun) -> ContextAnalysisPreviewRun:
        config = run.config
        return ContextAnalysisPreviewRun(
            run_id=run.run_id,
            project_id=run.project_id,
            task_id=run.task_id,
            status=run.status,
            phase=run.phase,
            publication_status=run.publication_status,
            source_snapshot_hash=run.source_snapshot_hash,
            analysis_scope=run.analysis_scope,
            provider_id=_optional_text(config.get("provider")),
            model_id=_optional_text(config.get("model")),
            prompt_version=_optional_text(config.get("prompt_version")),
            schema_version=_optional_text(config.get("schema_version")),
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _summaries(batches: Iterable[ContextAnalysisBatch]) -> dict[str, dict[str, Any]]:
        summaries: dict[str, dict[str, Any]] = {}
        for batch in batches:
            if batch.phase != "synthesis" or batch.status != "succeeded":
                continue
            for synthesis in batch.payload.get("syntheses", []):
                aggregate_id = _optional_text(synthesis.get("aggregate_id"))
                content = synthesis.get("content")
                if aggregate_id and isinstance(content, dict):
                    summaries[aggregate_id] = content
        return summaries

    @staticmethod
    def _event_catalog(batches: Iterable[ContextAnalysisBatch]) -> dict[str, dict[str, Any]]:
        for batch in batches:
            if batch.phase != "aggregation" or batch.status != "succeeded":
                continue
            catalog = batch.payload.get("catalog")
            if not isinstance(catalog, dict):
                continue
            return {
                str(chain["chain_id"]): dict(chain)
                for chain in catalog.get("final_chains", [])
                if isinstance(chain, dict) and chain.get("chain_id")
            }
        return {}

    @staticmethod
    def _event_coverage(
        batches: Iterable[ContextAnalysisBatch],
    ) -> dict[str, dict[str, int]]:
        units: dict[str, set[str]] = defaultdict(set)
        roles: dict[str, Counter[str]] = defaultdict(Counter)
        for batch in batches:
            if batch.phase != "aggregation" or batch.status != "succeeded":
                continue
            assignment_batch = batch.payload.get("assignment_batch")
            if not isinstance(assignment_batch, dict):
                continue
            for assignment in assignment_batch.get("assignments", []):
                unit_id = _optional_text(assignment.get("local_unit_id"))
                if not unit_id:
                    continue
                for link in assignment.get("links", []):
                    chain_id = _optional_text(link.get("event_chain_id"))
                    relation = _optional_text(link.get("relation"))
                    if not chain_id:
                        continue
                    units[chain_id].add(unit_id)
                    if relation:
                        roles[chain_id][relation] += 1
        return {
            chain_id: {
                "local_unit_coverage": len(unit_ids),
                "primary_member": roles[chain_id]["primary_member"],
                "supporting_context": roles[chain_id]["supporting_context"],
                "theme_related": roles[chain_id]["theme_related"],
            }
            for chain_id, unit_ids in units.items()
        }

    @classmethod
    def _entries(
        cls,
        aggregates: Iterable[ContextAggregate],
        summaries: dict[str, dict[str, Any]],
        event_catalog: dict[str, dict[str, Any]],
        event_coverage: dict[str, dict[str, int]],
    ) -> list[ContextAnalysisPreviewEntry]:
        entries: list[ContextAnalysisPreviewEntry] = []
        for aggregate in aggregates:
            if aggregate.aggregate_type not in {"entity", "event"}:
                continue
            payload = dict(aggregate.payload)
            if aggregate.aggregate_type == "entity":
                label = (
                    _optional_text(payload.get("canonical_display_name"))
                    or aggregate.aggregate_key.removeprefix("entity:")
                )
            else:
                chain_id = aggregate.aggregate_key.removeprefix("event:")
                if chain_id not in event_catalog:
                    continue
                payload.update(event_catalog[chain_id])
                payload["delivery_coverage"] = event_coverage.get(
                    chain_id,
                    {
                        "local_unit_coverage": 0,
                        "primary_member": 0,
                        "supporting_context": 0,
                        "theme_related": 0,
                    },
                )
                label = chain_id
            content = summaries.get(aggregate.aggregate_id, {})
            evidence_ids = content.get("evidence_source_item_ids", [])
            entries.append(ContextAnalysisPreviewEntry(
                aggregate_id=aggregate.aggregate_id,
                aggregate_key=aggregate.aggregate_key,
                aggregate_type=aggregate.aggregate_type,
                label=label,
                payload=payload,
                summary=_optional_text(content.get("summary")),
                summary_evidence_source_item_ids=[
                    str(item) for item in evidence_ids if item
                ] if isinstance(evidence_ids, list) else [],
            ))
        return sorted(
            entries,
            key=lambda item: (0 if item.aggregate_type == "event" else 1, item.label.casefold()),
        )

    @staticmethod
    def _counts(
        entries: Iterable[ContextAnalysisPreviewEntry],
        summaries: dict[str, dict[str, Any]],
    ) -> dict[str, int]:
        materialized = list(entries)
        entity_entries = [item for item in materialized if item.aggregate_type == "entity"]
        event_entries = [item for item in materialized if item.aggregate_type == "event"]
        tiers = Counter(str(item.payload.get("tier") or "not_recorded") for item in entity_entries)
        return {
            "entities": len(entity_entries),
            "events": len(event_entries),
            "syntheses": len(summaries),
            "entity_summaries": sum(item.summary is not None for item in entity_entries),
            "event_summaries": sum(item.summary is not None for item in event_entries),
            "core": tiers["core"],
            "secondary": tiers["secondary"],
            "incidental": tiers["incidental"],
            "not_recorded": tiers["not_recorded"],
            "audit_only": sum(bool(item.payload.get("audit_only")) for item in entity_entries),
        }


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
