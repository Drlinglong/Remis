"""Focused tests for the in-memory context archive tree v2 pipeline."""

from __future__ import annotations

import json

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import AnalysisScope, SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_tree_v2_catalog_service import ContextTreeV2CatalogService
from scripts.core.services.context_tree_v2_contract import (
    ChunkEdgeMetadata,
    ContextTreeCatalog,
    ContextTreeV2Extraction,
    LocalFragment,
    TreeGroup,
    TreeStory,
    UnitRoute,
)
from scripts.core.services.context_tree_v2_context_service import ContextTreeV2ContextService
from scripts.core.services.context_tree_v2_extraction_service import ContextTreeV2ExtractionService
from scripts.core.services.context_tree_v2_projection_service import ContextTreeV2ProjectionService
from scripts.core.services.context_tree_v2_workflow_service import ContextTreeV2WorkflowService


class StructuredFakeHandler:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.schemas = []

    def generate_structured_with_messages(
        self, messages, *, schema, schema_name, temperature=0.0
    ):
        self.calls.append(messages)
        self.schemas.append((schema, schema_name, temperature))
        return next(self.responses)


def _items():
    return [
        SourceItem(
            source_item_id="source-edge",
            relative_path="events/story.yml",
            item_key="story.0.title",
            source_order=0,
            source_text="The envoy receives the warning.",
        ),
        SourceItem(
            source_item_id="source-core",
            relative_path="events/story.yml",
            item_key="story.1.title",
            source_order=1,
            source_text="The envoy chooses the northern road.",
        ),
    ]


def _chunk():
    items = _items()
    units = ContextLocalUnitBuilder.build(items)
    core = units[1:]
    edge = units[:1]
    return ContextUnitChunk(
        core_units=tuple(core),
        edge_units=tuple(edge),
        chunk_index=1,
        chunk_count=2,
    )


def _extraction_payload(fragment_id="fragment_c1_1"):
    return {
        "local_fragments": [{
            "fragment_id": fragment_id,
            "summary": "The envoy chooses a road after receiving the warning.",
            "unit_ids": ["unit_1"],
            "continuation_cues": "The choice is resolved in a later chunk.",
            "boundary_includes": "The road choice.",
            "boundary_excludes": "The later arrival.",
            "touches_chunk_start": True,
            "touches_chunk_end": True,
        }],
        "unit_routes": [{
            "local_unit_id": "unit_1",
            "route": "narrative",
            "fragment_ids": [fragment_id],
        }],
        "entities": [],
        "terms": [],
        "facts": [],
        "events": [],
        "relationships": [],
    }


def _full_extraction_payload():
    payload = _extraction_payload()
    evidence = [{"source_item_id": "source_1"}]
    payload.update({
        "terms": [{
            "original": "envoy",
            "category": "person",
            "suggestion": "使者",
            "reasoning": "A named narrative participant.",
            "evidence": evidence,
        }],
        "entities": [{
            "name": "envoy",
            "entity_type": "person",
            "description": "The participant making the road choice.",
            "evidence": evidence,
        }],
        "facts": [{
            "subject": "envoy",
            "predicate": "chooses",
            "object": "road",
            "evidence": evidence,
        }],
        "events": [{
            "chain_id": "envoy-choice",
            "event": "The envoy chooses the northern road.",
            "sequence": 0,
            "participants": ["envoy"],
            "evidence": evidence,
        }],
        "relationships": [{
            "subject": "envoy",
            "relation": "chooses",
            "object": "road",
            "evidence": evidence,
        }],
    })
    return payload


def test_chunk_edge_metadata_is_explicit_and_reaches_the_v2_prompt():
    chunk = _chunk()
    handler = StructuredFakeHandler([json.dumps(_extraction_payload())])

    result = ContextTreeV2ExtractionService(handler).extract_structured(
        list(chunk.source_items),
        scope=AnalysisScope.NARRATIVE_CONTEXT,
        core_units=chunk.core_units,
        edge_units=chunk.edge_units,
        chunk_edge_metadata=chunk.edge_metadata,
    )

    request = json.loads(handler.calls[0][1]["content"])
    assert request["chunk_edge_metadata"] == {
        "chunk_index": 1,
        "chunk_count": 2,
        "core_unit_ids": ["unit_1"],
        "edge_before_unit_ids": ["unit_0"],
        "edge_after_unit_ids": [],
        "has_previous_core_chunk": True,
        "has_next_core_chunk": False,
    }
    assert [item["context_role"] for item in request["local_text_units"]] == ["core", "edge"]
    assert result.complete is True


