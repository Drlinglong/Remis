from __future__ import annotations

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_finding_reducer import reduce_findings
from scripts.core.services.context_research_lead_decisions import (
    EntityMergeDecision,
    EventMemberDecision,
    EventMergeEvidence,
    FindingDiscardDecision,
    FindingPatchDecision,
    LeadResearchDecisions,
    LeadResearchResult,
)
from scripts.core.services.context_research_shard_memo import ShardMemoCollection


def _evidence(source_id: str, snippet: str = "证据"):
    return {"source_item_ids": [source_id], "snippet": snippet}


def _event(chain_id: str, sequence: int, unit_id: str, source_id: str, entity_ids=()):
    return {
        "chain_id": chain_id,
        "sequence": sequence,
        "event": f"{chain_id} 事件",
        "local_unit_ids": [unit_id],
        "entity_ids": list(entity_ids),
        "evidence": [_evidence(source_id)],
    }


def _entity(entity_id: str, source_id: str, name: str = "实体"):
    return {
        "entity_id": entity_id,
        "name": name,
        "entity_type": "person",
        "summary": f"{name}摘要",
        "aliases": [],
        "evidence": [_evidence(source_id)],
    }


def _findings():
    return {
        "event_chains": [
            _event("chain-a", 0, "unit-0", "source-0", ("entity-old",)),
            _event("chain-b", 0, "unit-1", "source-1"),
        ],
        "entities": [
            _entity("entity-canonical", "source-c", "Remis"),
            _entity("entity-old", "source-old", "玲珑"),
        ],
        "archive_narratives": [{
            "narrative_id": "lore-1", "summary": "原始档案摘要。",
            "evidence": [_evidence("source-lore")],
        }],
    }


def _collection():
    return ShardMemoCollection(findings=ContextResearchFindings.model_validate(_findings()))


def test_omitted_findings_are_retained_without_normalization():
    source = _collection()

    reduced = reduce_findings(source, LeadResearchResult())

    for kind in ("archive_narratives", "entities", "event_chains", "reference_assets", "unresolved"):
        assert getattr(reduced, kind) == getattr(source.findings, kind)


def test_event_members_regroup_by_finding_ids_and_union_grounded_fields():
    lead = LeadResearchDecisions(event_members=(EventMemberDecision(
        chain_id="crisis-chain",
        sequence=2,
        finding_ids=("chain-a:0", "event_chains:chain-b:0"),
        local_unit_ids=("unit-0", "unit-1"),
    ),))

    reduced = reduce_findings(_collection(), lead)

    assert [(item.chain_id, item.sequence) for item in reduced.event_chains] == [
        ("crisis-chain", 2),
    ]
    assert reduced.event_chains[0].local_unit_ids == ("unit-0", "unit-1")
    assert reduced.event_chains[0].entity_ids == ("entity-old",)
    assert {tuple(item.source_item_ids) for item in reduced.event_chains[0].evidence} == {
        ("source-0",), ("source-1",),
    }


def test_entity_merge_unions_evidence_aliases_and_rewrites_event_links():
    lead = LeadResearchDecisions(entity_merges=(EntityMergeDecision(
        canonical_finding_id="entity-canonical",
        merged_finding_ids=("entities:entity-old",),
    ),))

    reduced = reduce_findings(_collection(), lead)

    assert [item.entity_id for item in reduced.entities] == ["entity-canonical"]
    assert reduced.entities[0].aliases == ("玲珑",)
    assert {tuple(item.source_item_ids) for item in reduced.entities[0].evidence} == {
        ("source-c",), ("source-old",),
    }
    assert reduced.event_chains[0].entity_ids == ("entity-canonical",)


def test_discard_and_allowlisted_patch_are_sparse_and_invalid_fields_are_diagnostic():
    lead = LeadResearchResult(decisions=LeadResearchDecisions(
        discards=(FindingDiscardDecision(
            finding_kind="archive_narratives", finding_id="missing", reason="不存在",
        ),),
        patches=(FindingPatchDecision(
            finding_kind="archive_narratives",
            finding_id="lore-1",
            fields={"summary": "修订摘要。", "source_item_ids": ["forbidden"]},
        ),),
    ))

    reduced = reduce_findings(_collection(), lead)

    assert reduced.archive_narratives[0].summary == "修订摘要。"
    diagnostics = reduced.diagnostics["reducer"]
    assert diagnostics["unknown_identities"] == ["archive_narratives:missing"]
    assert diagnostics["invalid_fields"] == [{
        "finding_kind": "archive_narratives",
        "finding_id": "lore-1",
        "field": "source_item_ids",
        "reason": "field is not patchable",
    }]


