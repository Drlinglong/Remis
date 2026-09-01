"""Focused tests for deterministic typed child-memo collection."""

from __future__ import annotations

import json

import pytest

from scripts.core.services.context_research_lead_decisions import LeadResearchResult
from scripts.core.services.context_research_delegation import DelegationTracker
from scripts.core.services.context_research_shard_memo import ShardMemo, ShardMemoCollector


def _manifest():
    return (
        {"shard_id": "s0", "core_local_unit_ids": ["unit_0"], "overlap_local_unit_ids": []},
        {"shard_id": "s1", "core_local_unit_ids": ["unit_1"], "overlap_local_unit_ids": ["unit_0"]},
    )


def _evidence(source_id: str, snippet: str = "grounded"):
    return {"source_item_ids": [source_id], "snippet": snippet}


def _findings(*, event=None, entity=None, narrative=None, asset=None, unresolved=None):
    return {
        "event_chains": [event] if event else [],
        "entities": [entity] if entity else [],
        "archive_narratives": [narrative] if narrative else [],
        "reference_assets": [asset] if asset else [],
        "unresolved": [unresolved] if unresolved else [],
    }


def _memo(role, shard_ids, core=(), overlap=(), units=()):
    return ShardMemo.model_validate({
        "role": role,
        "shard_ids": list(shard_ids),
        "core_local_unit_ids": list(core),
        "overlap_local_unit_ids": list(overlap),
        "units": list(units),
    })


def _unit(
    unit_id, ownership, findings, disposition="modeled", *,
    content_role="utility_or_noise", delivery_route="none", confidence=None,
    notes=None, evidence=(),
):
    content_findings = dict(findings)
    entity_mentions = content_findings.pop("entities", [])
    return {
        "local_unit_id": unit_id,
        "ownership": ownership,
        "disposition": disposition,
        "content_role": content_role,
        "delivery_route": delivery_route,
        "findings": content_findings,
        "entity_mentions": entity_mentions,
        "confidence": confidence,
        "notes": notes,
        "evidence": list(evidence),
    }


def _event(
    chain_id="chain-a", sequence=0, source_id="source-a", entity_ids=(),
    local_unit_ids=("unit_0",), text="发生了事件。",
):
    return {
        "chain_id": chain_id,
        "sequence": sequence,
        "event": text,
        "entity_ids": list(entity_ids),
        "local_unit_ids": list(local_unit_ids),
        "evidence": [_evidence(source_id)],
    }


def _entity(entity_id="entity-a", source_id="source-a", name="Remis"):
    return {
        "entity_id": entity_id,
        "name": name,
        "entity_type": "person",
        "summary": "实体摘要。",
        "evidence": [_evidence(source_id)],
    }


def test_core_units_have_one_owner_and_aggregate_typed_findings():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "archive_lore", ["s1"], core=["unit_1"],
        units=[_unit("unit_1", "core", _findings(
            entity=_entity("entity-b", "source-b"),
            asset={"asset_id": "asset-b", "name": "静态资产", "local_unit_id": "unit_1"},
        ))],
    ))
    collector.add(_memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(event=_event()))],
    ))

    result = collector.collect()

    assert [unit.local_unit_id for unit in result.units] == ["unit_0", "unit_1"]
    assert [item.chain_id for item in result.findings.event_chains] == ["chain-a"]
    assert [item.entity_id for item in result.findings.entities] == ["entity-b"]
    assert result.missing_core_local_unit_ids == ()
    assert result.complete is True


def test_core_unit_records_three_independent_axes():
    classified = _memo(
        "archive_lore", ["s0"], core=["unit_0"],
        units=[_unit(
            "unit_0", "core", _findings(entity=_entity()),
            content_role="background_narrative", delivery_route="none",
            confidence="medium", notes="这是档案前史，不绑定事件投递。",
            evidence=("S081", "S082"),
        )],
    )
    empty = _memo(
        "cartographer", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings())],
    )

    assert classified.units[0].content_role == "background_narrative"
    assert classified.units[0].delivery_route == "none"
    assert classified.units[0].entity_mentions[0].entity_id == "entity-a"
    assert classified.units[0].confidence == "medium"
    assert classified.units[0].evidence == ("S081", "S082")
    assert empty.units[0].content_role == "utility_or_noise"
    assert empty.units[0].delivery_route == "none"


def test_three_axis_contract_rejects_unknown_values_and_entity_is_not_a_route():
    with pytest.raises(ValueError):
        _memo(
            "archive_lore", ["s0"], core=["unit_0"],
            units=[_unit(
                "unit_0", "core", _findings(), content_role="not_a_role",
            )],
        )
    with pytest.raises(ValueError):
        _memo(
            "archive_lore", ["s0"], core=["unit_0"],
            units=[_unit(
                "unit_0", "core", _findings(entity=_entity()), delivery_route="entity",
            )],
        )


