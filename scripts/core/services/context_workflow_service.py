"""Bounded backend orchestration for neologism and Mod Context analysis."""

from __future__ import annotations

from typing import Any, Callable, Sequence

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
from scripts.core.services.context_analysis_checkpoint_service import (
    ContextAnalysisCheckpointService,
)
from scripts.core.services.context_chunking_policy import ContextChunkingPolicy
from scripts.core.services.context_delivery_membership_service import (
    ContextDeliveryMembershipService,
)
from scripts.core.services.context_release_assembler import ContextReleaseAssembler
from scripts.core.services.context_source_parser import ContextSourceParser, ParsedSourceFile
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.context_workflow_status_service import ContextWorkflowStatusService
from scripts.core.services.source_snapshot_service import (
    SourceItemIdentity,
    SourceItemSnapshot,
    SourceSnapshot,
    SourceSnapshotService,
)
from scripts.schemas.context import ContextRelease
from scripts.shared import task_state


class _ReviewProgressMiner:
    """Keep candidate-adapter review calls observable without changing its API."""

    def __init__(self, miner: Any, on_batch: Callable[..., None]):
        self._miner = miner
        self._on_batch = on_batch
        self._batch_number = 0

    @property
    def batch_count(self) -> int:
        return self._batch_number

    def review_terms(self, candidates: Sequence[dict[str, Any]], **kwargs: Any) -> Any:
        self._batch_number += 1
        batch_id = f"reviewing:{self._batch_number}"
        try:
            result = self._miner.review_terms(candidates, **kwargs)
        except Exception as exc:
            self._on_batch(
                batch_id,
                success=False,
                conflict_review_count=len(candidates),
                error=str(exc),
            )
            raise
        self._on_batch(
            batch_id,
            success=True,
            conflict_review_count=len(candidates),
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._miner, name)


