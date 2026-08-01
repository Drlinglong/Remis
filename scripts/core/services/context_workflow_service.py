"""Bounded backend orchestration for neologism and Mod Context analysis."""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Any, Callable, Iterable, Sequence

from scripts.core.api_handler import get_handler
from scripts.core.context_service import ContextService
from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceItem,
    StructuredNeologismExtraction,
)
from scripts.core.neologism_manager import neologism_manager
from scripts.core.neologism_miner import NeologismMiner
from scripts.core.services.context_candidate_adapter import ContextCandidateAdapter
from scripts.core.services.context_source_parser import ContextSourceParser, ParsedSourceFile
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.context_workflow_status_service import ContextWorkflowStatusService
from scripts.core.services.source_snapshot_service import (
    SourceItemIdentity,
    SourceItemSnapshot,
    SourceSnapshot,
    SourceSnapshotService,
    SourceChangeKind,
)
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextRelease,
    ContextReleaseMetadata,
    ContextSourceItem,
)
from scripts.shared import task_state


class ContextWorkflowService:
    """Own the maintained scan workflow while keeping domain ports injectable."""

    CHUNK_SIZE = 16
    REVIEW_BATCH_SIZE = ContextCandidateAdapter.REVIEW_BATCH_SIZE
    SCHEMA_VERSION = "context-v1"
    PROMPT_VERSION = "context-synthesis-v2"
    ACTIVE_STATUSES = ContextWorkflowStatusService.ACTIVE_STATUSES

    def __init__(
        self,
        repository: Any,
        *,
        handler_factory: Callable[..., Any] = get_handler,
        candidate_store: Any = neologism_manager,
        task_backend: Any = task_state,
        source_parser: ContextSourceParser | None = None,
        snapshot_service: SourceSnapshotService | None = None,
        miner_factory: Callable[[Any], Any] = NeologismMiner,
        synthesizer_factory: Callable[[Any], Any] = ContextSynthesisService,
        context_service: ContextService | None = None,
        candidate_adapter: ContextCandidateAdapter | None = None,
        status_service: ContextWorkflowStatusService | None = None,
    ):
        self.repository = repository
        self.context_service = context_service or ContextService(repository)
        self.handler_factory = handler_factory
        self.candidate_store = candidate_store
        self.task_backend = task_backend
        self.candidate_adapter = candidate_adapter or ContextCandidateAdapter(candidate_store)
        self.status_service = status_service or ContextWorkflowStatusService(task_backend)
        self.source_parser = source_parser or ContextSourceParser()
        self.snapshot_service = snapshot_service or SourceSnapshotService()
        self.miner_factory = miner_factory
        self.synthesizer_factory = synthesizer_factory

    def reserve(self, project_id: str, task_id: str, scope: AnalysisScope) -> bool:
        return self.status_service.reserve(project_id, task_id, scope)

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return ContextWorkflowStatusService._idle_status()

    def release_reservation(self, project_id: str, task_id: str) -> None:
        self.status_service.release_reservation(project_id, task_id)

    def get_status(self, project_id: str) -> dict[str, Any]:
        return self.status_service.get_status(project_id)

    def run(
        self,
        project_id: str,
        file_paths: Sequence[str],
        source_root: str,
        api_provider: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-CN",
        game_name: str = "Paradox Game",
        task_id: str | None = None,
        duplicate_index: dict[str, list[dict[str, Any]]] | None = None,
        model_name: str | None = None,
        review_language: str = "en",
        analysis_scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        upstream_version: str | None = None,
        analysis_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = AnalysisScope(analysis_scope)
        parsed_files: tuple[ParsedSourceFile, ...] = ()
        processed_files = 0
        try:
            parsed_files = self.source_parser.parse_files(file_paths, source_root)
            snapshot = self.source_parser.build_snapshot(parsed_files, self.snapshot_service)
            parent = self._latest_release(project_id) if scope is AnalysisScope.NARRATIVE_CONTEXT else None
            diff = self._source_diff(parent, snapshot)
            self._running(project_id, task_id, scope, parsed_files, snapshot, diff)
            handler = self.handler_factory(api_provider, model_name=model_name)
            miner = self.miner_factory(handler)
            extractions = self._extract(miner, parsed_files, scope, game_name, task_id)
            terms_result = self._finish_terms_only(
                project_id, parsed_files, extractions, miner, duplicate_index or {},
                source_lang, target_lang, game_name, review_language,
            )
            if scope is AnalysisScope.TERMS_ONLY:
                result = terms_result
            else:
                self._task_update(
                    task_id,
                    progress={"stage": "Synthesizing"},
                    fields={"stage_code": "synthesizing"},
                    push=True,
                )
                result = self._finish_context(
                    project_id, parsed_files, snapshot, diff, parent, extractions,
                    handler, api_provider, model_name, upstream_version, analysis_config,
                )
                result.update({"new_terms": terms_result["new_terms"], "duplicate_terms": terms_result["duplicate_terms"]})
            self._complete(project_id, task_id, result, len(parsed_files))
            return result
        except Exception as exc:
            self._failed(project_id, task_id, len(parsed_files), processed_files, exc)
            raise

    def _extract(
        self,
        miner: Any,
        parsed_files: Sequence[ParsedSourceFile],
        scope: AnalysisScope,
        game_name: str,
        task_id: str | None,
    ) -> list[StructuredNeologismExtraction]:
        chunks = list(self._chunks(item for source_file in parsed_files for item in source_file.items))
        results: list[StructuredNeologismExtraction] = []
        for index, chunk in enumerate(chunks, start=1):
            results.append(miner.extract_structured(list(chunk), scope=scope, game_name=game_name))
            self._task_update(
                task_id,
                progress={"current_batch": index, "total_batches": len(chunks), "stage": "Extracting"},
                fields={"stage_code": "extracting"},
                push=False,
            )
        return results

    def _finish_terms_only(
        self,
        project_id: str,
        parsed_files: Sequence[ParsedSourceFile],
        extractions: Sequence[StructuredNeologismExtraction],
        miner: Any,
        duplicate_index: dict[str, list[dict[str, Any]]],
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
    ) -> dict[str, Any]:
        return self.candidate_adapter.process_terms(
            project_id,
            parsed_files,
            extractions,
            miner,
            duplicate_index,
            source_lang,
            target_lang,
            game_name,
            review_language,
        )

    def _finish_context(
        self,
        project_id: str,
        parsed_files: Sequence[ParsedSourceFile],
        snapshot: SourceSnapshot,
        diff: Any,
        parent: ContextRelease | None,
        extractions: Sequence[StructuredNeologismExtraction],
        handler: Any,
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        sources = self._persist_sources(project_id, parsed_files, snapshot.source_snapshot_hash)
        contributions = self._persist_contributions(extractions, sources)
        if not contributions:
            return {
                "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
                "new_terms": 0,
                "context_release_id": None,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "affected_source_items": self._affected_items(diff),
            }
        aggregates = self._build_aggregates(project_id, contributions)
        for aggregate in aggregates:
            self.repository.save_aggregate(aggregate)
        syntheses = self.synthesizer_factory(handler).synthesize(aggregates, contributions, sources)
        metadata = self._metadata(
            snapshot, parsed_files, diff, parent, api_provider, model_name,
            upstream_version, analysis_config,
        )
        draft = self.context_service.start_draft(project_id, parent.release_id if parent else None)
        release = self.context_service.publish_draft(
            draft.draft_id, metadata, [item.aggregate_id for item in aggregates], syntheses
        )
        return {
            "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
            "new_terms": 0,
            "context_release_id": release.release_id,
            "source_snapshot_hash": snapshot.source_snapshot_hash,
            "affected_source_items": self._affected_items(diff),
            "parent_release_id": parent.release_id if parent else None,
        }

    def _persist_sources(
        self, project_id: str, parsed_files: Sequence[ParsedSourceFile], snapshot_hash: str
    ) -> dict[str, ContextSourceItem]:
        sources: dict[str, ContextSourceItem] = {}
        for source_file in parsed_files:
            for item in source_file.items:
                source = ContextSourceItem(
                    source_item_id=item.source_item_id,
                    project_id=project_id,
                    source_type="localization",
                    source_ref=f"{item.relative_path}::{item.source_order}:{item.item_key or ''}",
                    content=item.source_text,
                    content_hash=hashlib.sha256(item.source_text.encode("utf-8")).hexdigest(),
                    metadata={
                        "relative_path": item.relative_path,
                        "item_key": item.item_key,
                        "source_order": item.source_order,
                        "source_snapshot_hash": snapshot_hash,
                    },
                )
                existing = self.repository.get_source_item(source.source_item_id)
                sources[source.source_item_id] = existing or self.repository.create_source_item(source)
        return sources

    def _persist_contributions(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        sources: dict[str, ContextSourceItem],
    ) -> dict[str, ContextContribution]:
        contributions: dict[str, ContextContribution] = {}
        for extraction in extractions:
            for item in self._all_contributions(extraction):
                evidence = [entry.model_dump() for entry in item.evidence]
                source_item_id = evidence[0]["source_item_id"]
                if source_item_id not in sources:
                    raise ValueError("Extraction evidence referenced a source outside the parsed snapshot")
                contribution = ContextContribution(
                    contribution_id=str(uuid.uuid4()),
                    source_item_id=source_item_id,
                    contribution_type=self._contribution_type(item),
                    subject_key=self._subject_key(item),
                    payload={**item.model_dump(), "evidence": evidence},
                    provenance="text_inferred",
                )
                self.repository.create_contribution(contribution)
                contributions[contribution.contribution_id] = contribution
        return contributions

    @staticmethod
    def _all_contributions(extraction: StructuredNeologismExtraction) -> list[Any]:
        return [
            *extraction.terms, *extraction.entities, *extraction.facts,
            *extraction.events, *extraction.relationships,
        ]

    @staticmethod
    def _contribution_type(item: Any) -> str:
        name = item.__class__.__name__
        return {"TermContribution": "mention", "EntityContribution": "mention", "FactContribution": "fact",
                "EventChainContribution": "event", "RelationshipContribution": "relationship"}[name]

    @staticmethod
    def _subject_key(item: Any) -> str:
        if item.__class__.__name__ == "EventChainContribution":
            return f"event:{item.chain_id.strip().casefold()}"
        value = getattr(item, "original", None) or getattr(item, "name", None) or getattr(item, "subject", None)
        return f"entity:{str(value).strip().casefold()}"

    def _build_aggregates(
        self, project_id: str, contributions: dict[str, ContextContribution]
    ) -> list[ContextAggregate]:
        groups: dict[str, list[str]] = defaultdict(list)
        for contribution in contributions.values():
            groups[contribution.subject_key].append(contribution.contribution_id)
        groups["project:summary"] = list(contributions)
        aggregates = []
        for aggregate_key, contribution_ids in sorted(groups.items()):
            aggregate_type = "project" if aggregate_key == "project:summary" else (
                "event" if aggregate_key.startswith("event:") else "entity"
            )
            aggregate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:{project_id}:{aggregate_key}"))
            aggregates.append(ContextAggregate(
                aggregate_id=aggregate_id,
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_key=aggregate_key,
                payload={"active_contribution_count": len(contribution_ids)},
                contribution_ids=contribution_ids,
            ))
        return aggregates

    def _metadata(
        self,
        snapshot: SourceSnapshot,
        parsed_files: Sequence[ParsedSourceFile],
        diff: Any,
        parent: ContextRelease | None,
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
    ) -> ContextReleaseMetadata:
        config = dict(analysis_config or {})
        config.update({
            "reuse_strategy": "full_reextract",
            "source_items": [
                {
                    "relative_path": item.identity.relative_path,
                    "item_key": item.identity.item_key,
                    "source_order": item.identity.source_order,
                    "source_sha256": item.source_sha256,
                }
                for item in snapshot.items
            ],
            "affected_source_items": self._affected_items(diff),
        })
        return ContextReleaseMetadata(
            source_snapshot_hash=snapshot.source_snapshot_hash,
            analysis_scope={
                "mode": AnalysisScope.NARRATIVE_CONTEXT.value,
                "files": [item.relative_path for item in parsed_files],
            },
            schema_version=self.SCHEMA_VERSION,
            prompt_version=self.PROMPT_VERSION,
            provider_id=api_provider,
            model_id=model_name or f"{api_provider}-default",
            analysis_config=config,
            parent_release_id=parent.release_id if parent else None,
            upstream_version=upstream_version,
        )

    @staticmethod
    def _source_diff(parent: ContextRelease | None, current: SourceSnapshot) -> Any:
        if not parent:
            return current.diff(None)
        previous_items = tuple(
            SourceItemSnapshot(
                identity=SourceItemIdentity(
                    item["relative_path"], item.get("item_key"), item.get("source_order")
                ),
                source_sha256=item["source_sha256"],
            )
            for item in parent.metadata.analysis_config.get("source_items", [])
        )
        previous = SourceSnapshot(files=(), source_snapshot_hash=parent.metadata.source_snapshot_hash, items=previous_items)
        return current.diff(previous)

    @staticmethod
    def _affected_items(diff: Any) -> list[dict[str, str]]:
        return [
            {"relative_path": item.identity.relative_path, "item_key": item.identity.item_key or "", "kind": item.kind.value}
            for item in diff.item_changes
            if item.kind is not SourceChangeKind.UNCHANGED
        ]

    def _latest_release(self, project_id: str) -> ContextRelease | None:
        releases = self.repository.list_releases(project_id)
        return releases[0] if releases else None

    @staticmethod
    def _chunks(items: Iterable[SourceItem]) -> Iterable[tuple[SourceItem, ...]]:
        current: list[SourceItem] = []
        for item in items:
            current.append(item)
            if len(current) >= ContextWorkflowService.CHUNK_SIZE:
                yield tuple(current)
                current = []
        if current:
            yield tuple(current)

    def _running(
        self, project_id: str, task_id: str | None, scope: AnalysisScope,
        parsed_files: Sequence[ParsedSourceFile], snapshot: SourceSnapshot, diff: Any,
    ) -> None:
        self.status_service.mark_running(
            project_id,
            task_id,
            scope,
            len(parsed_files),
            snapshot.source_snapshot_hash,
            self._affected_items(diff),
        )

    def _complete(self, project_id: str, task_id: str | None, result: dict[str, Any], total_files: int) -> None:
        self.status_service.mark_completed(project_id, task_id, result, total_files)

    def _failed(self, project_id: str, task_id: str | None, total_files: int, processed_files: int, error: Exception) -> None:
        self.status_service.mark_failed(project_id, task_id, total_files, processed_files, error)

    def _set_status(self, project_id: str, **updates: Any) -> None:
        self.status_service.set_status(project_id, **updates)

    def _task_update(self, task_id: str | None, **updates: Any) -> None:
        self.status_service.update_task(task_id, **updates)
