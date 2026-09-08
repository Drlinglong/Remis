"""Focused tests for the lightweight Context Archive workflow v3."""

from __future__ import annotations

from types import SimpleNamespace
import json

import pytest

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import EntityContribution, SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
)
from scripts.core.services.context_research_workflow_v3 import (
    ContextResearchWorkflowV3,
)
from scripts.core.services.context_workflow_v3_extraction import (
    ContextWorkflowV3ExtractionService,
)
from scripts.core.services.context_workflow_v3_catalog import (
    ContextWorkflowV3CatalogService,
)
from scripts.core.prompts.context_workflow_v3_prompt import workflow_v3_catalog_prompt
from scripts.core.services.context_tree_v2_contract import (
    ContextTreeCatalog,
    ContextTreeV2Extraction,
    LocalFragment,
    TreeCatalogResult,
    TreeGroup,
    TreeProjectionResult,
    TreeStory,
    UnitRoute,
)
from scripts.developer_tools.smoke_context_research_harness import (
    _persist_workflow_v3_snapshot,
    _workflow_v3_trace_reference,
)


class FakeWorkflow:
    def __init__(self, result):
        self.result = result

    def run(self, chunks, **kwargs):
        self.chunks = chunks
        self.kwargs = kwargs
        return self.result


def _items():
    return (
        SourceItem(
            source_item_id="source-1",
            relative_path="events/story.yml",
            item_key="story.1.desc",
            source_order=0,
            source_text="Envoy discovers a warning beneath the gate.",
        ),
        SourceItem(
            source_item_id="source-2",
            relative_path="events/story.yml",
            item_key="story.2.name",
            source_order=1,
            source_text="Envoy",
        ),
        SourceItem(
            source_item_id="source-3",
            relative_path="lore/story.yml",
            item_key="story_origin_desc",
            source_order=2,
            source_text="The gate predates the current empire.",
        ),
    )


def _chunk():
    items = _items()
    return ContextUnitChunk(
        core_units=(
            LocalTextUnit("unit_0", "events/story.yml::story.1", (items[0],)),
            LocalTextUnit("unit_1", "events/story.yml::story.2", (items[1],)),
            LocalTextUnit("unit_2", "lore/story.yml::story_origin", (items[2],)),
        ),
        edge_units=(),
    )


def test_v3_extraction_prompt_uses_requested_description_language():
    chunk = _chunk()
    messages = ContextWorkflowV3ExtractionService._request_messages(
        _items(), chunk.core_units, chunk.edge_units, chunk.edge_metadata,
        scope="narrative_context",
        game_name="Stellaris",
        target_language="zh-CN",
        reasoning_language="en",
        source_aliases={item.source_item_id: f"source_{index}" for index, item in enumerate(_items())},
        description_language="de",
    )

    assert "Description language: de" in messages[0]["content"]


def _result():
    extraction = ContextTreeV2Extraction(
        local_fragments=[LocalFragment(
            fragment_id="fragment_c0_1",
            summary="The envoy discovers a warning.",
            unit_ids=["unit_0"],
        )],
        unit_routes=[
            UnitRoute(
                local_unit_id="unit_0",
                content_role="event_narrative",
                delivery_route="event",
                summary="A concrete discovery.",
                fragment_ids=["fragment_c0_1"],
            ),
            UnitRoute(
                local_unit_id="unit_1",
                content_role="static_reference",
                delivery_route="reference",
                summary="The envoy title.",
            ),
            UnitRoute(
                local_unit_id="unit_2",
                content_role="background_narrative",
                delivery_route="none",
                summary="The gate's earlier history.",
            ),
        ],
        entities=[EntityContribution(
            name="Envoy",
            entity_type="person",
            description="A messenger who discovers the warning.",
            # Representative evidence can be broader than the literal-frequency
            # match set; assembly must retain it in the entity source union.
            evidence=[{"source_item_id": "source-3"}],
        )],
    )
    catalog = TreeCatalogResult(
        catalog=ContextTreeCatalog(
            stories=[TreeStory(story_id="story_main", group_ids=["chain_main"])],
            groups=[TreeGroup(
                group_id="chain_main", fragment_ids=["fragment_c0_1"],
            )],
        ),
        diagnostics={
            "universal_translation_context": "本模组围绕古老星门、使者警告与帝国危机展开，翻译应保持悬疑感、专名与事件因果一致。",
        },
    )
    return SimpleNamespace(
        extractions=(extraction,),
        catalog=catalog,
        projection=TreeProjectionResult(),
        translation_contexts=(),
        diagnostics={"schema_version": "context-workflow-v3"},
        model_calls={"extraction": 1, "catalog": 1},
    )