def test_content_findings_can_coexist_before_explicit_delivery_is_applied():
    memo = _memo(
        "cartographer", ["s0"], core=["unit_0"],
        units=[_unit(
            "unit_0", "core", _findings(
                event=_event(),
                asset={"asset_id": "asset-a", "name": "静态资产", "local_unit_id": "unit_0"},
            ),
            content_role="event_narrative", delivery_route="event",
        )],
    )

    assert memo.units[0].findings.event_chains
    assert memo.units[0].findings.reference_assets


def test_legacy_route_and_nested_entity_shape_is_migrated_at_read_boundary():
    memo = _memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[{
            "local_unit_id": "unit_0",
            "ownership": "core",
            "disposition": "modeled",
            "candidate_routes": ["event_chain", "entity"],
            "preferred_route": "event_chain",
            "route_status": "decided",
            "findings": _findings(event=_event(), entity=_entity()),
        }],
    )

    unit = memo.units[0]
    assert unit.content_role == "event_narrative"
    assert unit.delivery_route == "event"
    assert unit.entity_mentions[0].entity_id == "entity-a"


def test_model_schema_advertises_only_the_three_axis_contract():
    schema = json.dumps(ShardMemo.model_json_schema(), sort_keys=True)

    assert "content_role" in schema
    assert "delivery_route" in schema
    assert "entity_mentions" in schema
    assert "candidate_routes" not in schema
    assert "preferred_route" not in schema


def test_one_event_finding_can_route_multiple_core_units_once():
    memo = _memo(
        "event_investigator", ["s0"], core=["unit_0", "unit_1"],
        units=[
            _unit("unit_0", "core", _findings(
                event=_event(local_unit_ids=("unit_0", "unit_1")),
            )),
            _unit("unit_1", "core", _findings()),
        ],
    )

    assert memo.units[0].findings.event_chains[0].local_unit_ids == (
        "unit_0", "unit_1",
    )


def test_duplicate_finding_identity_is_collected_once_instead_of_rejecting_memo():
    collector = ShardMemoCollector([{
        "shard_id": "s0", "core_local_unit_ids": ["unit_0", "unit_1"],
    }])
    collector.add(_memo(
        "event_investigator", ["s0"], core=["unit_0", "unit_1"],
        units=[
            _unit("unit_0", "core", _findings(
                event=_event(local_unit_ids=("unit_0", "unit_1")),
            )),
            _unit("unit_1", "core", _findings(
                event=_event(local_unit_ids=("unit_0", "unit_1")),
            )),
        ],
    ))

    result = collector.collect()
    assert len(result.findings.event_chains) == 1


def test_collection_preserves_all_five_typed_finding_collections():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "archive_lore", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(
            narrative={
                "narrative_id": "lore-a", "summary": "档案背景。",
                "evidence": [_evidence("source-lore")],
            },
            entity=_entity(),
            event=_event(),
            asset={
                "asset_id": "asset-a", "name": "静态资产",
                "evidence": [_evidence("source-asset")],
            },
            unresolved={
                "unresolved_id": "unknown-a", "reference_type": "story",
                "relation_source_id": "event-a", "relation_target_id": "story-a",
                "reason": "无法定位。", "evidence": [_evidence("source-unresolved")],
            },
        ))],
    ))

    findings = collector.collect().findings

    assert len(findings.archive_narratives) == 1
    assert len(findings.entities) == 1
    assert len(findings.event_chains) == 1
    assert len(findings.reference_assets) == 1
    assert len(findings.unresolved) == 1


def test_overlap_findings_merge_into_core_and_union_event_links_and_evidence():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(
            event=_event(entity_ids=("entity-a",), source_id="source-a"),
        ))],
    ))
    collector.add(_memo(
        "evidence_auditor", ["s1"], overlap=["unit_0"],
        units=[_unit("unit_0", "overlap", _findings(
            event=_event(
                entity_ids=("entity-b",), source_id="source-b", local_unit_ids=(),
            ),
            entity=_entity("overlap-only", "source-overlap"),
        ))],
    ))

    result = collector.collect()

    event = result.findings.event_chains[0]
    assert event.entity_ids == ("entity-a", "entity-b")
    assert [ref.source_item_ids for ref in event.evidence] == [("source-a",), ("source-b",)]
    assert [item.entity_id for item in result.findings.entities] == []
    assert result.units[0].overlap_observed_in == ("evidence_auditor",)


