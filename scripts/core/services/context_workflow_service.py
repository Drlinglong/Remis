"""Bounded backend orchestration for neologism and Mod Context analysis."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from scripts.core.api_handler import get_handler
from scripts.core.context_service import ContextService
from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import (
    AnalysisScope,
    MAX_DELIVERY_ASSIGNMENTS_PER_EXTRACTION,
    MAX_EVENTS_PER_EXTRACTION,
    SourceItem,
    StructuredNeologismExtraction,
    StructuredNeologismExtractor,
)
from scripts.core.neologism_manager import neologism_manager
from scripts.core.neologism_miner import NeologismMiner
from scripts.core.provider_structured_output import structured_output_mode
from scripts.core.services.context_candidate_adapter import ContextCandidateAdapter
from scripts.core.services.context_candidate_governance_flow_service import (
    ContextCandidateGovernanceFlowService,
)
from scripts.core.services.context_analysis_checkpoint_service import (
    ContextAnalysisCheckpointService,
)
from scripts.core.services.context_analysis_report_service import ContextAnalysisReportService
from scripts.core.services.context_chunking_policy import ContextChunkingPolicy, ContextUnitChunk
from scripts.core.services.context_delivery_membership_service import (
    ContextDeliveryMembershipService,
)
from scripts.core.services.context_extraction_execution_service import (
    ContextExtractionExecutionService,
)
from scripts.core.services.context_event_reconciliation_service import (
    ContextEventReconciliationService,
    EventReconciliationResult,
)
from scripts.core.services.context_event_reconciliation_execution_service import (
    ContextEventReconciliationExecutionService,
)
from scripts.core.services.context_parallel_execution_service import (
    map_context_calls_ordered,
    resolve_context_concurrency,
)
from scripts.core.services.context_model_usage import ContextModelUsageLedger
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


class ContextWorkflowService:
    """Own the maintained scan workflow while keeping domain ports injectable."""

    DEFAULT_MAX_ITEMS = ContextChunkingPolicy.DEFAULT_MAX_ITEMS
    MAX_ITEMS_LIMIT = ContextChunkingPolicy.MAX_ITEMS_LIMIT
    DEFAULT_MAX_SOURCE_CHARS = ContextChunkingPolicy.DEFAULT_MAX_SOURCE_CHARS
    CHUNK_SIZE = DEFAULT_MAX_ITEMS
    REVIEW_BATCH_SIZE = ContextCandidateAdapter.REVIEW_BATCH_SIZE
    SCHEMA_VERSION = "context-v4"
    PROMPT_VERSION = "context-archive-v9"
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
        reconciler_factory: Callable[[Any], Any] = ContextEventReconciliationService,
        context_service: ContextService | None = None,
        candidate_adapter: ContextCandidateAdapter | None = None,
        status_service: ContextWorkflowStatusService | None = None,
        analysis_batch_repository: Any | None = None,
        governance_service: Any | None = None,
    ):
        self.repository = repository
        self.context_service = context_service or ContextService(repository)
        self.handler_factory = handler_factory
        self.candidate_store = candidate_store
        self.task_backend = task_backend
        self.candidate_adapter = candidate_adapter or ContextCandidateAdapter(candidate_store)
        self.status_service = status_service or ContextWorkflowStatusService(task_backend)
        self.analysis_checkpoints = ContextAnalysisCheckpointService(analysis_batch_repository)
        self.governance_flow = ContextCandidateGovernanceFlowService(
            candidate_adapter=self.candidate_adapter,
            status_service=self.status_service,
            batch_store=self.analysis_checkpoints.repository,
            governance_service=governance_service,
        )
        self.release_assembler = ContextReleaseAssembler(repository)
        self.source_parser = source_parser or ContextSourceParser()
        self.snapshot_service = snapshot_service or SourceSnapshotService()
        self.miner_factory = miner_factory
        self.synthesizer_factory = synthesizer_factory
        self.reconciler_factory = reconciler_factory

    def reserve(self, project_id: str, task_id: str, scope: AnalysisScope) -> bool:
        return self.status_service.reserve(project_id, task_id, scope)

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return ContextWorkflowStatusService._idle_status()

    def release_reservation(self, project_id: str, task_id: str) -> None:
        self.status_service.release_reservation(project_id, task_id)

    def get_status(self, project_id: str) -> dict[str, Any]:
        return self.status_service.get_status(project_id)

    @staticmethod
    def prompt_example(description_language: str) -> str:
        extraction = StructuredNeologismExtractor.SYSTEM_PROMPT.format(
            scope=AnalysisScope.NARRATIVE_CONTEXT.value,
            game_name="Paradox Game",
            target_language="the configured target language",
            reasoning_language=description_language,
        ).strip()
        reconciliation = ContextEventReconciliationService._system_prompt(
            description_language,
        )
        synthesis = ContextSynthesisService.prompt_example(description_language)
        return (
            f"[Local extraction]\n{extraction}\n\n"
            f"[Global event reconciliation]\n{reconciliation}\n\n"
            f"[Archive synthesis]\n{synthesis}"
        )

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
        concurrency_limit: int | None = None,
    ) -> dict[str, Any]:
        scope = AnalysisScope(analysis_scope)
        effective_description_language = description_language or review_language
        parsed_files: tuple[ParsedSourceFile, ...] = ()
        processed_files = 0
        analysis_run, usage_ledger = None, ContextModelUsageLedger()
        try:
            parsed_files = self.source_parser.parse_files(file_paths, source_root)
            snapshot = self.source_parser.build_snapshot(parsed_files, self.snapshot_service)
            parent = self._latest_release(project_id) if scope is AnalysisScope.NARRATIVE_CONTEXT else None
            diff = self._source_diff(parent, snapshot)
            source_items = [item for source_file in parsed_files for item in source_file.items]
            chunk_config = self._chunk_config(analysis_config)
            local_units = ContextLocalUnitBuilder.build(source_items)
            edge_units = (
                ContextChunkingPolicy.DEFAULT_EDGE_UNITS
                if scope is AnalysisScope.NARRATIVE_CONTEXT else 0
            )
            chunks = ContextChunkingPolicy.unit_chunks(
                local_units, **chunk_config, edge_units=edge_units,
            )
            effective_concurrency = resolve_context_concurrency(
                concurrency_limit, api_provider,
            )
            workflow_context = self._workflow_context(
                scope,
                api_provider,
                model_name,
                source_lang,
                target_lang,
                effective_description_language,
                len(source_items),
                chunk_config,
                effective_concurrency,
                concurrency_limit,
            )
            workflow_context.update(self._chunk_diagnostics(local_units, chunks))
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
                    "schema_version": self.SCHEMA_VERSION,
                    "prompt_version": self.PROMPT_VERSION,
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
            extractions = self._extract(
                chunks,
                scope,
                game_name,
                project_id,
                task_id,
                target_lang,
                effective_description_language,
                analysis_run,
                api_provider,
                model_name,
                effective_concurrency,
                usage_ledger,
            )
            result = self._finish_scope(
                project_id, task_id, scope, parsed_files, snapshot, diff, parent,
                source_items, local_units, chunks, extractions, api_provider, model_name,
                source_lang, target_lang, game_name, effective_description_language,
                duplicate_index or {}, workflow_context, analysis_run, upstream_version,
                analysis_config, chunk_config, effective_concurrency,
                usage_ledger,
            )
            if analysis_run is not None:
                self.analysis_checkpoints.mark_published(analysis_run)
                result["analysis_run_id"] = analysis_run.run_id
            self._complete(project_id, task_id, result, len(parsed_files))
            return result
        except Exception as exc:
            self.analysis_checkpoints.mark_failed(analysis_run)
            self._failed(project_id, task_id, len(parsed_files), processed_files, exc)
            raise

    def _finish_scope(
        self,
        project_id: str,
        task_id: str | None,
        scope: AnalysisScope,
        parsed_files: Sequence[ParsedSourceFile],
        snapshot: SourceSnapshot,
        diff: Any,
        parent: ContextRelease | None,
        source_items: Sequence[SourceItem],
        local_units: Sequence[Any],
        chunks: Sequence[ContextUnitChunk],
        extractions: Sequence[StructuredNeologismExtraction],
        api_provider: str,
        model_name: str | None,
        source_lang: str,
        target_lang: str,
        game_name: str,
        description_language: str,
        duplicate_index: dict[str, list[dict[str, Any]]],
        workflow_context: dict[str, Any],
        analysis_run: Any | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
        chunk_config: dict[str, int],
        effective_concurrency: int,
        usage_ledger: ContextModelUsageLedger,
    ) -> dict[str, Any]:
        reconciled = None
        final_extractions = list(extractions)
        if scope is AnalysisScope.NARRATIVE_CONTEXT:
            reconciled = self._reconcile_events(
                project_id, task_id, local_units, extractions, api_provider,
                model_name, description_language, analysis_run, effective_concurrency,
                usage_ledger,
            )
            final_extractions = self._replace_local_events(extractions, reconciled)
        review_miner = self.miner_factory(self.handler_factory(api_provider, model_name=model_name))
        governance, terms = self.governance_flow.govern_and_process_terms(
            governance_kwargs={
                "project_id": project_id, "extractions": final_extractions,
                "analysis_scope": scope, "source_items": source_items,
                "local_units": local_units, "reconciled": reconciled,
                "duplicate_index": duplicate_index, "source_language": source_lang,
            },
            process_kwargs={
                "project_id": project_id, "parsed_files": parsed_files,
                "extractions": final_extractions, "miner": review_miner,
                "duplicate_index": duplicate_index, "source_lang": source_lang,
                "target_lang": target_lang, "game_name": game_name,
                "review_language": description_language, "task_id": task_id,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "analysis_scope": scope, "analysis_config": analysis_config,
                "run_id": analysis_run.run_id if analysis_run is not None else None,
                "usage_ledger": usage_ledger,
            },
        )
        if reconciled is None:
            analysis_report = None
        else:
            analysis_report = self._analysis_report(
                source_items, local_units, chunks, extractions, reconciled,
                provider=api_provider, model=model_name,
                effective_concurrency=effective_concurrency,
                prompt_version=self.PROMPT_VERSION,
                parsed_files=parsed_files,
                model_execution=usage_ledger.summary(),
                governance=governance,
            )
        if reconciled is None:
            terms["analysis_report"] = ContextAnalysisReportService.governance_only(governance)
            terms["candidate_governance"] = governance.counts()
            return terms
        result = self._finish_context(
            project_id, parsed_files, snapshot, diff, parent, final_extractions,
            api_provider, model_name, upstream_version, analysis_config,
            description_language, chunk_config, task_id, effective_concurrency,
            analysis_report, governance, usage_ledger,
        )
        result["analysis_report"] = analysis_report
        result.update({
            "new_terms": terms["new_terms"],
            "duplicate_terms": terms["duplicate_terms"],
            "candidate_governance": governance.counts(),
        })
        return result

    def _extract(
        self,
        chunks: Sequence[ContextUnitChunk],
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
        usage_ledger: ContextModelUsageLedger,
    ) -> list[StructuredNeologismExtraction]:
        return ContextExtractionExecutionService(
            handler_factory=self.handler_factory,
            miner_factory=self.miner_factory,
            checkpoints=self.analysis_checkpoints,
            status_service=self.status_service,
            usage_ledger=usage_ledger,
        ).execute(
            chunks,
            scope=scope,
            game_name=game_name,
            project_id=project_id,
            task_id=task_id,
            target_language=target_language,
            reasoning_language=reasoning_language,
            analysis_run=analysis_run,
            api_provider=api_provider,
            model_name=model_name,
            concurrency=concurrency,
        )

    def _reconcile_events(
        self,
        project_id: str,
        task_id: str | None,
        local_units: Sequence[Any],
        extractions: Sequence[StructuredNeologismExtraction],
        api_provider: str,
        model_name: str | None,
        description_language: str,
        analysis_run: Any | None,
        concurrency: int,
        usage_ledger: ContextModelUsageLedger,
    ) -> EventReconciliationResult:
        return ContextEventReconciliationExecutionService(
            handler_factory=self.handler_factory,
            reconciler_factory=self.reconciler_factory,
            checkpoints=self.analysis_checkpoints,
            status_service=self.status_service,
            usage_ledger=usage_ledger,
        ).execute(
            local_units,
            extractions,
            project_id=project_id,
            task_id=task_id,
            analysis_run=analysis_run,
            api_provider=api_provider,
            model_name=model_name,
            description_language=description_language,
            concurrency=concurrency,
        )

    @staticmethod
    def _replace_local_events(
        extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> list[StructuredNeologismExtraction]:
        local = [
            extraction.model_copy(update={"events": [], "delivery_assignments": []})
            for extraction in extractions
        ]
        global_batch_count = max(
            1,
            (len(reconciled.events) + MAX_EVENTS_PER_EXTRACTION - 1)
            // MAX_EVENTS_PER_EXTRACTION,
            (
                len(reconciled.delivery_assignments)
                + MAX_DELIVERY_ASSIGNMENTS_PER_EXTRACTION
                - 1
            )
            // MAX_DELIVERY_ASSIGNMENTS_PER_EXTRACTION,
        )
        global_batches = [
            StructuredNeologismExtraction(
                events=reconciled.events[
                    index * MAX_EVENTS_PER_EXTRACTION:
                    (index + 1) * MAX_EVENTS_PER_EXTRACTION
                ],
                delivery_assignments=reconciled.delivery_assignments[
                    index * MAX_DELIVERY_ASSIGNMENTS_PER_EXTRACTION:
                    (index + 1) * MAX_DELIVERY_ASSIGNMENTS_PER_EXTRACTION
                ],
                diagnostics=reconciled.diagnostics if index == 0 else {},
            )
            for index in range(global_batch_count)
        ]
        return [*local, *global_batches]

    def _finish_context(
        self,
        project_id: str,
        parsed_files: Sequence[ParsedSourceFile],
        snapshot: SourceSnapshot,
        diff: Any,
        parent: ContextRelease | None,
        extractions: Sequence[StructuredNeologismExtraction],
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
        description_language: str,
        chunk_config: dict[str, int],
        task_id: str | None,
        concurrency: int,
        analysis_report: dict[str, Any],
        governance: Any,
        usage_ledger: ContextModelUsageLedger,
    ) -> dict[str, Any]:
        sources = self.release_assembler.persist_sources(
            project_id, parsed_files, snapshot.source_snapshot_hash,
        )
        governance_available = bool(getattr(governance, "available", False))
        contributions = self.release_assembler.persist_contributions(
            extractions,
            sources,
            governance.aggregate_key_for_surface if governance_available else None,
        )
        if not contributions:
            return {
                "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
                "new_terms": 0,
                "context_release_id": None,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "affected_source_items": self._affected_items(diff),
            }
        aggregates = self.release_assembler.build_aggregates(
            project_id,
            contributions,
            governance if governance_available else None,
        )
        delivery_memberships = ContextDeliveryMembershipService.build(
            extractions, aggregates, sources,
        )
        for aggregate in aggregates:
            self.repository.save_aggregate(aggregate)
        source_item_ids = list(sources)
        synthesizer = self.synthesizer_factory(
            self.handler_factory(api_provider, model_name=model_name)
        )
        synthesis_aggregates = self.governance_flow.synthesis_eligible_aggregates(
            aggregates, governance,
        )
        planned_synthesis_batches = synthesizer.plan_batches(
            synthesis_aggregates,
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
        syntheses = self._synthesize_parallel(
            planned_synthesis_batches, contributions, sources, description_language,
            project_id, task_id, api_provider, model_name, concurrency,
            usage_ledger,
        )
        model_execution = usage_ledger.summary()
        analysis_report["model_execution"] = model_execution
        analysis_report["input_and_chunking"].update({
            "reasoning_profile": model_execution.get("reasoning_profile"),
            "token_usage": model_execution.get("token_usage"),
            "cost": model_execution.get("cost"),
            "usage_note": model_execution.get("usage_note"),
        })
        metadata_config = dict(analysis_config or {})
        metadata_config["effective_concurrency"] = concurrency
        metadata_config["candidate_governance"] = governance.counts()
        metadata_config["analysis_report"] = analysis_report
        metadata = self.release_assembler.metadata(
            snapshot, parsed_files, diff, parent, api_provider, model_name,
            upstream_version, metadata_config, description_language, chunk_config,
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
            "candidate_governance": governance.counts(),
        }

    def _synthesize_parallel(
        self,
        batches: Sequence[Sequence[Any]],
        contributions: dict[str, Any],
        sources: dict[str, Any],
        description_language: str,
        project_id: str,
        task_id: str | None,
        api_provider: str,
        model_name: str | None,
        concurrency: int,
        usage_ledger: ContextModelUsageLedger,
    ) -> list[Any]:
        materialized = [list(batch) for batch in batches]

        def worker(batch: list[Any]) -> list[Any]:
            handler = self.handler_factory(api_provider, model_name=model_name)
            synthesizer = self.synthesizer_factory(handler)
            try:
                return synthesizer.synthesize(
                    batch,
                    contributions,
                    sources,
                    description_language,
                    planned_batches=[batch],
                )
            finally:
                usage_ledger.capture(handler, "synthesis")

        def record_completion(outcome: Any) -> None:
            source_ids = self.release_assembler.aggregate_source_ids(
                outcome.item, contributions,
            )
            self.status_service.record_batch(
                project_id, task_id, "synthesizing",
                f"synthesizing:{outcome.index + 1}",
                success=outcome.succeeded,
                source_item_ids=source_ids,
                error=str(outcome.error) if outcome.error else None,
            )

        outcomes = map_context_calls_ordered(
            materialized,
            worker,
            max_workers=concurrency,
            on_completed=record_completion,
        )
        errors = [outcome.error for outcome in outcomes if outcome.error is not None]
        if errors:
            raise errors[0]
        return [item for outcome in outcomes for item in (outcome.value or [])]

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
    _analysis_report = staticmethod(ContextAnalysisReportService.build)

    @staticmethod
    def _chunk_diagnostics(
        local_units: Sequence[Any], chunks: Sequence[ContextUnitChunk],
    ) -> dict[str, Any]:
        return {
            "local_units": len(local_units),
            "chunks": len(chunks),
            "core_units_per_chunk": [len(chunk.core_units) for chunk in chunks],
            "edge_units_per_chunk": [len(chunk.edge_units) for chunk in chunks],
        }

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
        effective_concurrency: int,
        concurrency_limit: int | None,
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
            "concurrency_limit": concurrency_limit,
            "effective_concurrency": effective_concurrency,
            "structured_output_mode": structured_output_mode(provider),
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