class ContextWorkflowService:
    """Own the maintained scan workflow while keeping domain ports injectable."""

    DEFAULT_MAX_ITEMS = ContextChunkingPolicy.DEFAULT_MAX_ITEMS
    MAX_ITEMS_LIMIT = ContextChunkingPolicy.MAX_ITEMS_LIMIT
    DEFAULT_MAX_SOURCE_CHARS = ContextChunkingPolicy.DEFAULT_MAX_SOURCE_CHARS
    CHUNK_SIZE = DEFAULT_MAX_ITEMS
    REVIEW_BATCH_SIZE = ContextCandidateAdapter.REVIEW_BATCH_SIZE
    SCHEMA_VERSION = "context-v2"
    PROMPT_VERSION = "context-synthesis-v5"
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
        analysis_batch_repository: Any | None = None,
    ):
        self.repository = repository
        self.context_service = context_service or ContextService(repository)
        self.handler_factory = handler_factory
        self.candidate_store = candidate_store
        self.task_backend = task_backend
        self.candidate_adapter = candidate_adapter or ContextCandidateAdapter(candidate_store)
        self.status_service = status_service or ContextWorkflowStatusService(task_backend)
        self.analysis_checkpoints = ContextAnalysisCheckpointService(analysis_batch_repository)
        self.release_assembler = ContextReleaseAssembler(repository)
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
        description_language: str | None = None,
        analysis_scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        upstream_version: str | None = None,
        analysis_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = AnalysisScope(analysis_scope)
        effective_description_language = description_language or review_language
        parsed_files: tuple[ParsedSourceFile, ...] = ()
        processed_files = 0
        analysis_run = None
        try:
            parsed_files = self.source_parser.parse_files(file_paths, source_root)
            snapshot = self.source_parser.build_snapshot(parsed_files, self.snapshot_service)
            parent = self._latest_release(project_id) if scope is AnalysisScope.NARRATIVE_CONTEXT else None
            diff = self._source_diff(parent, snapshot)
            source_items = [item for source_file in parsed_files for item in source_file.items]
            chunk_config = self._chunk_config(analysis_config)
            chunks = list(self._chunks(source_items, **chunk_config))
            workflow_context = self._workflow_context(
                scope,
                api_provider,
                model_name,
                source_lang,
                target_lang,
                effective_description_language,
                len(source_items),
                chunk_config,
            )
            analysis_run = self.analysis_checkpoints.start(
                project_id,
                task_id,
                snapshot.source_snapshot_hash,
                scope,
                {
                    "provider": api_provider,
                    "model": model_name or f"{api_provider}-default",
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "description_language": effective_description_language,
                    "game_name": game_name,
                    "chunking": dict(chunk_config),
                },
            )
            if analysis_run is not None:
                workflow_context.update({
                    "analysis_run_id": analysis_run.run_id,
                    "resume_supported": True,
                })
            self._running(
                project_id,
                task_id,
                scope,
                parsed_files,
                snapshot,
                diff,
                source_items=len(source_items),
                total_batches=len(chunks),
                workflow_context=workflow_context,
            )
            handler = self.handler_factory(api_provider, model_name=model_name)
            miner = self.miner_factory(handler)
            extractions = self._extract(
                miner,
                chunks,
                scope,
                game_name,
                project_id,
                task_id,
                target_lang,
                effective_description_language,
                analysis_run,
            )
            terms_result = self._finish_terms_only(
                project_id, parsed_files, extractions, miner, duplicate_index or {},
                source_lang, target_lang, game_name, effective_description_language, task_id,
                snapshot.source_snapshot_hash, scope, workflow_context,
                analysis_run.run_id if analysis_run is not None else None,
            )
            if scope is AnalysisScope.TERMS_ONLY:
                result = terms_result
            else:
                result = self._finish_context(
                    project_id, parsed_files, snapshot, diff, parent, extractions,
                    handler, api_provider, model_name, upstream_version, analysis_config,
                    effective_description_language, chunk_config, task_id,
                )
                result.update({"new_terms": terms_result["new_terms"], "duplicate_terms": terms_result["duplicate_terms"]})
            if analysis_run is not None:
                self.analysis_checkpoints.mark_published(analysis_run)
                result["analysis_run_id"] = analysis_run.run_id
            self._complete(project_id, task_id, result, len(parsed_files))
            return result
        except Exception as exc:
            self.analysis_checkpoints.mark_failed(analysis_run)
            self._failed(project_id, task_id, len(parsed_files), processed_files, exc)
            raise

    def _extract(
        self,
        miner: Any,
        chunks: Sequence[Sequence[SourceItem]],
        scope: AnalysisScope,
        game_name: str,
        project_id: str,
        task_id: str | None,
        target_language: str,
        reasoning_language: str,
        analysis_run: Any | None,
    ) -> list[StructuredNeologismExtraction]:
        results: list[StructuredNeologismExtraction] = []
        for index, chunk in enumerate(chunks, start=1):
            batch_id = f"extracting:{index}"
            source_item_ids = [item.source_item_id for item in chunk]
            result = self.analysis_checkpoints.restore_extraction(
                analysis_run, index - 1, source_item_ids,
            )
            if result is not None:
                results.append(result)
                self.status_service.record_batch(
                    project_id,
                    task_id,
                    "extracting",
                    batch_id,
                    success=True,
                    source_item_ids=source_item_ids,
                    resumed=True,
                )
                continue
            try:
                result = miner.extract_structured(
                    list(chunk),
                    scope=scope,
                    game_name=game_name,
                    target_language=target_language,
                    reasoning_language=reasoning_language,
                )
            except Exception as exc:
                self.analysis_checkpoints.save_extraction_failure(
                    analysis_run, index - 1, source_item_ids, exc,
                )
                self.status_service.record_batch(
                    project_id,
                    task_id,
                    "extracting",
                    batch_id,
                    success=False,
                    source_item_ids=source_item_ids,
                    error=str(exc),
                )
                raise
            self.analysis_checkpoints.save_extraction(
                analysis_run, index - 1, chunk, result,
            )
            results.append(result)
            self.status_service.record_batch(
                project_id,
                task_id,
                "extracting",
                batch_id,
                success=True,
                source_item_ids=source_item_ids,
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
        task_id: str | None,
        source_snapshot_hash: str,
        analysis_scope: AnalysisScope,
        analysis_config: dict[str, Any],
        run_id: str | None,
    ) -> dict[str, Any]:
        self.status_service.begin_stage(project_id, task_id, "reviewing", 0)
        review_miner = _ReviewProgressMiner(
            miner,
            lambda batch_id, **details: self.status_service.record_batch(
                project_id, task_id, "reviewing", batch_id, **details
            ),
        )
        result = self.candidate_adapter.process_terms(
            project_id, parsed_files, extractions, review_miner, duplicate_index,
            source_lang, target_lang, game_name, review_language,
            task_id=task_id,
            source_snapshot_hash=source_snapshot_hash,
            analysis_scope=analysis_scope,
            analysis_config=analysis_config,
            run_id=run_id,
            batch_store=self.analysis_checkpoints.repository,
        )
        self.status_service.complete_stage(
            project_id,
            task_id,
            "reviewing",
            skipped=review_miner.batch_count == 0,
        )
        return result

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
        description_language: str,
        chunk_config: dict[str, int],
        task_id: str | None,
    ) -> dict[str, Any]:
        sources = self.release_assembler.persist_sources(
            project_id, parsed_files, snapshot.source_snapshot_hash,
        )
        contributions = self.release_assembler.persist_contributions(extractions, sources)
        if not contributions:
            return {
                "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
                "new_terms": 0,
                "context_release_id": None,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "affected_source_items": self._affected_items(diff),
            }
        aggregates = self.release_assembler.build_aggregates(project_id, contributions)
        delivery_memberships = ContextDeliveryMembershipService.build(
            extractions, aggregates, sources,
        )
        for aggregate in aggregates:
            self.repository.save_aggregate(aggregate)
        source_item_ids = list(sources)
        synthesizer = self.synthesizer_factory(handler)
        planned_synthesis_batches = synthesizer.plan_batches(
            aggregates,
            contributions,
            sources,
            description_language,
        )
        self.status_service.begin_stage(
            project_id,
            task_id,
            "synthesizing",
            len(planned_synthesis_batches),
            source_item_ids=source_item_ids,
        )
        syntheses = synthesizer.synthesize(
            aggregates,
            contributions,
            sources,
            description_language,
            on_batch=lambda index, batch, **details: self.status_service.record_batch(
                project_id,
                task_id,
                "synthesizing",
                f"synthesizing:{index}",
                source_item_ids=self.release_assembler.aggregate_source_ids(batch, contributions),
                **details,
            ),
            planned_batches=planned_synthesis_batches,
        )
        metadata = self.release_assembler.metadata(
            snapshot, parsed_files, diff, parent, api_provider, model_name,
            upstream_version, analysis_config, description_language, chunk_config,
            self.SCHEMA_VERSION, self.PROMPT_VERSION,
        )
        self.status_service.begin_stage(project_id, task_id, "publishing", 1, source_item_ids=source_item_ids)
        draft = self.context_service.start_draft(project_id, parent.release_id if parent else None)
        try:
            release = self.context_service.publish_draft(
                draft.draft_id,
                metadata,
                [item.aggregate_id for item in aggregates],
                syntheses,
                delivery_memberships,
            )
        except Exception as exc:
            self.status_service.record_batch(
                project_id, task_id, "publishing", "publishing:1",
                success=False, source_item_ids=source_item_ids, error=str(exc),
            )
            raise
        self.status_service.record_batch(
            project_id, task_id, "publishing", "publishing:1",
            success=True, source_item_ids=source_item_ids,
        )
        return {
            "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
            "new_terms": 0,
            "context_release_id": release.release_id,
            "source_snapshot_hash": snapshot.source_snapshot_hash,
            "affected_source_items": self._affected_items(diff),
            "parent_release_id": parent.release_id if parent else None,
            "delivery_membership_count": len(delivery_memberships),
        }

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
        return ContextReleaseAssembler.affected_items(diff)

    def _latest_release(self, project_id: str) -> ContextRelease | None:
        releases = self.repository.list_releases(project_id)
        return releases[0] if releases else None

    _chunk_config = ContextChunkingPolicy.config

    @staticmethod
    def _workflow_context(
        scope: AnalysisScope,
        provider: str,
        model: str | None,
        source_lang: str,
        target_lang: str,
        description_language: str,
        source_items: int,
        chunk_config: dict[str, int],
    ) -> dict[str, Any]:
        return {
            "analysis_scope": scope.value,
            "scope": scope.value,
            "provider": provider,
            "model": model or f"{provider}-default",
            "source_lang": source_lang,
            "target_lang": target_lang,
            "target": target_lang,
            "description_language": description_language,
            "description": description_language,
            "source_items": source_items,
            "chunking": dict(chunk_config),
        }

    _chunks = ContextChunkingPolicy.chunks
    _contiguous_groups = ContextChunkingPolicy.contiguous_groups
    _pack_group = ContextChunkingPolicy.pack_group
    _grouping_key = ContextChunkingPolicy.grouping_key

    def _running(
        self, project_id: str, task_id: str | None, scope: AnalysisScope,
        parsed_files: Sequence[ParsedSourceFile], snapshot: SourceSnapshot, diff: Any,
        *,
        source_items: int,
        total_batches: int,
        workflow_context: dict[str, Any],
    ) -> None:
        self.status_service.mark_running(
            project_id,
            task_id,
            scope,
            len(parsed_files),
            snapshot.source_snapshot_hash,
            self._affected_items(diff) if scope is AnalysisScope.NARRATIVE_CONTEXT else None,
            source_items=source_items,
            total_batches=total_batches,
            workflow_context=workflow_context,
        )

    def _complete(self, project_id: str, task_id: str | None, result: dict[str, Any], total_files: int) -> None:
        self.status_service.mark_completed(project_id, task_id, result, total_files)

    def _failed(self, project_id: str, task_id: str | None, total_files: int, processed_files: int, error: Exception) -> None:
        self.status_service.mark_failed(project_id, task_id, total_files, processed_files, error)

    def _set_status(self, project_id: str, **updates: Any) -> None:
        self.status_service.set_status(project_id, **updates)

    def _task_update(self, task_id: str | None, **updates: Any) -> None:
        self.status_service.update_task(task_id, **updates)
