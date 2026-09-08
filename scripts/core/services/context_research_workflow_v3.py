"""Lightweight Workflow v3 backend for three-axis Context Research."""

from __future__ import annotations

import re
from typing import Any, Callable

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_model_usage import ContextModelUsageLedger
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ArchiveNarrative,
    ContextAnalysisRequest,
    ContextResearchDraft,
    EvidenceReference,
    EventChain,
    ReferenceAsset,
    ResearchEntity,
)
from scripts.core.services.context_research_entity_grading import (
    calculate_entity_frequency,
)
from scripts.core.services.context_research_entity_normalization import (
    normalize_compiled_entities,
)
from scripts.core.services.context_research_read_metrics import CorpusReadMeter
from scripts.core.services.context_research_tree_v2_adapter import (
    ContextResearchTreeV2Adapter,
    ContextResearchUnsupported,
)
from scripts.core.services.context_research_universal_context import (
    build_universal_translation_context,
)
from scripts.core.services.context_publication_policy import evaluate_context_publication
from scripts.core.services.context_tree_v2_contract import UnitRoute
from scripts.core.services.context_tree_v2_workflow_service import (
    ContextTreeV2WorkflowResult,
    ContextTreeV2WorkflowService,
)
from scripts.core.services.context_tree_v2_contract import (
    ContextTreeV2Extraction,
    TranslationContextProjection,
    TreeCatalogResult,
    TreeProjectionResult,
)
from scripts.core.services.context_workflow_v3_catalog import (
    ContextWorkflowV3CatalogService,
)
from scripts.core.services.context_workflow_v3_extraction import (
    ContextWorkflowV3ExtractionService,
)


_ENTITY_TYPE_MAP = {
    "person": "person",
    "place": "place",
    "organization/faction": "organization",
    "technology/concept": "concept",
    "item/other": "item",
}