def test_overlap_without_core_owner_does_not_publish_and_reports_missing():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "archive_lore", ["s1"], overlap=["unit_0"],
        units=[_unit("unit_0", "overlap", _findings(entity=_entity("orphan")))],
    ))

    result = collector.collect()

    assert result.units == ()
    assert result.findings.entities == ()
    assert result.missing_core_local_unit_ids == ("unit_0", "unit_1")


def test_duplicate_core_and_scalar_conflict_are_reported_deterministically():
    first = _memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(event=_event()))],
    )
    second = _memo(
        "evidence_auditor", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(event=_event(source_id="source-b", text="另一个事件。")))],
    )
    left = ShardMemoCollector(_manifest())
    left.add(second)
    left.add(first)
    right = ShardMemoCollector(_manifest())
    right.add(first)
    right.add(second)

    left_result = left.collect()
    right_result = right.collect()

    assert left_result.model_dump() == right_result.model_dump()
    assert left_result.duplicate_core_local_unit_ids == ("unit_0",)
    assert left_result.conflicting_finding_ids == ("event_chains:chain-a:0",)
    assert left_result.complete is False


def test_wrong_manifest_ownership_is_reported_without_publishing_findings():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "cartographer", ["s0"], core=["unit_1"],
        units=[_unit(
            "unit_1", "core", _findings(), disposition="intentionally_unmodeled",
        )],
    ))

    result = collector.collect()

    assert result.invalid_unit_ownership == ("unit_1",)
    assert result.conflict_local_unit_ids == ("unit_1",)
    assert result.findings.entities == ()


def test_non_modeled_unit_findings_do_not_reject_memo_or_publish_claims():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "archive_lore", ["s0"], core=["unit_0"],
        units=[_unit(
            "unit_0", "core", _findings(entity=_entity("mechanical")),
            disposition="intentionally_unmodeled",
        )],
    ))

    result = collector.collect()
    assert result.units[0].disposition == "intentionally_unmodeled"
    assert result.findings.entities == ()


def test_empty_lead_result_keeps_all_child_findings():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(
            event=_event(), entity=_entity(), narrative={
                "narrative_id": "lore-a", "summary": "档案背景。",
                "evidence": [_evidence("source-lore")],
            },
        ))],
    ))
    collected = collector.collect()
    before_lead = collected.findings.model_dump()
    lead = LeadResearchResult()

    assert lead.decisions.named_finding_ids() == ()
    assert collected.findings.event_chains
    assert collected.findings.entities
    assert collected.findings.archive_narratives
    assert collected.findings.model_dump() == before_lead


def test_missing_core_coverage_maps_to_deterministic_shard_ids():
    collector = ShardMemoCollector(_manifest())
    collector.add(_memo(
        "event_investigator", ["s0", "s1"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings())],
    ))

    result = collector.collect()

    assert result.missing_core_local_unit_ids == ("unit_1",)
    assert result.missing_shard_ids == ("s1",)


def test_finding_and_evidence_conflicts_are_diagnostics_not_completion_gates():
    collector = ShardMemoCollector(_manifest())
    conflicting_event = _event(source_id="source-a", text="第二种表述。")
    conflicting_event["evidence"] = [_evidence("source-a", "不同证据措辞。")]
    collector.add(_memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings(
            event=_event(source_id="source-a", text="第一种表述。"),
        ))],
    ))
    collector.add(_memo(
        "evidence_auditor", ["s1"], core=["unit_1"],
        units=[_unit("unit_1", "core", _findings(), disposition="modeled")],
    ))
    collector.add(_memo(
        "evidence_auditor", ["s1"], overlap=["unit_0"],
        units=[_unit("unit_0", "overlap", _findings(
            event=conflicting_event,
        ))],
    ))

    result = collector.collect()

    assert result.conflicting_finding_ids == ("event_chains:chain-a:0",)
    assert result.evidence_conflicts == ("evidence:source-a",)
    assert result.complete is True


def test_partial_memo_within_task_lease_is_retained_for_gap_completion():
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Lease:
        core_local_unit_ids = ("unit_0", "unit_1")
        overlap_local_unit_ids = ()

    memo = _memo(
        "event_investigator", ["s0"], core=["unit_0"],
        units=[_unit("unit_0", "core", _findings())],
    )
    tracker = DelegationTracker(
        Events(), memo_collector=ShardMemoCollector((
            {"shard_id": "s0", "core_local_unit_ids": ["unit_0"]},
            {"shard_id": "s1", "core_local_unit_ids": ["unit_1"]},
        )),
    )

    accepted = tracker.accept_memo(
        role="event_investigator",
        expected_shard_ids=("s0", "s1"),
        lease=Lease(),
        output=memo,
    )

    assert accepted is True
    collected = tracker.collect_memos()
    assert collected is not None
    assert len(tracker.memos) == 1
    assert collected.missing_shard_ids == ("s1",)
