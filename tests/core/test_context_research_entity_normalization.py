from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import (
    ContextResearchDraftCompiler,
    ContextResearchFindings,
)
from scripts.core.services.context_research_contract import ContextAnalysisRequest


def _source(source_id: str, key: str, text: str) -> SourceItem:
    return SourceItem(
        source_item_id=source_id,
        relative_path="events/demo.yml",
        item_key=key,
        source_order=int(source_id[-1]),
        source_text=text,
    )


def _request(*items: SourceItem) -> ContextAnalysisRequest:
    return ContextAnalysisRequest(project_id="entity-normalization", source_items=items)


def test_compiler_merges_grounded_aliases_and_rewrites_event_links() -> None:
    request = _request(
        _source("source-0", "demo.1.desc", "The Red Archivist begins the chronicle."),
        _source("source-1", "demo.2.desc", "Red Archivist continues the chronicle."),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [
            {
                "entity_id": "entity-b",
                "name": "The Red Archivist",
                "entity_type": "person",
                "summary": "The archivist.",
                "evidence": [{"source_item_ids": ["source-0"]}],
            },
            {
                "entity_id": "entity-a",
                "name": "红色档案官",
                "aliases": ["Red Archivist"],
                "entity_type": "person",
                "summary": "同一位档案官。",
                "importance": "primary",
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
        ],
        "event_chains": [{
            "chain_id": "chronicle",
            "event": "The archivist advances the chronicle.",
            "entity_ids": ["entity-b", "entity-a"],
            "evidence": [{"source_item_ids": ["source-0", "source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [entity.entity_id for entity in draft.entities] == ["entity-a"]
    entity = draft.entities[0]
    assert entity.name == "Red Archivist"
    assert entity.aliases == ("The Red Archivist", "红色档案官")
    assert entity.source_item_ids == ("source-0", "source-1")
    assert entity.local_unit_coverage == 2
    assert entity.frequency_grade == "B"
    assert entity.importance == "primary"
    assert entity.mention_count == 2
    assert draft.event_chains[0].entity_ids == ("entity-a",)
    normalization = draft.diagnostics["compiler"]["entity_normalization"]
    assert normalization["automatic_merge_count"] == 1
    assert normalization["pair_decisions"][0]["evidence_strength"] == "grounded_alias"
    assert normalization["merged_groups"] == [{
        "canonical_entity_id": "entity-a",
        "canonical_display_name": "Red Archivist",
        "merged_entity_ids": ["entity-b"],
        "match_keys": ["red archivist"],
        "entity_type": "person",
        "source_item_ids": ["source-0", "source-1"],
    }]


def test_shared_unit_or_substring_without_exact_alias_does_not_merge() -> None:
    request = _request(
        _source("source-0", "demo.1.desc", "The Red Archivist meets the Blue Archivist."),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [
            {
                "entity_id": "red",
                "name": "Red Archivist",
                "entity_type": "person",
                "summary": "Red.",
                "evidence": [{"source_item_ids": ["source-0"]}],
            },
            {
                "entity_id": "blue",
                "name": "Blue Archivist",
                "entity_type": "person",
                "summary": "Blue.",
                "evidence": [{"source_item_ids": ["source-0"]}],
            },
        ],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [entity.entity_id for entity in draft.entities] == ["blue", "red"]
    assert draft.diagnostics["compiler"]["entity_normalization"]["automatic_merge_count"] == 0


def test_incompatible_grounded_types_remain_separate_with_diagnostic() -> None:
    request = _request(
        _source("source-0", "demo.1.desc", "The Crown commands the guard."),
        _source("source-1", "demo.2.desc", "The Crown stands above the city."),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [
            {
                "entity_id": "crown-place",
                "name": "The Crown",
                "entity_type": "place",
                "summary": "A place called the Crown.",
                "evidence": [{"source_item_ids": ["source-0"]}],
            },
            {
                "entity_id": "crown-org",
                "name": "Crown",
                "entity_type": "organization",
                "summary": "An organization called Crown.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
        ],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [entity.entity_id for entity in draft.entities] == ["crown-org", "crown-place"]
    assert draft.diagnostics["compiler"]["entity_normalization"]["blocked_type_conflicts"] == [{
        "match_entity_ids": ["crown-org", "crown-place"],
        "entity_types": ["organization", "place"],
        "reason": "incompatible concrete entity types share a grounded alias",
    }]


def test_complete_linkage_blocks_transitive_alias_bridge() -> None:
    request = _request(
        _source("source-0", "demo.1.desc", "The Red Archivist arrives."),
        _source("source-1", "demo.2.desc", "The Red Archivist meets the Blue Archivist."),
        _source("source-2", "demo.3.desc", "The Blue Archivist returns."),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [
            {
                "entity_id": "red",
                "name": "Red Archivist",
                "entity_type": "person",
                "summary": "Red.",
                "evidence": [{"source_item_ids": ["source-0"]}],
            },
            {
                "entity_id": "middle",
                "name": "Red Archivist",
                "aliases": ["Blue Archivist"],
                "entity_type": "person",
                "summary": "Middle.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
            {
                "entity_id": "blue",
                "name": "Blue Archivist",
                "entity_type": "person",
                "summary": "Blue.",
                "evidence": [{"source_item_ids": ["source-2"]}],
            },
        ],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert len(draft.entities) == 2
    diagnostic = draft.diagnostics["compiler"]["entity_normalization"]
    assert diagnostic["blocked_complete_linkage_merges"]