@pytest.mark.asyncio
async def test_workflow_v3_projects_three_axes_and_global_chain_deterministically():
    workflow = FakeWorkflow(_result())
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=_items(),
        chunks=(_chunk(),),
        description_language="zh-CN",
    )
    backend = ContextResearchWorkflowV3(workflow)
    draft = await backend.analyze(
        request,
        AgentExecutionContext(provider_selection_id="local", model_id="model-a"),
    )

    assert draft.event_chains[0].chain_id == "chain_main"
    assert draft.event_chains[0].local_unit_ids == ("unit_0",)
    assert draft.reference_assets[0].local_unit_id == "unit_1"
    assert draft.archive_narratives[0].narrative_id == "archive:unit_2"
    assert draft.entities[0].name == "Envoy"
    assert draft.entities[0].frequency_grade == "B"
    assert "source-3" in draft.entities[0].source_item_ids
    assert draft.universal_translation_context.generation == "lead_synthesized"
    resolution = draft.diagnostics["model"]["route_resolution"]
    assert resolution["content_roles"]["unit_2"] == "background_narrative"
    assert resolution["delivery_routes"]["unit_1"] == "reference"
    assert draft.diagnostics["corpus_read_amplification"]["value"] == pytest.approx(1.0)
    assert draft.diagnostics["model_execution"]["call_count"] == 0
    assert draft.diagnostics["run"] == {
        "status": "complete",
        "publishable": True,
        "coverage": {
            "owned_unit_count": 3,
            "routed_unit_count": 3,
            "complete": True,
            "uncovered_source_item_count": 0,
            "uncovered_source_items_block_publication": True,
        },
    }
    assert backend.last_debug_snapshot["model_calls"]["catalog"] == 1
    assert workflow.kwargs["description_language"] == "zh-CN"

    replayed = backend.replay(request, backend.last_debug_snapshot)
    assert replayed.event_chains == draft.event_chains
    assert replayed.entities == draft.entities
    assert replayed.diagnostics["replayed_from_debug_snapshot"] is True


@pytest.mark.asyncio
async def test_workflow_v3_marks_unresolved_draft_not_publishable():
    result = _result()
    result.catalog = result.catalog.model_copy(update={
        "catalog": result.catalog.catalog.model_copy(update={
            "unresolved_fragment_ids": ["fragment_c0_1"],
        }),
    })
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=_items(),
        chunks=(_chunk(),),
        description_language="zh-CN",
    )

    draft = await ContextResearchWorkflowV3(FakeWorkflow(result)).analyze(
        request,
        AgentExecutionContext(provider_selection_id="local", model_id="model-a"),
    )

    assert draft.unresolved
    assert draft.diagnostics["run"]["status"] == "incomplete"
    assert draft.diagnostics["run"]["publishable"] is False


def test_v3_catalog_uses_requested_description_language_for_context_and_repair():
    card = LocalFragment(
        fragment_id="fragment-de",
        summary="The envoy discovers a warning.",
        unit_ids=["unit-de"],
    )
    response = json.dumps({
        "stories": [],
        "groups": [],
        "unresolved_fragment_ids": ["fragment-de"],
        "universal_translation_context": "Eine düstere Geschichte über einen Boten, ein uraltes Tor und eine drohende Krise.",
    })
    captured = {}
    service = ContextWorkflowV3CatalogService(SimpleNamespace())
    def generate(messages, label):
        captured["messages"] = messages
        return response
    service._generate_v3 = generate

    result = service.build_catalog([card], description_language="de")
    prompt = "\n".join(item["content"] for item in captured["messages"])

    assert result.diagnostics["universal_translation_context"].startswith("Eine düstere")
    assert "Description language: de" in prompt
    assert "Simplified Chinese" not in prompt
    assert "in de" in service._repair_v3(ValueError("bad"), [card], "de")