class ContextResearchWorkflowV3(ContextResearchTreeV2Adapter):
    """Run bounded chunk analysis, one global lead, and deterministic assembly."""

    def __init__(
        self,
        workflow: ContextTreeV2WorkflowService | Any | None = None,
        *,
        handler_factory: Callable[..., Any] | None = None,
        usage_ledger: ContextModelUsageLedger | None = None,
    ) -> None:
        self.usage_ledger = usage_ledger or ContextModelUsageLedger()
        self.last_debug_snapshot: dict[str, Any] | None = None
        if workflow is None:
            if handler_factory is None:
                raise ValueError("workflow or handler_factory is required")
            workflow = ContextTreeV2WorkflowService(
                handler_factory=handler_factory,
                extractor_factory=ContextWorkflowV3ExtractionService,
                catalog_factory=ContextWorkflowV3CatalogService,
                usage_ledger=self.usage_ledger,
            )
        super().__init__(workflow)

    async def analyze(
        self,
        request: ContextAnalysisRequest,
        execution_context: AgentExecutionContext,
    ) -> ContextResearchDraft:
        self._check_cancelled(execution_context)
        if request.scope.value == "terms_only":
            raise ContextResearchUnsupported(
                "Workflow v3 requires narrative_context scope"
            )
        chunks = self._chunks(request)
        meter = self._read_meter(request, chunks)
        self._emit(execution_context, "context_research.started", {
            "request_id": request.request_id,
            "backend": "context-workflow-v3",
            "chunk_count": len(chunks),
        })
        try:
            result = await self._run_workflow(
                chunks,
                scope=request.scope,
                api_provider=execution_context.provider_selection_id,
                model_name=execution_context.model_id,
                game_name=request.game_name,
                target_language=request.target_language,
                reasoning_language=request.reasoning_language,
                description_language=request.description_language,
                project_summary=request.project_summary,
                runtime=execution_context.provider_runtime,
            )
        except Exception:
            partial = getattr(self.workflow, "last_partial_snapshot", None)
            if partial is not None:
                self.last_debug_snapshot = {
                    **partial,
                    "model_execution": self.usage_ledger.summary(),
                    "corpus_read_amplification": meter.snapshot(),
                }
            raise
        self._check_cancelled(execution_context)
        self.last_debug_snapshot = self._debug_snapshot(result, meter)
        draft = self._project_v3(request, chunks, result)
        diagnostics = dict(draft.diagnostics)
        diagnostics["model_execution"] = self.usage_ledger.summary()
        diagnostics["corpus_read_amplification"] = meter.snapshot()
        draft = draft.model_copy(update={"diagnostics": diagnostics})
        self._emit(execution_context, "context_research.completed", {
            "request_id": request.request_id,
            "backend": "context-workflow-v3",
            "event_chain_count": len(draft.event_chains),
            "entity_count": len(draft.entities),
        })
        execution_context.usage.record(
            "context_research.completed",
            backend="context-workflow-v3",
            model_calls=dict(getattr(result, "model_calls", {}) or {}),
            model_execution=self.usage_ledger.summary(),
            corpus_read_amplification=meter.snapshot(),
        )
        return draft

    def replay(
        self,
        request: ContextAnalysisRequest,
        snapshot: dict[str, Any],
    ) -> ContextResearchDraft:
        """Recompile a persisted paid-stage snapshot without model calls."""

        if snapshot.get("schema_version") != "context-workflow-v3-debug-v1":
            raise ValueError("unsupported Workflow v3 debug snapshot")
        chunks = self._chunks(request)
        result = self._result_from_snapshot(snapshot)
        draft = self._project_v3(request, chunks, result)
        diagnostics = {
            **dict(draft.diagnostics),
            "model_execution": dict(snapshot.get("model_execution") or {}),
            "corpus_read_amplification": dict(
                snapshot.get("corpus_read_amplification") or {}
            ),
            "replayed_from_debug_snapshot": True,
        }
        return draft.model_copy(update={"diagnostics": diagnostics})

    @classmethod
    def _project_v3(cls, request, chunks, result) -> ContextResearchDraft:
        if result.projection is None or result.catalog is None:
            raise ContextResearchUnsupported("Workflow v3 returned no global projection")
        units = cls._core_units(chunks)
        unit_sources = cls._unit_sources(chunks)
        routes = cls._routes(result)
        missing_route_ids = sorted(set(units) - set(routes))
        unknown_route_ids = sorted(set(routes) - set(units))
        if missing_route_ids or unknown_route_ids:
            raise ValueError(
                "Workflow v3 route coverage mismatch: "
                f"missing={missing_route_ids}, unknown={unknown_route_ids}"
            )
        entities = cls._entities(result.extractions, units)
        events = cls._catalog_events(result, unit_sources, entities)
        entities, events, entity_diagnostics = normalize_compiled_entities(
            entities, events, units,
        )
        entities = cls._attach_event_participation(entities, events)
        narratives = cls._narratives(routes, units, unit_sources)
        assets = cls._reference_assets(routes, units, unit_sources)
        unresolved = tuple(cls._unresolved(result, unit_sources))
        proposed_context = str(
            result.catalog.diagnostics.get("universal_translation_context") or ""
        )
        universal_context = build_universal_translation_context(
            request,
            events,
            narratives,
            entities,
            proposed_text=proposed_context,
        )
        covered = {
            source_id
            for item in (*narratives, *entities, *events, *assets, *unresolved)
            for source_id in item.source_item_ids
        }
        covered.update(universal_context.source_item_ids)
        uncovered_source_item_ids = [
            source_id for source_id in cls._request_source_ids(request)
            if source_id not in covered
        ]
        publication = evaluate_context_publication(
            unresolved_count=len(unresolved),
            uncovered_source_item_count=len(uncovered_source_item_ids),
        )
        diagnostics = {
            "adapter": "context-workflow-v3",
            "workflow_version": "context-workflow-v3",
            "project_id": request.project_id,
            "model": {
                "route_resolution": {
                    "content_roles": {
                        unit_id: route.content_role for unit_id, route in routes.items()
                    },
                    "delivery_routes": {
                        unit_id: route.delivery_route for unit_id, route in routes.items()
                    },
                },
            },
            "tree_v2_diagnostics": dict(result.diagnostics),
            "model_calls": dict(result.model_calls),
            "entity_normalization": entity_diagnostics,
            "uncovered_source_item_ids": uncovered_source_item_ids,
            "run": {
                "status": publication.status,
                "publishable": publication.publishable,
                "coverage": {
                    "owned_unit_count": len(units),
                    "routed_unit_count": len(routes),
                    "complete": publication.coverage_complete,
                    "uncovered_source_item_count": len(uncovered_source_item_ids),
                    "uncovered_source_items_block_publication": True,
                },
            },
        }
        return ContextResearchDraft(
            archive_narratives=narratives,
            entities=entities,
            event_chains=events,
            reference_assets=assets,
            unresolved=unresolved,
            universal_translation_context=universal_context,
            diagnostics=diagnostics,
        ).validate_against(request)

    @staticmethod
    def _core_units(chunks) -> dict[str, LocalTextUnit]:
        return {
            unit.unit_id: unit
            for chunk in chunks
            for unit in chunk.core_units
        }

    @staticmethod
    def _routes(result) -> dict[str, UnitRoute]:
        routes = {
            route.local_unit_id: route
            for extraction in result.extractions
            for route in extraction.unit_routes
        }
        if len(routes) != sum(len(item.unit_routes) for item in result.extractions):
            raise ValueError("Workflow v3 produced duplicate unit routes")
        return routes

    @classmethod
    def _narratives(cls, routes, units, unit_sources):
        return tuple(
            ArchiveNarrative(
                narrative_id=f"archive:{unit_id}",
                summary=route.summary or cls._unit_summary(units[unit_id]),
                source_item_ids=unit_sources[unit_id],
            )
            for unit_id, route in routes.items()
            if route.content_role == "background_narrative"
        )

    @classmethod
    def _reference_assets(cls, routes, units, unit_sources):
        return tuple(
            ReferenceAsset(
                asset_id=f"asset:{unit_id}",
                name=cls._unit_name(units[unit_id]),
                description=route.summary,
                local_unit_id=unit_id,
                source_item_ids=unit_sources[unit_id],
            )
            for unit_id, route in routes.items()
            if route.delivery_route == "reference"
        )

    @classmethod
    def _entities(cls, extractions, units) -> tuple[ResearchEntity, ...]:
        values: list[ResearchEntity] = []
        known_sources = {
            item.source_item_id
            for unit in units.values()
            for item in unit.items
        }
        for extraction in extractions:
            for contribution in extraction.entities:
                if cls._dynamic_entity(contribution.name):
                    continue
                metrics = calculate_entity_frequency(
                    contribution.name, (), units,
                )
                if not metrics.local_unit_ids:
                    continue
                evidence_ids = tuple(dict.fromkeys(
                    evidence.source_item_id
                    for evidence in contribution.evidence
                    if evidence.source_item_id in known_sources
                ))
                if not evidence_ids:
                    continue
                source_ids = tuple(dict.fromkeys((
                    *(
                        item.source_item_id
                        for unit_id in metrics.local_unit_ids
                        for item in units[unit_id].items
                    ),
                    *evidence_ids,
                )))
                values.append(ResearchEntity(
                    entity_id=f"entity_v3_{len(values)}",
                    name=contribution.name,
                    entity_type=_ENTITY_TYPE_MAP.get(contribution.entity_type, "other"),
                    summary=contribution.description or contribution.name,
                    importance="supporting",
                    mention_count=metrics.mention_count,
                    local_unit_ids=metrics.local_unit_ids,
                    local_unit_coverage=metrics.local_unit_coverage,
                    source_files=metrics.source_files,
                    file_spread=metrics.file_spread,
                    frequency_grade=metrics.frequency_grade,
                    source_item_ids=source_ids,
                    evidence=(EvidenceReference(source_item_ids=evidence_ids),),
                ))
        return tuple(values)

    @classmethod
    def _catalog_events(cls, result, unit_sources, entities):
        fragments = {
            fragment.fragment_id: fragment
            for extraction in result.extractions
            for fragment in extraction.local_fragments
        }
        events: list[EventChain] = []
        for group in result.catalog.catalog.groups:
            for sequence, fragment_id in enumerate(group.fragment_ids):
                fragment = fragments[fragment_id]
                local_unit_ids = tuple(fragment.unit_ids)
                source_ids = cls._sources_for_units(local_unit_ids, unit_sources)
                entity_ids = tuple(
                    entity.entity_id
                    for entity in entities
                    if set(entity.local_unit_ids) & set(local_unit_ids)
                )
                events.append(EventChain(
                    chain_id=group.group_id,
                    event=fragment.summary,
                    sequence=sequence,
                    local_unit_ids=local_unit_ids,
                    entity_ids=entity_ids,
                    source_item_ids=source_ids,
                ))
        return tuple(events)

    @staticmethod
    def _attach_event_participation(entities, events):
        by_entity: dict[str, list[str]] = {}
        for event in events:
            for entity_id in event.entity_ids:
                chain_ids = by_entity.setdefault(entity_id, [])
                if event.chain_id not in chain_ids:
                    chain_ids.append(event.chain_id)
        return tuple(
            entity.model_copy(update={
                "event_chain_ids": tuple(by_entity.get(entity.entity_id, ())),
                "event_participation_count": len(by_entity.get(entity.entity_id, ())),
            })
            for entity in entities
        )

    @staticmethod
    def _unit_name(unit: LocalTextUnit) -> str:
        return next(
            (str(item.item_key) for item in unit.items if item.item_key),
            unit.unit_key.split("::", 1)[-1],
        )

    @staticmethod
    def _unit_summary(unit: LocalTextUnit) -> str:
        text = " ".join(str(item.source_text) for item in unit.items).strip()
        return text[:999] + "…" if len(text) > 1_000 else text

    @staticmethod
    def _dynamic_entity(value: str) -> bool:
        normalized = re.sub(r"§(?:!|[A-Za-z0-9])", "", value).casefold().strip()
        return bool(
            re.fullmatch(r"\[[a-z_]\w*\.[^\]]+\]", normalized)
            or re.fullmatch(r"\$[a-z_]\w*\$", normalized)
            or "dynamic" in normalized
            or normalized in {"root polity", "root empire", "root country"}
        )

    @staticmethod
    def _read_meter(request, chunks) -> CorpusReadMeter:
        meter = CorpusReadMeter(request.source_items)
        for chunk in chunks:
            meter.observe(
                "read_units",
                {
                    "units": [
                        {
                            "ownership": (
                                "owned" if unit in chunk.core_units else "context_only"
                            ),
                            "entries": [
                                {
                                    "source_item_id": item.source_item_id,
                                    "text": item.source_text,
                                }
                                for item in unit.items
                            ],
                        }
                        for unit in (*chunk.core_units, *chunk.edge_units)
                    ],
                },
                actor_role="workflow_v3_chunk_extractor",
            )
        return meter

    def _debug_snapshot(self, result, meter: CorpusReadMeter) -> dict[str, Any]:
        """Capture paid model outputs before deterministic assembly can fail."""

        return {
            "schema_version": "context-workflow-v3-debug-v1",
            "extractions": [item.model_dump(mode="json") for item in result.extractions],
            "catalog": (
                result.catalog.model_dump(mode="json") if result.catalog else None
            ),
            "projection": (
                result.projection.model_dump(mode="json") if result.projection else None
            ),
            "translation_contexts": [
                item.model_dump(mode="json") for item in result.translation_contexts
            ],
            "model_calls": dict(result.model_calls),
            "workflow_diagnostics": dict(result.diagnostics),
            "model_execution": self.usage_ledger.summary(),
            "corpus_read_amplification": meter.snapshot(),
        }

    @staticmethod
    def _result_from_snapshot(snapshot: dict[str, Any]) -> ContextTreeV2WorkflowResult:
        catalog = snapshot.get("catalog")
        projection = snapshot.get("projection")
        return ContextTreeV2WorkflowResult(
            extractions=tuple(
                ContextTreeV2Extraction.model_validate(item)
                for item in snapshot.get("extractions", ())
            ),
            catalog=TreeCatalogResult.model_validate(catalog) if catalog else None,
            projection=(
                TreeProjectionResult.model_validate(projection) if projection else None
            ),
            translation_contexts=tuple(
                TranslationContextProjection.model_validate(item)
                for item in snapshot.get("translation_contexts", ())
            ),
            model_calls={
                str(key): int(value)
                for key, value in (snapshot.get("model_calls") or {}).items()
            },
            diagnostics=dict(snapshot.get("workflow_diagnostics") or {}),
        )


__all__ = ["ContextResearchWorkflowV3"]
