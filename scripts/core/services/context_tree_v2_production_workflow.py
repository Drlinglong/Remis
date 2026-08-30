"""Production adapter for the context archive tree v2 workflow."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceItem,
    StructuredNeologismExtraction,
)
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_model_usage import ContextModelUsageLedger
from scripts.core.services.context_tree_v2_analysis_assembler import (
    ContextTreeV2AnalysisAssembler,
)
from scripts.core.services.context_tree_v2_candidate_governance import (
    ContextTreeV2CandidateGovernanceService,
)
from scripts.core.services.context_tree_v2_checkpoint_service import (
    ContextTreeV2CheckpointService,
)
from scripts.core.services.context_tree_v2_catalog_service import (
    ContextTreeV2CatalogService,
)
from scripts.core.services.context_tree_v2_context_service import (
    ContextTreeV2ContextService,
)
from scripts.core.services.context_tree_v2_entity_digest import (
    ContextTreeV2EntityDigestService,
)
from scripts.core.services.context_tree_v2_extraction_execution_service import (
    ContextTreeV2ExtractionExecutionService,
)
from scripts.core.services.context_tree_v2_projection_service import (
    ContextTreeV2ProjectionService,
)
from scripts.core.services.context_tree_v2_term_candidate_service import (
    ContextTreeV2TermCandidateService,
)
from scripts.core.services.context_tree_v2_term_only import (
    ContextTreeV2TermOnlyService,
)
from scripts.core.services.context_tree_v2_workflow_service import (
    ContextTreeV2WorkflowResult,
)
from scripts.schemas.context_tree_v2_entity_digest import DigestLocalUnit


class ContextTreeV2ProductionWorkflowService:
    """Connect v2 model stages to status, candidates and immutable storage."""

    def __init__(
        self,
        *,
        handler_factory: Any,
        tree_repository: Any,
        candidate_store: Any,
        status_service: Any,
        checkpoint_repository: Any | None = None,
    ) -> None:
        self.handler_factory = handler_factory
        self.tree_repository = tree_repository
        self.candidate_store = candidate_store
        self.status_service = status_service
        self.checkpoints = ContextTreeV2CheckpointService(checkpoint_repository)

    def run(
        self,
        *,
        project_id: str,
        project_title: str,
        task_id: str | None,
        source_snapshot_hash: str,
        source_items: Sequence[SourceItem],
        local_units: Sequence[LocalTextUnit],
        chunks: Sequence[ContextUnitChunk],
        scope: AnalysisScope,
        api_provider: str,
        model_name: str | None,
        source_language: str,
        target_language: str,
        game_name: str,
        description_language: str,
        duplicate_index: dict[str, list[dict[str, Any]]],
        analysis_run: Any | None,
        usage_ledger: ContextModelUsageLedger,
        concurrency: int,
    ) -> dict[str, Any]:
        scope = AnalysisScope(scope)
        extractions = ContextTreeV2ExtractionExecutionService(
            handler_factory=self.handler_factory,
            checkpoints=self.checkpoints,
            status_service=self.status_service,
            usage_ledger=usage_ledger,
        ).execute(
            chunks,
            scope=scope,
            game_name=game_name,
            project_id=project_id,
            task_id=task_id,
            target_language=target_language,
            reasoning_language=description_language,
            analysis_run=analysis_run,
            api_provider=api_provider,
            model_name=model_name,
            concurrency=concurrency,
        )
        term_result = self._term_result(extractions, source_language)
        if scope is AnalysisScope.TERMS_ONLY:
            governance = ContextTreeV2CandidateGovernanceService(
                source_language
            ).govern(
                self._governance_views(extractions), source_items, local_units,
            )
            return self._finish_terms(
                project_id, task_id, term_result, source_items, local_units,
                source_language, target_language, description_language,
                duplicate_index, usage_ledger, governance,
            )
        return self._finish_archive(
            project_id=project_id,
            project_title=project_title,
            task_id=task_id,
            source_snapshot_hash=source_snapshot_hash,
            source_items=source_items,
            local_units=local_units,
            chunks=chunks,
            extractions=extractions,
            term_result=term_result,
            api_provider=api_provider,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            description_language=description_language,
            duplicate_index=duplicate_index,
            analysis_run=analysis_run,
            usage_ledger=usage_ledger,
        )

    @staticmethod
    def _term_result(extractions: Sequence[Any], source_language: str) -> Any:
        term_views = [
            {"terms": [item.model_dump(mode="json") for item in extraction.terms]}
            for extraction in extractions
        ]
        return ContextTreeV2TermOnlyService(source_language=source_language).build(term_views)

    @staticmethod
    def _governance_views(extractions: Sequence[Any]) -> list[StructuredNeologismExtraction]:
        return [
            StructuredNeologismExtraction(
                terms=list(item.terms), entities=list(item.entities),
            )
            for item in extractions
        ]

    def _finish_terms(
        self,
        project_id: str,
        task_id: str | None,
        term_result: Any,
        source_items: Sequence[SourceItem],
        local_units: Sequence[LocalTextUnit],
        source_language: str,
        target_language: str,
        description_language: str,
        duplicate_index: dict[str, list[dict[str, Any]]],
        ledger: ContextModelUsageLedger,
        governance: Any,
    ) -> dict[str, Any]:
        self.status_service.begin_stage(project_id, task_id, "reviewing", 1)
        counts = ContextTreeV2TermCandidateService(
            self.candidate_store, source_language=source_language,
        ).persist(
            project_id, term_result, governance, source_items,
            local_units=local_units,
            target_language=target_language,
            review_language=description_language,
            duplicate_index=duplicate_index,
        )
        self.status_service.record_batch(
            project_id, task_id, "reviewing", "tree-v2-program-terms", success=True,
            source_item_ids=[item.source_item_id for item in source_items],
        )
        self.status_service.complete_stage(project_id, task_id, "reviewing")
        return {
            **counts,
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "workflow_version": "context-tree-v2",
            "candidate_governance": {
                "coverage_authority": "program_distinct_local_units",
                "grade_rule": {"A": ">=3", "B": "2", "C": "1"},
            },
            "analysis_report": {
                "workflow_version": "context-tree-v2",
                "term_count": len(term_result.terms),
                "model_execution": ledger.summary(),
                "skipped_stages": dict(term_result.skipped_stages),
            },
        }

    def _finish_archive(self, **values: Any) -> dict[str, Any]:
        workflow = self._catalog_and_project(**values)
        group_ids = {
            route.local_unit_id: tuple(route.group_ids)
            for route in workflow.projection.unit_routes
        }
        structured = self._governance_views(values["extractions"])
        governance = ContextTreeV2CandidateGovernanceService(
            values["source_language"]
        ).govern(
            structured, values["source_items"], values["local_units"],
            event_group_ids_by_unit=group_ids,
        )
        digest_result = self._digest(workflow, governance, **values)
        tree_id = str(uuid.uuid4())
        assembled = ContextTreeV2AnalysisAssembler.assemble(
            project_id=values["project_id"], tree_id=tree_id,
            source_snapshot_hash=values["source_snapshot_hash"],
            project_title=values["project_title"],
            source_items=values["source_items"], local_units=values["local_units"],
            chunks=values["chunks"], extractions=values["extractions"],
            workflow_result=workflow, governance=governance,
            entity_digest_result=digest_result, term_result=values["term_result"],
        )
        return self._persist_archive(
            assembled, workflow, governance, digest_result, **values,
        )

    def _catalog_and_project(self, **values: Any) -> ContextTreeV2WorkflowResult:
        fragments = [
            fragment for extraction in values["extractions"]
            for fragment in extraction.local_fragments
        ]
        routes = [
            route for extraction in values["extractions"]
            for route in extraction.unit_routes
        ]
        self.status_service.begin_stage(values["project_id"], values["task_id"], "aggregating", 1)
        source_ids = [unit.unit_id for unit in values["local_units"]]
        catalog = self.checkpoints.restore_catalog(values["analysis_run"], source_ids)
        resumed = catalog is not None
        if catalog is None:
            handler = self.handler_factory(values["api_provider"], model_name=values["model_name"])
            try:
                catalog = ContextTreeV2CatalogService(handler).build_catalog(
                    fragments,
                    chunk_edge_metadata=[chunk.edge_metadata for chunk in values["chunks"]],
                    description_language=values["description_language"],
                )
                self.checkpoints.save_catalog(
                    values["analysis_run"], source_ids, catalog,
                )
            finally:
                values["usage_ledger"].capture(handler, "tree_v2_catalog")
        projection = ContextTreeV2ProjectionService.project(
            routes, catalog,
            expected_unit_ids=[unit.unit_id for unit in values["local_units"]],
        )
        contexts = ContextTreeV2ContextService.project_all_translation_contexts(
            projection, catalog.catalog, fragments, project_summary="",
        )
        self.status_service.record_batch(
            values["project_id"], values["task_id"], "aggregating",
            "tree-v2-catalog", success=True,
            source_item_ids=source_ids, resumed=resumed,
        )
        self.status_service.complete_stage(values["project_id"], values["task_id"], "aggregating")
        return ContextTreeV2WorkflowResult(
            extractions=tuple(values["extractions"]), catalog=catalog,
            projection=projection, translation_contexts=contexts,
            model_calls={
                "extraction": len(values["extractions"]),
                "fragment_repair": sum(
                    int(item.diagnostics.get("repair_count", 0))
                    for item in values["extractions"]
                ),
                "catalog": 0 if resumed else int(catalog.diagnostics.get("model_call_count", 1)),
                "assignment": 0, "synthesis": 0,
            },
            diagnostics={
                "schema_version": "context-tree-v2",
                "prompt_version": "context-archive-tree-v2",
                "assignment_model_calls": 0,
                "aggregate_synthesis_model_calls": 0,
            },
        )

    def _digest(self, workflow: Any, governance: Any, **values: Any) -> Any:
        digest_units = self._digest_units(
            values["local_units"], values["chunks"], values["extractions"],
            workflow.projection,
        )
        groups = ContextTreeV2ContextService.build_group_contexts(
            workflow.catalog.catalog,
            [fragment for item in values["extractions"] for fragment in item.local_fragments],
        )
        self.status_service.begin_stage(values["project_id"], values["task_id"], "synthesizing", 1)
        source_ids = [unit.unit_id for unit in values["local_units"]]
        result = self.checkpoints.restore_digests(values["analysis_run"], source_ids)
        resumed = result is not None
        if result is None:
            handler = self.handler_factory(values["api_provider"], model_name=values["model_name"])
            try:
                result = ContextTreeV2EntityDigestService(handler).run(
                    governance.candidates, digest_units,
                    project_title=values["project_title"], event_group_summaries=groups,
                )
                eligible_ids = {
                    item.candidate_id for item in governance.candidates
                    if item.is_digest_eligible
                }
                complete_ids = {
                    item.candidate_id for item in result.digests
                    if item.digest_status == "complete"
                }
                if eligible_ids <= complete_ids:
                    self.checkpoints.save_digests(
                        values["analysis_run"], source_ids, result,
                    )
            finally:
                values["usage_ledger"].capture(handler, "tree_v2_entity_digest")
        self.status_service.record_batch(
            values["project_id"], values["task_id"], "synthesizing",
            "tree-v2-entity-digests", success=True,
            source_item_ids=source_ids, resumed=resumed,
        )
        self.status_service.complete_stage(values["project_id"], values["task_id"], "synthesizing")
        return result

    @staticmethod
    def _digest_units(local_units: Sequence[Any], chunks: Sequence[Any], extractions: Sequence[Any], projection: Any) -> tuple[DigestLocalUnit, ...]:
        batch_by_unit = {
            unit.unit_id: index
            for index, chunk in enumerate(chunks)
            for unit in chunk.core_units
        }
        groups_by_unit = {
            route.local_unit_id: tuple(route.group_ids)
            for route in projection.unit_routes
        }
        summaries: dict[str, list[str]] = {}
        for extraction in extractions:
            for fragment in extraction.local_fragments:
                for unit_id in fragment.unit_ids:
                    summaries.setdefault(unit_id, []).append(fragment.summary)
        return tuple(
            DigestLocalUnit(
                unit_id=unit.unit_id,
                source_text="\n".join(item.source_text for item in unit.items),
                event_group_ids=groups_by_unit.get(unit.unit_id, ()),
                batch_index=batch_by_unit.get(unit.unit_id),
                unit_order=index,
                fragment_summary="\n".join(dict.fromkeys(summaries.get(unit.unit_id, ()))),
            )
            for index, unit in enumerate(local_units)
        )

    def _persist_archive(
        self, tree: Any, workflow: Any, governance: Any, digests: Any,
        **values: Any,
    ) -> dict[str, Any]:
        project_id, task_id = values["project_id"], values["task_id"]
        self.status_service.begin_stage(project_id, task_id, "publishing", 1)
        stored = self.tree_repository.save_tree(tree)
        draft = self.tree_repository.create_draft(project_id, stored.tree_id)
        validation = self.tree_repository.validate_draft(project_id, draft.draft_id)
        eligible = [item for item in governance.candidates if item.is_digest_eligible]
        complete_ids = {
            item.candidate_id for item in digests.digests
            if item.digest_status == "complete"
        }
        all_required_digests_complete = all(
            item.candidate_id in complete_ids for item in eligible
        )
        counts = ContextTreeV2TermCandidateService(
            self.candidate_store, source_language=values["source_language"],
        ).persist(
            project_id, values["term_result"], governance, values["source_items"],
            local_units=values["local_units"],
            target_language=values["target_language"],
            review_language=values["description_language"],
            duplicate_index=values["duplicate_index"],
        )
        release = None
        if validation.valid and all_required_digests_complete:
            release = self.tree_repository.publish_draft(
                project_id, draft.draft_id,
                idempotency_key=f"context-tree-v2:{stored.tree_id}",
            )
        self.status_service.record_batch(
            project_id, task_id, "publishing", "tree-v2-storage", success=True,
            source_item_ids=[item.source_item_id for item in values["source_items"]],
        )
        self.status_service.complete_stage(project_id, task_id, "publishing")
        release_id = release.get("release_id") if isinstance(release, dict) else getattr(release, "release_id", None)
        complete = [item for item in digests.digests if item.digest_status == "complete"]
        return {
            **counts,
            "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
            "workflow_version": "context-tree-v2",
            "tree_id": stored.tree_id,
            "draft_id": draft.draft_id,
            "context_release_id": release_id,
            "publication_status": "published" if release_id else "review_required",
            "candidate_governance": governance.report,
            "analysis_report": {
                "workflow_version": "context-tree-v2",
                "model_calls": {
                    **workflow.model_calls,
                    "entity_digest": len([
                        item for item in digests.call_records if item.status != "skipped"
                    ]),
                },
                "entity_digest_eligible": len(eligible),
                "entity_digest_complete": len(complete),
                "entity_digest_incomplete": len(eligible) - len(complete),
                "required_entity_digests_complete": all_required_digests_complete,
                "full_entity_evidence_retained": sum(
                    len(item.full_evidence) for item in digests.evidence_bundles
                ),
                "unresolved_reference_count": len(stored.unresolved_references),
                "validation": validation.model_dump(mode="json"),
                "model_execution": values["usage_ledger"].summary(),
            },
        }


__all__ = ["ContextTreeV2ProductionWorkflowService"]
