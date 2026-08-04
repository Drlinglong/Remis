"""In-memory v2 analysis orchestration with no assignment or synthesis stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from scripts.core.neologism_extraction import AnalysisScope
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_tree_v2_catalog_service import ContextTreeV2CatalogService
from scripts.core.services.context_tree_v2_contract import (
    ContextTreeV2Extraction,
    TREE_V2_CHECKPOINT_COMPATIBILITY_VERSION,
    TREE_V2_PROMPT_VERSION,
    TREE_V2_SCHEMA_VERSION,
    TranslationContextProjection,
    TreeCatalogResult,
    TreeProjectionResult,
)
from scripts.core.services.context_tree_v2_context_service import ContextTreeV2ContextService
from scripts.core.services.context_tree_v2_extraction_service import ContextTreeV2ExtractionService
from scripts.core.services.context_tree_v2_projection_service import ContextTreeV2ProjectionService


@dataclass(frozen=True)
class ContextTreeV2WorkflowResult:
    """Pure workflow output ready for a later storage/publishing adapter."""

    extractions: tuple[ContextTreeV2Extraction, ...]
    catalog: TreeCatalogResult | None
    projection: TreeProjectionResult | None
    translation_contexts: tuple[TranslationContextProjection, ...]
    model_calls: dict[str, int]
    diagnostics: dict[str, Any]


class ContextTreeV2WorkflowService:
    """Coordinate v2 stages while leaving persistence to a separate integration."""

    SCHEMA_VERSION = TREE_V2_SCHEMA_VERSION
    PROMPT_VERSION = TREE_V2_PROMPT_VERSION
    CHECKPOINT_COMPATIBILITY_VERSION = TREE_V2_CHECKPOINT_COMPATIBILITY_VERSION

    def __init__(
        self,
        *,
        handler_factory: Callable[..., Any],
        extractor_factory: Callable[[Any], ContextTreeV2ExtractionService] = ContextTreeV2ExtractionService,
        catalog_factory: Callable[[Any], ContextTreeV2CatalogService] = ContextTreeV2CatalogService,
        usage_ledger: Any | None = None,
    ) -> None:
        self.handler_factory = handler_factory
        self.extractor_factory = extractor_factory
        self.catalog_factory = catalog_factory
        self.usage_ledger = usage_ledger

    def run(
        self,
        chunks: Sequence[ContextUnitChunk],
        *,
        scope: AnalysisScope = AnalysisScope.NARRATIVE_CONTEXT,
        api_provider: str = "local",
        model_name: str | None = None,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
        description_language: str = "en",
        project_summary: str = "",
    ) -> ContextTreeV2WorkflowResult:
        scope = AnalysisScope(scope)
        extraction_results = tuple(
            self._extract_chunk(
                chunk,
                scope=scope,
                api_provider=api_provider,
                model_name=model_name,
                game_name=game_name,
                target_language=target_language,
                reasoning_language=reasoning_language,
            )
            for chunk in chunks
        )
        extraction_calls = len(extraction_results) + sum(
            int(result.diagnostics.get("repair_count", 0))
            for result in extraction_results
        )
        if scope is AnalysisScope.TERMS_ONLY:
            return ContextTreeV2WorkflowResult(
                extractions=extraction_results,
                catalog=None,
                projection=None,
                translation_contexts=(),
                model_calls={
                    "extraction": extraction_calls,
                    "fragment_repair": extraction_calls - len(extraction_results),
                    "catalog": 0,
                    "assignment": 0,
                    "synthesis": 0,
                },
                diagnostics={
                    "schema_version": TREE_V2_SCHEMA_VERSION,
                    "prompt_version": TREE_V2_PROMPT_VERSION,
                    "checkpoint_compatibility_version": TREE_V2_CHECKPOINT_COMPATIBILITY_VERSION,
                    "catalog_skipped": True,
                    "entity_summary_skipped": True,
                    "event_context_skipped": True,
                },
            )

        fragments = [
            fragment
            for extraction in extraction_results
            for fragment in extraction.local_fragments
        ]
        routes = [
            route
            for extraction in extraction_results
            for route in extraction.unit_routes
        ]
        expected_unit_ids = [
            unit.unit_id
            for chunk in chunks
            for unit in chunk.core_units
        ]
        catalog = self._catalog(
            fragments,
            chunks,
            api_provider=api_provider,
            model_name=model_name,
            description_language=description_language,
        )
        projection = ContextTreeV2ProjectionService.project(
            routes,
            catalog,
            expected_unit_ids=expected_unit_ids,
        )
        translation_contexts = ContextTreeV2ContextService.project_all_translation_contexts(
            projection,
            catalog.catalog,
            fragments,
            project_summary=project_summary,
        )
        catalog_calls = int(catalog.diagnostics.get("model_call_count", 0))
        return ContextTreeV2WorkflowResult(
            extractions=extraction_results,
            catalog=catalog,
            projection=projection,
            translation_contexts=translation_contexts,
            model_calls={
                "extraction": extraction_calls,
                "fragment_repair": extraction_calls - len(extraction_results),
                "catalog": catalog_calls,
                "assignment": 0,
                "synthesis": 0,
            },
            diagnostics={
                "schema_version": TREE_V2_SCHEMA_VERSION,
                "prompt_version": TREE_V2_PROMPT_VERSION,
                "checkpoint_compatibility_version": TREE_V2_CHECKPOINT_COMPATIBILITY_VERSION,
                "fragment_count": len(fragments),
                "unit_route_count": len(routes),
                "unresolved_fragment_reference_count": len(
                    projection.unresolved_fragment_references
                ) + sum(
                    len(result.unresolved_fragment_references)
                    for result in extraction_results
                ),
                "sibling_group_order_semantics": "unordered",
                "group_fragment_order_semantics": "ordered",
            },
        )

    def _extract_chunk(
        self,
        chunk: ContextUnitChunk,
        *,
        scope: AnalysisScope,
        api_provider: str,
        model_name: str | None,
        game_name: str,
        target_language: str,
        reasoning_language: str,
    ) -> ContextTreeV2Extraction:
        handler = self.handler_factory(api_provider, model_name=model_name)
        try:
            return self.extractor_factory(handler).extract_structured(
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
            if self.usage_ledger is not None:
                self.usage_ledger.capture(handler, "tree_v2_extraction")

    def _catalog(
        self,
        fragments: Sequence[Any],
        chunks: Sequence[ContextUnitChunk],
        *,
        api_provider: str,
        model_name: str | None,
        description_language: str,
    ) -> TreeCatalogResult:
        handler = self.handler_factory(api_provider, model_name=model_name)
        metadata = [chunk.edge_metadata for chunk in chunks]
        try:
            return self.catalog_factory(handler).build_catalog(
                fragments,
                chunk_edge_metadata=metadata,
                description_language=description_language,
            )
        finally:
            if self.usage_ledger is not None:
                self.usage_ledger.capture(handler, "tree_v2_catalog")
