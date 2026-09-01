"""Regression coverage for the deterministic Agent findings compiler."""

from __future__ import annotations

import pytest

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import (
    ContextResearchDraftCompiler,
    ContextResearchFindings,
)
from scripts.core.services.context_research_contract import ContextAnalysisRequest


def _source(source_id: str, key: str, text: str | None = None) -> SourceItem:
    return SourceItem(
        source_item_id=source_id,
        relative_path="events/demo.yml",
        item_key=key,
        source_order=0,
        source_text=text or f"Evidence for {key}",
    )


def _request() -> ContextAnalysisRequest:
    return ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("source-1", "demo.1.desc"),
            _source("source-2", "demo.2.desc"),
        ),
        description_language="zh-CN",
    )


def test_compiler_derives_every_source_index_from_allowlisted_evidence():
    findings = ContextResearchFindings.model_validate({
        "source_item_ids": ["model-must-not-own-this-index"],
        "archive_narratives": [{
            "narrative_id": "archive-1",
            "summary": "只进入档案的世界观背景。",
            "source_item_ids": ["legacy-item-index-is-ignored"],
            "delivery_target": True,
            "evidence": [{
                "source_item_ids": ["source-1", "source-1", "unknown-source"],
                "snippet": "世界观证据",
                "relative_path": "model/path/is/ignored.yml",
            }],
        }],
        "event_chains": [{
            "chain_id": "event-1",
            "event": "具体事件发生。",
            "sequence": 1,
            "archive_context_ids": ["archive-1"],
            "evidence": [{"source_item_ids": ["source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.source_item_ids == ("source-1", "source-2")
    assert draft.archive_narratives[0].source_item_ids == ("source-1",)
    assert draft.archive_narratives[0].delivery_target is False
    assert draft.archive_narratives[0].evidence[0].relative_path == "events/demo.yml"
    assert draft.archive_narratives[0].evidence[0].item_key == "demo.1.desc"
    assert draft.event_chains[0].archive_context_ids == ("archive-1",)
    rejected = draft.diagnostics["compiler"]["rejected_source_item_ids"]
    assert [item["source_item_id"] for item in rejected] == ["unknown-source"]


def test_compiler_drops_ungrounded_duplicates_without_killing_grounded_results():
    findings = ContextResearchFindings.model_validate({
        "archive_narratives": [
            {
                "narrative_id": "archive-1",
                "summary": "保留的档案叙事。",
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
            {
                "narrative_id": "archive-1",
                "summary": "重复身份不覆盖第一条。",
                "evidence": [{"source_item_ids": ["source-2"]}],
            },
            {
                "narrative_id": "archive-ungrounded",
                "summary": "没有合法证据。",
                "evidence": [{"source_item_ids": ["made-up-source"]}],
            },
        ],
        "reference_assets": [{
            "asset_id": "asset-1",
            "name": "静态资产",
            "receives_event_context": True,
            "evidence": [{"source_item_ids": ["source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert [item.narrative_id for item in draft.archive_narratives] == ["archive-1"]
    assert draft.reference_assets[0].receives_event_context is False
    compiler = draft.diagnostics["compiler"]
    assert compiler["dropped_duplicate_findings"] == [{
        "finding_type": "archive_narrative",
        "identity": "archive-1",
    }]
    assert compiler["dropped_ungrounded_findings"] == [{
        "finding_type": "archive_narrative",
        "identity": "archive-ungrounded",
    }]


def test_unknown_archive_link_becomes_grounded_unresolved_record():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "event-1",
            "event": "事件引用了不存在的档案卡。",
            "archive_context_ids": ["missing-archive"],
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.event_chains[0].archive_context_ids == ()
    assert len(draft.unresolved) == 1
    assert draft.unresolved[0].source_id == "event-1"
    assert draft.unresolved[0].target_id == "missing-archive"
    assert draft.unresolved[0].source_item_ids == ("source-1",)
    assert draft.diagnostics["compiler"]["unknown_archive_context_links"] == [{
        "chain_id": "event-1",
        "archive_context_id": "missing-archive",
    }]


def test_model_unresolved_uses_relation_names_but_accepts_legacy_aliases():
    findings = ContextResearchFindings.model_validate({
        "unresolved": [{
            "unresolved_id": "unknown-1",
            "reference_type": "story",
            "source_id": "event-1",
            "target_id": "missing-story",
            "reason": "来源没有说明这条关系。",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.unresolved[0].source_id == "event-1"
    assert draft.unresolved[0].target_id == "missing-story"
    assert draft.diagnostics["compiler"]["published_counts"]["unresolved"] == 1


def test_event_step_expands_delivery_membership_from_deterministic_local_unit():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            SourceItem(
                source_item_id="source-title", relative_path="events/demo.yml",
                item_key="demo.1.t", source_order=0, source_text="A title",
            ),
            SourceItem(
                source_item_id="source-desc", relative_path="events/demo.yml",
                item_key="demo.1.desc", source_order=1, source_text="A concrete event",
            ),
            SourceItem(
                source_item_id="source-option", relative_path="events/demo.yml",
                item_key="demo.1.c", source_order=2, source_text="Declare war",
            ),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "A concrete event with a player choice.",
            "sequence": 1,
            "local_unit_ids": ["unit_0"],
            "evidence": [{"source_item_ids": ["source-desc"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.event_chains[0].local_unit_ids == ("unit_0",)
    assert draft.event_chains[0].source_item_ids == (
        "source-title", "source-desc", "source-option",
    )
    assert draft.event_chains[0].evidence[0].source_item_ids == ("source-desc",)


def test_sibling_steps_can_share_one_chain_identity():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [
            {
                "chain_id": "demo-chain", "event": "First step.", "sequence": 1,
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
            {
                "chain_id": "demo-chain", "event": "Second step.", "sequence": 2,
                "evidence": [{"source_item_ids": ["source-2"]}],
            },
        ],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert [(item.chain_id, item.sequence) for item in draft.event_chains] == [
        ("demo-chain", 1), ("demo-chain", 2),
    ]


def test_compiler_infers_a_complete_local_unit_from_evidence_members():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("title", "demo.1.t"),
            _source("desc", "demo.1.desc"),
            _source("choice", "demo.1.a"),
            _source("next", "demo.2.desc"),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "A concrete event with its choice.",
            "evidence": [{"source_item_ids": ["title", "desc", "choice"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.event_chains[0].local_unit_ids == ("unit_0",)
    assert draft.event_chains[0].source_item_ids == ("title", "desc", "choice")
    assert draft.diagnostics["compiler"]["inferred_local_unit_ids"] == [{
        "chain_id": "demo-chain",
        "sequence": 0,
        "local_unit_id": "unit_0",
    }]


def test_compiler_does_not_infer_an_incomplete_local_unit():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("title", "demo.1.t"),
            _source("desc", "demo.1.desc"),
            _source("choice", "demo.1.a"),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "Only one member is evidenced.",
            "evidence": [{"source_item_ids": ["desc"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.event_chains[0].local_unit_ids == ()
    assert draft.event_chains[0].source_item_ids == ("desc",)
    assert draft.diagnostics["compiler"]["inferred_local_unit_ids"] == []


def test_resolved_unit_route_is_dropped_only_when_one_event_covers_all_evidence():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "The event covers both family members.",
            "evidence": [{"source_item_ids": ["source-1", "source-2"]}],
        }],
        "unresolved": [{
            "unresolved_id": "route-1",
            "reference_type": "unit_route",
            "source_id": "unit_0",
            "target_id": "demo-chain",
            "reason": "The old route was not assigned.",
            "evidence": [{"source_item_ids": ["source-1", "source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.unresolved == ()
    assert draft.diagnostics["compiler"]["dropped_resolved_unit_routes"] == [{
        "unresolved_id": "route-1",
        "source_item_ids": ("source-1", "source-2"),
    }]


def test_unit_route_remains_when_coverage_is_cross_event_or_incomplete():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("source-1", "demo.1.t"),
            _source("source-2", "demo.1.desc"),
            _source("source-3", "demo.1.a"),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [
            {
                "chain_id": "first-event",
                "event": "First event.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            },
            {
                "chain_id": "second-event",
                "event": "Second event.",
                "evidence": [{"source_item_ids": ["source-3"]}],
            },
        ],
        "unresolved": [{
            "unresolved_id": "route-cross-event",
            "reference_type": "unit_route",
            "source_id": "unit_0",
            "target_id": "mixed-events",
            "reason": "Evidence is split across events.",
            "evidence": [{"source_item_ids": ["source-1", "source-2"]}],
        }, {
            "unresolved_id": "route-incomplete",
            "reference_type": "unit_route",
            "source_id": "unit_1",
            "target_id": "first-event",
            "reason": "Only part of the local family is covered.",
            "evidence": [{"source_item_ids": ["source-1", "source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [item.unresolved_id for item in draft.unresolved] == [
        "route-cross-event", "route-incomplete",
    ]
    assert draft.diagnostics["compiler"]["dropped_resolved_unit_routes"] == []


def test_embedded_dynamic_entity_uncertainty_is_not_a_top_level_unresolved():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source("event-source", "demo.1.desc", "The capital is [Root.GetCapitalName]."),),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "The crisis event.",
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
        "unresolved": [{
            "unresolved_id": "unresolved_root_capital_name",
            "reference_type": "source_evidence",
            "source_id": "entity_root_capital",
            "target_id": "[Root.GetCapitalName]",
            "reason": "Only a runtime variable is available.",
            "evidence": [{"source_item_ids": ["event-source"], "snippet": "The capital..."}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.unresolved == ()
    embedded = draft.diagnostics["compiler"]["embedded_event_uncertainties"]
    assert embedded[0]["unresolved_id"] == "unresolved_root_capital_name"
    assert embedded[0]["reason"] == "Only a runtime variable is available."
    assert embedded[0]["evidence"][0]["source_item_ids"] == ("event-source",)


def test_cross_chain_or_non_dynamic_source_evidence_remains_unresolved():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source("event-source", "demo.1.desc", "The capital is unknown."),),
    )
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "The crisis event.",
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
        "unresolved": [{
            "unresolved_id": "unresolved_missing_capital",
            "reference_type": "source_evidence",
            "source_id": "entity_root_capital",
            "target_id": "capital-of-missing-polity",
            "reason": "The cross-chain target is absent.",
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [item.unresolved_id for item in draft.unresolved] == ["unresolved_missing_capital"]
    assert draft.diagnostics["compiler"]["embedded_event_uncertainties"] == []


def test_dynamic_entity_candidate_and_event_link_are_dropped_without_unresolved():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source("event-source", "demo.1.desc", "The capital is [Root.GetCapitalName]."),),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "entity_root_capital",
            "name": "[Root.GetCapitalName]",
            "entity_type": "place",
            "summary": "A runtime placeholder, not a named entity.",
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "The crisis event.",
            "entity_ids": ["entity_root_capital"],
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.entities == ()
    assert draft.event_chains[0].entity_ids == ()
    assert draft.event_chains[0].source_item_ids == ("event-source",)
    assert draft.unresolved == ()
    assert draft.diagnostics["compiler"]["rejected_dynamic_entity_candidates"] == [{
        "entity_id": "entity_root_capital",
        "name": "[Root.GetCapitalName]",
    }]
    assert draft.diagnostics["compiler"]["dropped_dynamic_entity_links"] == [{
        "chain_id": "demo-chain",
        "sequence": 0,
        "entity_id": "entity_root_capital",
    }]
    assert draft.diagnostics["compiler"]["unknown_entity_links"] == []


def test_dynamic_placeholder_inside_normal_entity_name_is_not_rejected():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source(
            "event-source", "demo.1.desc", "The capital [Root.GetCapitalName] is threatened.",
        ),),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "capital-threat",
            "name": "Capital [Root.GetCapitalName]",
            "entity_type": "concept",
            "summary": "A normal prose surface containing a variable.",
            "evidence": [{"source_item_ids": ["event-source"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [item.entity_id for item in draft.entities] == ["capital-threat"]
    assert draft.diagnostics["compiler"]["rejected_dynamic_entity_candidates"] == []


def test_unknown_non_dynamic_entity_link_still_becomes_unresolved():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "demo-chain",
            "event": "The event mentions an unverified actor.",
            "entity_ids": ["missing-actor"],
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.unresolved[0].target_id == "missing-actor"
    assert draft.diagnostics["compiler"]["dropped_dynamic_entity_links"] == []


def test_compiler_reports_request_sources_not_covered_by_any_published_item():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("source-1", "demo.1.desc"),
            _source("source-2", "demo.2.desc", "Remis remains in power."),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "remis",
            "name": "Remis",
            "entity_type": "polity",
            "summary": "A grounded polity.",
            "evidence": [{"source_item_ids": ["source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.diagnostics["compiler"]["uncovered_source_item_ids"] == ["source-1"]


def test_entity_finding_schema_rejects_unknown_type_and_importance():
    with pytest.raises(ValueError):
        ContextResearchFindings.model_validate({
            "entities": [{
                "entity_id": "remis",
                "name": "Remis",
                "entity_type": "narrative",
                "summary": "Not a contract entity type.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            }],
        })
    with pytest.raises(ValueError):
        ContextResearchFindings.model_validate({
            "entities": [{
                "entity_id": "remis",
                "name": "Remis",
                "entity_type": "polity",
                "importance": "critical",
                "summary": "Not a contract importance value.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            }],
        })


def test_first_class_entity_is_publishable_and_event_can_link_to_it():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("source-1", "demo.1.desc", "Remis establishes the new order."),
            _source("source-2", "demo.2.desc", "The event follows Remis."),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "remis",
            "name": "Remis",
            "entity_type": "polity",
            "summary": "The polity at the center of the event.",
            "importance": "primary",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
        "event_chains": [{
            "chain_id": "remis-crisis",
            "event": "Remis announces a new order.",
            "sequence": 1,
            "entity_ids": ["remis"],
            "evidence": [{"source_item_ids": ["source-2"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert [(entity.entity_id, entity.name) for entity in draft.entities] == [("remis", "Remis")]
    assert draft.event_chains[0].entity_ids == ("remis",)
    assert draft.diagnostics["compiler"]["unknown_entity_links"] == []


def test_entity_evidence_rejects_a_legal_source_id_without_entity_surface():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source("source-1", "tradition.pax.name", "True peace is enforced."),),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "pax-remisia",
            "name": "Pax Remisia",
            "aliases": ["Remisian Peace"],
            "entity_type": "concept",
            "summary": "A named doctrine.",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.entities == ()
    assert draft.diagnostics["compiler"]["rejected_entity_evidence_ids"] == [{
        "entity_id": "pax-remisia",
        "source_item_id": "source-1",
    }]


def test_entity_evidence_expands_a_matching_name_sibling_into_the_local_unit():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(
            _source("name", "ap.absolute_sublimation.name", "Absolute Sublimation"),
            _source("desc", "ap.absolute_sublimation.desc", "The protocol changes every citizen."),
        ),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "absolute-sublimation",
            "name": "Absolute Sublimation",
            "entity_type": "concept",
            "summary": "A named ascension doctrine.",
            "evidence": [{"source_item_ids": ["desc"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.entities[0].source_item_ids == ("desc", "name")
    assert draft.entities[0].evidence[0].source_item_ids == ("desc",)


def test_entity_evidence_uses_aliases_and_strips_paradox_formatting_codes():
    request = ContextAnalysisRequest(
        project_id="project-1",
        source_items=(_source("source-1", "tech.protocol.name", "§RSUBLIMATION PROTOCOL§!"),),
    )
    findings = ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "sublimation-protocol",
            "name": "Protocol of Ascension",
            "aliases": ["Sublimation Protocol"],
            "entity_type": "technology",
            "summary": "A named technology.",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.entities[0].source_item_ids == ("source-1",)


def test_unknown_entity_link_is_not_published_or_silently_invented():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "remis-crisis",
            "event": "The event mentions an unverified actor.",
            "entity_ids": ["missing-actor"],
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.entities == ()
    assert draft.event_chains[0].entity_ids == ()
    assert draft.unresolved[0].target_id == "missing-actor"


def test_reference_asset_stays_an_asset_and_invalid_local_unit_is_cleared():
    findings = ContextResearchFindings.model_validate({
        "reference_assets": [{
            "asset_id": "remis-banner",
            "name": "Remis",
            "local_unit_id": "unit-does-not-exist",
            "entity_id": "must-not-promote",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })

    draft = ContextResearchDraftCompiler().compile(findings, _request())

    assert draft.entities == ()
    assert draft.reference_assets[0].asset_id == "remis-banner"
    assert draft.reference_assets[0].local_unit_id is None
    assert draft.diagnostics["compiler"]["rejected_asset_local_unit_ids"] == [{
        "asset_id": "remis-banner",
        "local_unit_id": "unit-does-not-exist",
    }]
