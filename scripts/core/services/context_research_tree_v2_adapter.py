"""Thin, fail-closed adapter from Tree v2 to the research contract."""

from __future__ import annotations

import asyncio
import inspect
from collections import OrderedDict
from typing import Any, Callable, Sequence

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.services.context_chunking_policy import ContextChunkingPolicy, ContextUnitChunk
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
    ContextResearchCancelled,
    ContextResearchContractError,
    ContextResearchDraft,
    EventChain,
    ReferenceAsset,
    Unresolved,
    UnknownSourceItemReference,
)
from scripts.core.services.context_tree_v2_contract import ContextTreeV2Extraction
from scripts.core.services.context_tree_v2_workflow_service import ContextTreeV2WorkflowService


class ContextResearchUnsupported(ContextResearchContractError):
    """Raised when Tree v2 cannot represent a research operation faithfully."""


class ContextResearchTreeV2Adapter:
    """Expose the existing synchronous Tree v2 workflow as an async backend.

    No Tree v2 workflow methods are changed here.  The adapter only projects
    evidence already present in extraction/projection results and refuses to
    invent source IDs or delivery semantics.
    """

    def __init__(
        self,
        workflow: ContextTreeV2WorkflowService | Any | None = None,
        *,
        handler_factory: Callable[..., Any] | None = None,
    ) -> None:
        if workflow is None:
            if handler_factory is None:
                raise ValueError("workflow or handler_factory is required")
            workflow = ContextTreeV2WorkflowService(handler_factory=handler_factory)
        self.workflow = workflow

    async def analyze(
        self,
        request: ContextAnalysisRequest,
        execution_context: AgentExecutionContext,
    ) -> ContextResearchDraft:
        """Run Tree v2 and project only source-grounded research records."""

        self._check_cancelled(execution_context)
        if request.scope.value == "terms_only":
            raise ContextResearchUnsupported(
                "Tree v2 terms-only output is not representable by the research draft"
            )
        chunks = self._chunks(request)
        self._emit(execution_context, "context_research.started", {
            "request_id": request.request_id,
            "source_item_count": len(request.known_source_item_ids),
        })
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
        self._check_cancelled(execution_context)
        draft = self._project(request, chunks, result)
        self._emit(execution_context, "context_research.completed", {
            "request_id": request.request_id,
            "archive_narrative_count": len(draft.archive_narratives),
            "event_chain_count": len(draft.event_chains),
            "reference_asset_count": len(draft.reference_assets),
            "unresolved_count": len(draft.unresolved),
        })
        self._record_usage(execution_context, result)
        return draft

    async def _run_workflow(
        self,
        chunks: Sequence[ContextUnitChunk],
        **kwargs: Any,
    ) -> Any:
        """Keep the async research boundary responsive around legacy Tree v2."""

        run = self.workflow.run
        if inspect.iscoroutinefunction(run):
            return await run(chunks, **kwargs)
        result = await asyncio.to_thread(run, chunks, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _chunks(self, request: ContextAnalysisRequest) -> tuple[ContextUnitChunk, ...]:
        if request.chunks is not None:
            if not request.chunks:
                raise ContextResearchUnsupported("an empty Tree v2 chunk set has no research semantics")
            return request.chunks
        if not request.source_items:
            raise ContextResearchUnsupported(
                "Tree v2 adaptation requires source_items, not source IDs alone"
            )
        units = ContextLocalUnitBuilder.build(request.source_items)
        return ContextChunkingPolicy.unit_chunks(units)

    @classmethod
    def _project(
        cls,
        request: ContextAnalysisRequest,
        chunks: Sequence[ContextUnitChunk],
        result: Any,
    ) -> ContextResearchDraft:
        if not hasattr(result, "extractions"):
            raise ContextResearchUnsupported("Tree v2 result has no extraction evidence")
        unit_sources = cls._unit_sources(chunks)
        events = cls._events(result.extractions)
        assets = cls._assets(result, unit_sources)
        unresolved = cls._unresolved(result, unit_sources)
        draft = ContextResearchDraft(
            source_item_ids=cls._request_source_ids(request),
            # Tree v2 fragments are delivery-capable event fragments.  The
            # old contract does not prove archive-only narrative semantics.
            archive_narratives=(),
            event_chains=tuple(events),
            reference_assets=tuple(assets),
            unresolved=tuple(unresolved),
            diagnostics={
                "adapter": "context-tree-v2",
                "project_id": request.project_id,
                "research_question": request.research_question,
                "delivery_projection": "tree-v2 routes are not copied into archive narratives",
                "unsupported_gaps": ["archive_narrative_mapping"],
                "tree_v2_diagnostics": dict(getattr(result, "diagnostics", {}) or {}),
            },
        )
        return draft.validate_against(request)

    @staticmethod
    def _request_source_ids(request: ContextAnalysisRequest) -> tuple[str, ...]:
        return request.source_item_ids or tuple(
            item.source_item_id for item in request.source_items
        )

    @staticmethod
    def _unit_sources(chunks: Sequence[ContextUnitChunk]) -> dict[str, tuple[str, ...]]:
        sources: dict[str, tuple[str, ...]] = {}
        for chunk in chunks:
            for unit in (*chunk.core_units, *chunk.edge_units):
                ids = tuple(item.source_item_id for item in unit.items)
                previous = sources.get(unit.unit_id)
                if previous is not None and previous != ids:
                    raise ContextResearchContractError(
                        f"Tree v2 unit {unit.unit_id} has conflicting source memberships"
                    )
                sources[unit.unit_id] = ids
        return sources

    @staticmethod
    def _events(extractions: Sequence[ContextTreeV2Extraction]) -> list[EventChain]:
        values: "OrderedDict[tuple[str, int], EventChain]" = OrderedDict()
        for extraction in extractions:
            for event in extraction.events:
                identity = (event.chain_id, event.sequence)
                source_ids = tuple(dict.fromkeys(
                    source_id
                    for evidence in event.evidence
                    for source_id in (evidence.source_item_id,)
                ))
                if not source_ids:
                    raise UnknownSourceItemReference(
                        f"event {event.chain_id} has no source evidence"
                    )
                previous = values.get(identity)
                if previous is not None:
                    if previous.event != event.event:
                        raise ContextResearchContractError(
                            f"Tree v2 event identity has conflicting text: {event.chain_id}:{event.sequence}"
                        )
                    merged_ids = tuple(dict.fromkeys((*previous.source_item_ids, *source_ids)))
                    values[identity] = previous.model_copy(update={"source_item_ids": merged_ids})
                    continue
                values[identity] = EventChain(
                    chain_id=event.chain_id,
                    event=event.event,
                    sequence=event.sequence,
                    source_item_ids=source_ids,
                )
        return list(values.values())

    @classmethod
    def _assets(
        cls,
        result: Any,
        unit_sources: dict[str, tuple[str, ...]],
    ) -> list[ReferenceAsset]:
        projection = getattr(result, "projection", None)
        if projection is None:
            return []
        values: list[ReferenceAsset] = []
        for route in projection.unit_routes:
            if route.route != "reference_asset":
                continue
            unit_id = route.local_unit_id
            values.append(ReferenceAsset(
                asset_id=f"asset:{unit_id}",
                name=unit_id,
                local_unit_id=unit_id,
                source_item_ids=cls._sources_for_units((unit_id,), unit_sources),
            ))
        return values

    @classmethod
    def _unresolved(
        cls,
        result: Any,
        unit_sources: dict[str, tuple[str, ...]],
    ) -> list[Unresolved]:
        values: list[Unresolved] = []
        for extraction in getattr(result, "extractions", ()):
            for reference in extraction.unresolved_fragment_references:
                values.append(Unresolved(
                    unresolved_id=f"fragment-reference:{reference.local_unit_id}:{reference.fragment_id}",
                    reference_type="fragment",
                    source_id=reference.local_unit_id,
                    target_id=reference.fragment_id,
                    reason=reference.reason,
                    repair_attempts=reference.repair_attempts,
                    source_item_ids=cls._sources_for_units((reference.local_unit_id,), unit_sources),
                ))
        catalog = getattr(result, "catalog", None)
        if catalog is not None:
            for fragment_id in catalog.catalog.unresolved_fragment_ids:
                values.append(Unresolved(
                    unresolved_id=f"catalog-fragment:{fragment_id}",
                    reference_type="fragment",
                    source_id="tree-v2-catalog",
                    target_id=fragment_id,
                    reason="Tree v2 catalog retained an unresolved fragment.",
                    repair_attempts=catalog.repair_count,
                    source_item_ids=cls._sources_for_fragment(fragment_id, result, unit_sources),
                ))
        return values

    @staticmethod
    def _sources_for_fragment(
        fragment_id: str,
        result: Any,
        unit_sources: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        for extraction in getattr(result, "extractions", ()):
            for fragment in extraction.local_fragments:
                if fragment.fragment_id == fragment_id:
                    return ContextResearchTreeV2Adapter._sources_for_units(
                        fragment.unit_ids, unit_sources,
                    )
        raise UnknownSourceItemReference(
            f"unresolved catalog fragment has no source evidence: {fragment_id}"
        )

    @staticmethod
    def _sources_for_units(
        unit_ids: Sequence[str],
        unit_sources: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        source_ids = tuple(dict.fromkeys(
            source_id
            for unit_id in unit_ids
            for source_id in unit_sources.get(unit_id, ())
        ))
        if not source_ids:
            raise UnknownSourceItemReference(
                f"Tree v2 references unknown or empty units: {list(unit_ids)}"
            )
        return source_ids

    @staticmethod
    def _check_cancelled(context: AgentExecutionContext) -> None:
        if context.cancellation.is_cancelled():
            raise ContextResearchCancelled("context research cancelled")

    @staticmethod
    def _emit(
        context: AgentExecutionContext,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        context.events.emit(event, payload)

    @staticmethod
    def _record_usage(context: AgentExecutionContext, result: Any) -> None:
        model_calls = dict(getattr(result, "model_calls", {}) or {})
        context.usage.record(
            "context_research.completed",
            model_calls=model_calls,
        )


__all__ = ["ContextResearchTreeV2Adapter", "ContextResearchUnsupported"]