def test_unknown_fragment_reference_gets_one_targeted_repair_without_rebinding():
    first = _extraction_payload("fragment_missing")
    first["local_fragments"] = []
    repaired = {
        "local_fragments": [{
            "fragment_id": "fragment_missing",
            "summary": "Repaired local fragment.",
            "unit_ids": ["unit_1"],
            "touches_chunk_start": True,
            "touches_chunk_end": False,
        }]
    }
    handler = StructuredFakeHandler([json.dumps(first), json.dumps(repaired)])

    result = ContextTreeV2ExtractionService(handler).extract_structured(
        list(_chunk().source_items),
        scope=AnalysisScope.NARRATIVE_CONTEXT,
        core_units=_chunk().core_units,
        edge_units=_chunk().edge_units,
        chunk_edge_metadata=_chunk().edge_metadata,
    )

    assert len(handler.calls) == 2
    assert handler.schemas[1][1] == "remis_context_tree_v2_fragment_repair"
    assert "fragment_missing" in handler.calls[1][-1]["content"]
    assert result.unit_routes[0].fragment_ids == ["fragment_missing"]
    assert result.local_fragments[0].fragment_id == "fragment_missing"
    assert result.unresolved_fragment_references == []
    assert result.diagnostics["repair_count"] == 1


def test_failed_fragment_repair_preserves_unknown_route_as_unresolved():
    first = _extraction_payload("fragment_missing")
    first["local_fragments"] = []
    handler = StructuredFakeHandler([
        json.dumps(first),
        json.dumps({"local_fragments": []}),
    ])

    result = ContextTreeV2ExtractionService(handler).extract_structured(
        list(_chunk().source_items),
        scope=AnalysisScope.NARRATIVE_CONTEXT,
        core_units=_chunk().core_units,
        edge_units=_chunk().edge_units,
        chunk_edge_metadata=_chunk().edge_metadata,
    )

    assert len(handler.calls) == 2
    assert result.unit_routes[0].fragment_ids == ["fragment_missing"]
    assert result.unresolved_fragment_references[0].fragment_id == "fragment_missing"
    assert result.unresolved_fragment_references[0].local_unit_id == "unit_1"
    assert result.complete is False
    assert result.diagnostics["repair_failed"] is True
    assert result.diagnostics["repair_count"] == 1


def test_catalog_is_id_only_and_keeps_group_order_semantics_separate():
    fragments = [
        LocalFragment(fragment_id="fragment_a", summary="A", unit_ids=["unit_0"]),
        LocalFragment(fragment_id="fragment_b", summary="B", unit_ids=["unit_1"]),
    ]
    response = {
        "stories": [{"story_id": "story_1", "group_ids": ["group_1"]}],
        "groups": [{"group_id": "group_1", "fragment_ids": ["fragment_a", "fragment_b"]}],
        "unresolved_fragment_ids": [],
    }
    handler = StructuredFakeHandler([json.dumps(response)])

    result = ContextTreeV2CatalogService(handler).build_catalog(fragments)

    assert result.catalog.groups[0].fragment_ids == ["fragment_a", "fragment_b"]
    assert result.diagnostics["sibling_group_order_semantics"] == "unordered"
    assert result.diagnostics["group_fragment_order_semantics"] == "ordered"
    assert set(result.catalog.model_dump()) == {"stories", "groups", "unresolved_fragment_ids"}
    assert set(handler.schemas[0][0]["properties"]) == {
        "stories", "groups", "unresolved_fragment_ids"
    }


def test_program_projection_and_context_assembly_do_not_synthesize_or_order_siblings():
    fragments = [
        LocalFragment(fragment_id="fragment_a", summary="A", unit_ids=["unit_0"]),
        LocalFragment(fragment_id="fragment_b", summary="B", unit_ids=["unit_0"]),
        LocalFragment(fragment_id="fragment_c", summary="C", unit_ids=["unit_1"]),
    ]
    catalog = ContextTreeCatalog(
        stories=[TreeStory(story_id="story", group_ids=["group_b", "group_a"])],
        groups=[
            TreeGroup(group_id="group_b", fragment_ids=["fragment_c"]),
            TreeGroup(group_id="group_a", fragment_ids=["fragment_b", "fragment_a"]),
        ],
    )
    routes = [
        UnitRoute(local_unit_id="unit_0", route="narrative", fragment_ids=["fragment_a", "fragment_b"]),
        UnitRoute(local_unit_id="unit_1", route="reference_asset"),
        UnitRoute(local_unit_id="unit_2", route="no_context"),
    ]

    projection = ContextTreeV2ProjectionService.project(
        routes, catalog, expected_unit_ids=["unit_0", "unit_1", "unit_2"]
    )
    groups = ContextTreeV2ContextService.build_group_contexts(catalog, fragments)
    narrative_context = ContextTreeV2ContextService.project_translation_context(
        projection.unit_routes[0], groups, project_summary="Manual project summary"
    )
    reference_context = ContextTreeV2ContextService.project_translation_context(
        projection.unit_routes[1], groups
    )

    assert projection.unit_routes[0].group_ids == ["group_a"]
    assert [group.group_id for group in groups] == ["group_a", "group_b"]
    assert groups[0].fragment_ids == ["fragment_b", "fragment_a"]
    assert groups[0].summary_bullets == ["B", "A"]
    assert narrative_context.event_groups[0].summary_bullets == ["B", "A"]
    assert narrative_context.project_summary == "Manual project summary"
    assert reference_context.event_groups == []
    assert reference_context.route == "reference_asset"