def test_v3_catalog_repairs_summary_outside_the_50_to_100_character_contract():
    card = LocalFragment(fragment_id="fragment-1", summary="The envoy arrives.", unit_ids=["unit-1"])
    valid = json.dumps({
        "stories": [],
        "groups": [],
        "unresolved_fragment_ids": ["fragment-1"],
        "universal_translation_context": "A compact project overview covering the envoy, the warning, and the consequences of the road choice.",
    })
    service = ContextWorkflowV3CatalogService(SimpleNamespace())
    responses = iter([
        json.dumps({
            "stories": [], "groups": [], "unresolved_fragment_ids": ["fragment-1"],
            "universal_translation_context": "Too short.",
        }),
        valid,
    ])
    service._generate_v3 = lambda messages, label: next(responses)

    result = service.build_catalog([card])

    assert result.repair_count == 1
    assert result.diagnostics["universal_translation_context_target_met"] is True


def test_unit_route_derives_legacy_projection_from_three_axis_values():
    route = UnitRoute(
        local_unit_id="unit_8",
        content_role="background_narrative",
        delivery_route="none",
        summary="Archive-only history.",
    )

    assert route.route == "no_context"
    assert route.fragment_ids == []


def test_runner_persists_workflow_v3_snapshot_on_success(tmp_path):
    target = tmp_path / "run.trace.json"
    backend = SimpleNamespace(last_debug_snapshot={
        "schema_version": "context-workflow-v3-debug-v1",
        "summary": "中文中间结果",
    })

    _persist_workflow_v3_snapshot(backend, str(target))

    assert json.loads(target.read_text(encoding="utf-8"))["summary"] == "中文中间结果"


def test_workflow_v3_trace_reference_uses_live_output_and_preserves_replay_source():
    assert _workflow_v3_trace_reference(None, "live.trace.json") == "live.trace.json"
    assert (
        _workflow_v3_trace_reference("source.trace.json", "replayed.trace.json")
        == "source.trace.json"
    )


class _V3ExtractionHandler:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_structured_with_messages(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


def test_v3_local_extraction_emits_terms_but_no_legacy_narrative_collections():
    payload = {
        "local_fragments": [{
            "fragment_id": "fragment_c0_1",
            "summary": "The envoy discovers a warning.",
            "unit_ids": ["unit_0"],
        }],
        "unit_routes": [
            {
                "local_unit_id": "unit_0",
                "content_role": "event_narrative",
                "delivery_route": "event",
                "summary": "A concrete discovery.",
                "fragment_ids": ["fragment_c0_1"],
            },
            {
                "local_unit_id": "unit_1",
                "content_role": "static_reference",
                "delivery_route": "reference",
                "summary": "The envoy title.",
            },
            {
                "local_unit_id": "unit_2",
                "content_role": "background_narrative",
                "delivery_route": "none",
                "summary": "The gate's earlier history.",
            },
        ],
        "entities": [{
            "name": "Envoy",
            "entity_type": "person",
            "description": "A messenger.",
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "terms": [{
            "original": "warning",
            "category": "concept",
            "suggestion": "警告",
            "reasoning": "A recurring domain expression.",
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "facts": [{
            "subject": "Envoy",
            "predicate": "finds",
            "object": "warning",
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "events": [{
            "chain_id": "legacy-chain",
            "event": "warning",
            "sequence": 0,
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "relationships": [{
            "subject": "Envoy",
            "relation": "finds",
            "object": "warning",
            "evidence": [{"source_item_id": "source_0"}],
        }],
    }
    handler = _V3ExtractionHandler(json.dumps(payload))
    service = ContextWorkflowV3ExtractionService(handler)
    chunk = _chunk()

    extraction = service.extract_structured(
        list(chunk.source_items),
        scope="narrative_context",
        core_units=chunk.core_units,
        edge_units=chunk.edge_units,
        chunk_edge_metadata=chunk.edge_metadata,
    )

    assert len(handler.calls) == 1
    assert extraction.terms[0].original == "warning"
    assert extraction.entities[0].name == "Envoy"
    assert extraction.facts == []
    assert extraction.events == []
    assert extraction.relationships == []
    assert extraction.diagnostics["workflow_v3_legacy_fields_discarded"] == {
        "facts": 1, "events": 1, "relationships": 1,
    }
    prompt = handler.calls[0][0][0]["content"]
    assert "terms are extracted independently" in prompt
    assert "never derive them from entity cards" in prompt