def test_unknown_event_member_does_not_cancel_valid_member_or_other_findings():
    lead = LeadResearchDecisions(event_members=(EventMemberDecision(
        chain_id="new-chain",
        sequence=0,
        finding_ids=("missing-chain:0", "chain-a:0"),
    ),))

    reduced = reduce_findings(_collection(), lead)

    assert [(item.chain_id, item.sequence) for item in reduced.event_chains] == [
        ("new-chain", 0), ("chain-b", 0),
    ]
    assert reduced.archive_narratives[0].narrative_id == "lore-1"
    assert "event_chains:missing-chain:0" in reduced.diagnostics["reducer"]["unknown_identities"]


def test_invalid_patch_value_is_diagnostic_and_does_not_drop_the_finding():
    lead = LeadResearchDecisions(patches=(FindingPatchDecision(
        finding_kind="archive_narratives",
        finding_id="lore-1",
        fields={"summary": ["not", "text"]},
    ),))

    reduced = reduce_findings(_collection(), lead)

    assert reduced.archive_narratives[0].summary == "原始档案摘要。"
    assert reduced.diagnostics["reducer"]["invalid_fields"][0]["reason"] == (
        "field value failed finding validation"
    )


def test_event_decision_schema_distinguishes_new_chain_from_existing_members():
    schema = EventMemberDecision.model_json_schema()["properties"]

    assert "New canonical output chain ID" in schema["chain_id"]["description"]
    assert "Never put the new chain_id" in schema["finding_ids"]["description"]
    assert "Prefer these" in schema["local_unit_ids"]["description"]


def test_event_merge_requires_and_records_verified_positive_evidence():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [
            _event("chain-a", 0, "unit_0", "source-0", ("entity-remis",)),
            _event("chain-b", 1, "unit_1", "source-1", ("entity-remis",)),
        ],
    })
    units = (
        LocalTextUnit(
            unit_id="unit_0", unit_key="events/demo.yml::crisis.1",
            items=(SourceItem(
                source_item_id="source-0", relative_path="events/demo.yml",
                item_key="crisis.1.desc", source_order=0, source_text="Remis starts."),),
        ),
        LocalTextUnit(
            unit_id="unit_1", unit_key="events/demo.yml::crisis.2",
            items=(SourceItem(
                source_item_id="source-1", relative_path="events/demo.yml",
                item_key="crisis.2.desc", source_order=1, source_text="Remis continues."),),
        ),
    )
    lead = LeadResearchDecisions(event_members=(EventMemberDecision(
        chain_id="crisis-chain", sequence=0,
        finding_ids=("chain-a:0", "chain-b:1"),
        positive_evidence=(
            EventMergeEvidence(
                signal="shared_entities", entity_ids=("entity-remis",),
            ),
            EventMergeEvidence(
                signal="adjacent_local_units", local_unit_ids=("unit_0", "unit_1"),
            ),
        ),
    ),))

    reduced = reduce_findings(findings, lead, local_units=units)

    assert [(item.chain_id, item.sequence) for item in reduced.event_chains] == [
        ("crisis-chain", 0),
    ]
    reducer = reduced.diagnostics["reducer"]
    assert len(reducer["merge_evidence_acceptances"]) == 1
    assert reducer["merge_evidence_rejections"] == []


def test_event_merge_without_lead_evidence_is_rejected_when_compiler_can_verify():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [
            _event("chain-a", 0, "unit_0", "source-0", ("entity-remis",)),
            _event("chain-b", 1, "unit_1", "source-1", ("entity-remis",)),
        ],
    })
    units = (
        LocalTextUnit(
            unit_id="unit_0", unit_key="events/demo.yml::crisis.1",
            items=(SourceItem(
                source_item_id="source-0", relative_path="events/demo.yml",
                item_key="crisis.1.desc", source_order=0, source_text="Remis starts."),),
        ),
        LocalTextUnit(
            unit_id="unit_1", unit_key="events/demo.yml::crisis.2",
            items=(SourceItem(
                source_item_id="source-1", relative_path="events/demo.yml",
                item_key="crisis.2.desc", source_order=1, source_text="Remis continues."),),
        ),
    )
    lead = LeadResearchDecisions(event_members=(EventMemberDecision(
        chain_id="crisis-chain", sequence=0,
        finding_ids=("chain-a:0", "chain-b:1"),
    ),))

    reduced = reduce_findings(findings, lead, local_units=units)

    assert len(reduced.event_chains) == 2
    assert reduced.diagnostics["reducer"]["merge_evidence_rejections"][0]["reason"] == (
        "lead_merge_evidence_missing"
    )