def test_terms_only_v2_skips_catalog_and_assignment_or_synthesis_calls():
    handler = StructuredFakeHandler([json.dumps({
        **_extraction_payload(),
        "local_fragments": [],
        "unit_routes": [],
        "terms": [],
    })])
    service = ContextTreeV2WorkflowService(
        handler_factory=lambda *_args, **_kwargs: handler,
    )

    result = service.run(
        [_chunk()],
        scope=AnalysisScope.TERMS_ONLY,
    )

    assert len(handler.calls) == 1
    assert result.catalog is None
    assert result.projection is None
    assert result.model_calls == {
        "extraction": 1,
        "fragment_repair": 0,
        "catalog": 0,
        "assignment": 0,
        "synthesis": 0,
    }


def test_term_only_and_full_use_identical_extraction_prompt_and_schema_then_discard():
    handler = StructuredFakeHandler([
        json.dumps(_full_extraction_payload()),
        json.dumps(_full_extraction_payload()),
    ])
    service = ContextTreeV2ExtractionService(handler)
    chunk = _chunk()

    full = service.extract_structured(
        list(chunk.source_items),
        scope=AnalysisScope.NARRATIVE_CONTEXT,
        core_units=chunk.core_units,
        edge_units=chunk.edge_units,
        chunk_edge_metadata=chunk.edge_metadata,
    )
    terms_only = service.extract_structured(
        list(chunk.source_items),
        scope=AnalysisScope.TERMS_ONLY,
        core_units=chunk.core_units,
        edge_units=chunk.edge_units,
        chunk_edge_metadata=chunk.edge_metadata,
    )

    assert handler.calls[0][0]["content"] == handler.calls[1][0]["content"]
    assert handler.calls[0][1]["content"] == handler.calls[1][1]["content"]
    assert handler.schemas[0][0] == handler.schemas[1][0]
    assert set(json.loads(handler.calls[0][1]["content"])) == {
        "source_items", "local_text_units", "core_unit_ids", "chunk_edge_metadata"
    }
    assert len(json.loads(handler.calls[1][1]["content"])["local_text_units"]) == 2
    assert full.entities and full.events and full.facts and full.relationships
    assert terms_only.entities == []
    assert terms_only.events == []
    assert terms_only.facts == []
    assert terms_only.relationships == []
    assert terms_only.local_fragments == []
    assert terms_only.unit_routes == []
    assert terms_only.terms and terms_only.terms[0].original == "envoy"
    assert terms_only.diagnostics["terms_only_discarded_fields"] == {
        "local_fragments": 1,
        "unit_routes": 1,
        "entities": 1,
        "facts": 1,
        "events": 1,
        "relationships": 1,
    }
    assert terms_only.diagnostics["complete"] is True


def test_narrative_v2_uses_one_catalog_call_and_program_projection_only():
    extraction_handler = StructuredFakeHandler([json.dumps(_extraction_payload())])
    catalog_handler = StructuredFakeHandler([json.dumps({
        "stories": [{"story_id": "story_1", "group_ids": ["group_1"]}],
        "groups": [{
            "group_id": "group_1",
            "fragment_ids": ["fragment_c1_1"],
        }],
        "unresolved_fragment_ids": [],
    })])
    handlers = iter([extraction_handler, catalog_handler])
    service = ContextTreeV2WorkflowService(
        handler_factory=lambda *_args, **_kwargs: next(handlers),
    )

    result = service.run(
        [_chunk()],
        scope=AnalysisScope.NARRATIVE_CONTEXT,
        project_summary="A manually supplied summary.",
    )

    assert result.model_calls == {
        "extraction": 1,
        "fragment_repair": 0,
        "catalog": 1,
        "assignment": 0,
        "synthesis": 0,
    }
    assert result.projection is not None
    assert result.projection.unit_routes[0].group_ids == ["group_1"]
    assert result.translation_contexts[0].event_groups[0].summary_bullets == [
        "The envoy chooses a road after receiving the warning."
    ]
    assert result.translation_contexts[0].project_summary == "A manually supplied summary."
    assert len(extraction_handler.calls) == 1
    assert len(catalog_handler.calls) == 1
