"""Invariants for the Agent context research boundary."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ArchiveNarrative,
    CancellationSignal,
    ContextAnalysisRequest,
    ContextResearchBackend,
    ContextResearchDraft,
    EventChain,
    EventSink,
    ReferenceAsset,
    Unresolved,
    UnknownSourceItemReference,
    UsageSink,
)


def _item(source_item_id: str = "source-1") -> SourceItem:
    return SourceItem(
        source_item_id=source_item_id,
        relative_path="events/story.yml",
        item_key="story.0.desc",
        source_order=0,
        source_text="The envoy receives a warning.",
    )


def test_execution_context_is_a_dependency_value_not_a_lifecycle_runner():
    context = AgentExecutionContext(provider_selection_id="local", model_id="model-a")

    assert context.provider_runtime is None
    assert context.cancellation.is_cancelled() is False
    assert not any(name in AgentExecutionContext.__dict__ for name in ("run", "resume", "fork"))
    assert isinstance(context.cancellation, CancellationSignal)
    assert isinstance(context.usage, UsageSink)
    assert isinstance(context.events, EventSink)


def test_request_requires_a_nonempty_and_ordered_source_snapshot():
    request = ContextAnalysisRequest(project_id="project-1", source_items=(_item(),))
    assert request.known_source_item_ids == frozenset({"source-1"})
    assert tuple(item.source_item_id for item in request.source_items) == ("source-1",)

    with pytest.raises(ValidationError):
        ContextAnalysisRequest(project_id="project-1", source_items=(_item(),), source_item_ids=("other",))
    with pytest.raises(ValidationError):
        ContextAnalysisRequest(project_id="project-1", source_item_ids=())
    with pytest.raises(ValidationError):
        ContextAnalysisRequest(project_id=" ", source_items=(_item(),))
    assert request.research_question


def test_archive_narrative_and_reference_asset_cannot_receive_event_context():
    narrative = ArchiveNarrative(
        narrative_id="fragment-1",
        summary="A local narrative.",
        source_item_ids=("source-1",),
    )
    asset = ReferenceAsset(
        asset_id="asset-1",
        name="Envoy",
        source_item_ids=("source-1",),
    )
    assert narrative.delivery_target is False
    assert asset.receives_event_context is False

    with pytest.raises(ValidationError):
        ArchiveNarrative(
            narrative_id="fragment-1",
            summary="A local narrative.",
            source_item_ids=("source-1",),
            delivery_target=True,
        )
    with pytest.raises(ValidationError):
        ReferenceAsset(
            asset_id="asset-1", name="Envoy", source_item_ids=("source-1",),
            receives_event_context=True,
        )


def test_draft_rejects_unknown_source_ids_and_unknown_archive_links():
    draft = ContextResearchDraft(
        source_item_ids=("source-1",),
        archive_narratives=(ArchiveNarrative(
            narrative_id="fragment-1", summary="A local narrative.",
            source_item_ids=("source-1",),
        ),),
        event_chains=(EventChain(
            chain_id="chain-1", event="The warning arrives.",
            source_item_ids=("source-1",), archive_context_ids=("fragment-1",),
        ),),
    )
    assert draft.validate_against(ContextAnalysisRequest(project_id="project-1", source_items=(_item(),))) is not None

    with pytest.raises(ValidationError, match="unknown source items"):
        ContextResearchDraft(
            source_item_ids=("source-1",),
            reference_assets=(ReferenceAsset(
                asset_id="asset-1", name="Envoy", source_item_ids=("unknown",),
            ),),
        )
    with pytest.raises(ValueError, match="unknown archive context"):
        ContextResearchDraft(
            source_item_ids=("source-1",),
            event_chains=(EventChain(
                chain_id="chain-1", event="An event.", source_item_ids=("source-1",),
                archive_context_ids=("missing",),
            ),),
        )


def test_draft_source_snapshot_is_only_the_union_of_referenced_evidence():
    request = ContextAnalysisRequest(
        project_id="project-1", source_items=(_item("source-1"), _item("source-2")),
    )
    draft = ContextResearchDraft(reference_assets=(ReferenceAsset(
        asset_id="asset-1", name="Envoy", source_item_ids=("source-1",),
    ),))

    validated = draft.validate_against(request)
    assert validated.source_item_ids == ("source-1",)
    assert validated.source_item_ids != tuple(request.known_source_item_ids)


def test_backend_protocol_is_async_and_unresolved_keeps_unknown_target_explicit():
    method = ContextResearchBackend.__dict__["analyze"]
    assert inspect.iscoroutinefunction(method)
    unresolved = Unresolved(
        unresolved_id="u-1", reference_type="fragment", source_id="unit-1",
        target_id="missing-fragment", reason="Absent after bounded repair.",
        source_item_ids=("source-1",), repair_attempts=1,
    )
    assert unresolved.target_id == "missing-fragment"
    assert unresolved.reference_id == unresolved.unresolved_id
