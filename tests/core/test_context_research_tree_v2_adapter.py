"""Tests for the deliberately small Tree v2 research projection."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import EventChainContribution, SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
    ContextResearchCancelled,
    UnknownSourceItemReference,
)
from scripts.core.services.context_research_tree_v2_adapter import (
    ContextResearchTreeV2Adapter,
    ContextResearchUnsupported,
)
from scripts.core.services.context_tree_v2_contract import (
    ContextTreeCatalog,
    ContextTreeV2Extraction,
    LocalFragment,
    ProjectedUnitRoute,
    TreeCatalogResult,
    TreeProjectionResult,
    UnitRoute,
)


class FakeWorkflow:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, chunks, **kwargs):
        self.calls.append((chunks, kwargs))
        return self.result


class Cancelled:
    def is_cancelled(self):
        return True


def _source_items():
    return (
        SourceItem(
            source_item_id="source-1", relative_path="events/story.yml",
            item_key="story.0.desc", source_order=0,
            source_text="The envoy receives a warning.",
        ),
        SourceItem(
            source_item_id="source-2", relative_path="events/story.yml",
            item_key="story.1.name", source_order=1,
            source_text="Envoy", 
        ),
    )


def _chunk():
    items = _source_items()
    return ContextUnitChunk(
        core_units=(
            LocalTextUnit("unit_0", "events/story.yml::story.0", (items[0],)),
            LocalTextUnit("unit_1", "events/story.yml::story.1", (items[1],)),
        ),
        edge_units=(),
    )


def _result():
    extraction = ContextTreeV2Extraction(
        local_fragments=(LocalFragment(
            fragment_id="fragment-1", summary="The warning arrives.", unit_ids=["unit_0"],
        ),),
        unit_routes=(
            UnitRoute(local_unit_id="unit_0", route="narrative", fragment_ids=["fragment-1"]),
            UnitRoute(local_unit_id="unit_1", route="reference_asset"),
        ),
        events=({
            "chain_id": "chain-1", "event": "The warning arrives.", "sequence": 0,
            "evidence": [{"source_item_id": "source-1"}],
        },),
    )
    return SimpleNamespace(
        extractions=(extraction,),
        catalog=TreeCatalogResult(catalog=ContextTreeCatalog()),
        projection=TreeProjectionResult(unit_routes=(
            ProjectedUnitRoute(
                local_unit_id="unit_0", route="narrative", fragment_ids=["fragment-1"],
                group_ids=[], receives_event_context=False,
            ),
            ProjectedUnitRoute(
                local_unit_id="unit_1", route="reference_asset", receives_event_context=False,
            ),
        )),
        diagnostics={"schema_version": "context-tree-v2"},
    )


@pytest.mark.asyncio
async def test_adapter_reuses_tree_v2_and_preserves_source_evidence():
    workflow = FakeWorkflow(_result())
    request = ContextAnalysisRequest(project_id="project-1", source_items=_source_items())
    draft = await ContextResearchTreeV2Adapter(workflow).analyze(
        request, AgentExecutionContext(provider_selection_id="local", model_id="model-a"),
    )

    assert draft.archive_narratives == ()
    assert draft.event_chains[0].chain_id == "chain-1"
    assert draft.event_chains[0].source_item_ids == ("source-1",)
    assert draft.reference_assets[0].local_unit_id == "unit_1"
    assert draft.reference_assets[0].receives_event_context is False
    assert draft.diagnostics["project_id"] == "project-1"
    assert draft.diagnostics["unsupported_gaps"] == ["archive_narrative_mapping"]
    assert workflow.calls[0][1]["api_provider"] == "local"
    assert workflow.calls[0][1]["model_name"] == "model-a"


@pytest.mark.asyncio
async def test_adapter_runs_legacy_sync_workflow_off_the_event_loop_thread():
    main_thread = threading.get_ident()

    class ThreadRecordingWorkflow(FakeWorkflow):
        def run(self, chunks, **kwargs):
            self.worker_thread = threading.get_ident()
            return super().run(chunks, **kwargs)

    workflow = ThreadRecordingWorkflow(_result())
    await ContextResearchTreeV2Adapter(workflow).analyze(
        ContextAnalysisRequest(project_id="project-1", source_items=_source_items()),
        AgentExecutionContext(provider_selection_id="local"),
    )

    assert workflow.worker_thread != main_thread


@pytest.mark.asyncio
async def test_adapter_fails_closed_for_unknown_tree_evidence():
    result = _result()
    result.extractions[0].events = (EventChainContribution(
        chain_id="chain-unknown", event="Unknown evidence.", sequence=0,
        evidence=[{"source_item_id": "source-missing"}],
    ),)
    with pytest.raises((UnknownSourceItemReference, ValidationError)):
        await ContextResearchTreeV2Adapter(FakeWorkflow(result)).analyze(
            ContextAnalysisRequest(project_id="project-1", source_items=_source_items()),
            AgentExecutionContext(provider_selection_id="local"),
        )


@pytest.mark.asyncio
async def test_adapter_has_explicit_boundaries_for_cancellation_and_id_only_requests():
    request = ContextAnalysisRequest(project_id="project-1", source_items=_source_items())
    with pytest.raises(ContextResearchCancelled):
        await ContextResearchTreeV2Adapter(FakeWorkflow(_result())).analyze(
            request,
            AgentExecutionContext(provider_selection_id="local", cancellation=Cancelled()),
        )

    with pytest.raises(ContextResearchUnsupported, match="source_items"):
        await ContextResearchTreeV2Adapter(FakeWorkflow(_result())).analyze(
            ContextAnalysisRequest(project_id="project-1", source_item_ids=("source-1",)),
            AgentExecutionContext(provider_selection_id="local"),
        )
