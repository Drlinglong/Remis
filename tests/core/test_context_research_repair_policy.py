"""Contract tests for bounded, source-grounded research repair packets."""

from __future__ import annotations

import pytest

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_contract import ContextAnalysisRequest
from scripts.core.services.context_research_repair_policy import build_repair_packet


def _item(source_id: str, key: str) -> SourceItem:
    return SourceItem(
        source_item_id=source_id,
        relative_path="events/demo.yml",
        item_key=key,
        source_order=int(source_id.rsplit("-", 1)[-1]),
        source_text=f"Evidence for {key}",
    )


def _request() -> ContextAnalysisRequest:
    return ContextAnalysisRequest(
        project_id="repair-test",
        source_items=(
            _item("source-1", "remis_crisis.1.desc"),
            _item("source-2", "remis_crisis.1.desc_text"),
            _item("source-3", "unrelated.1.desc"),
        ),
        description_language="zh-CN",
    )


def _findings(*, two_steps: bool = False) -> ContextResearchFindings:
    events = [{
        "chain_id": "crisis",
        "event": "危机开始",
        "sequence": 1,
        "local_unit_ids": ["unit_0"],
        "source_item_ids": ["source-1"],
        "evidence": [{"source_item_ids": ["source-1"]}],
    }]
    if two_steps:
        events.append({
            "chain_id": "crisis",
            "event": "危机继续",
            "sequence": 2,
            "local_unit_ids": ["unit_1"],
            "source_item_ids": ["source-3"],
            "evidence": [{"source_item_ids": ["source-3"]}],
        })
    return ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "remis",
            "name": "Remis",
            "entity_type": "person",
            "summary": "项目中的核心实体。",
            "source_item_ids": ["source-1"],
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
        "event_chains": events,
    })


def test_packet_is_request_bound_and_adds_only_local_siblings():
    packet = build_repair_packet(
        {
            "unknown_entity_links": [{
                "chain_id": "crisis", "sequence": 1, "entity_id": "missing",
                "source_item_ids": ["hallucinated-source"],
            }],
        },
        _findings(),
        request=_request(),
    )

    target = packet.targets[0]
    assert (target.finding_type, target.finding_id, target.sequence) == (
        "event_chain", "crisis", 1,
    )
    assert target.allowed_fields == ("entity_ids",)
    assert target.related_local_unit_ids == ("unit_0",)
    assert target.source_allow_list == ("source-1", "source-2")
    assert "hallucinated-source" not in packet.valid_source_allow_list
    assert packet.model_call_allowed is True


def test_repairable_diagnostic_without_request_cannot_enable_model_call():
    packet = build_repair_packet(
        {"unknown_entity_links": [{"chain_id": "crisis", "sequence": 1}]},
        _findings(),
    )

    assert packet.targets[0].source_allow_list == ()
    assert packet.model_call_allowed is False


def test_discard_only_diagnostic_does_not_request_repair():
    packet = build_repair_packet(
        {"dropped_dynamic_entity_links": [{
            "chain_id": "crisis", "sequence": 1, "entity_id": "generated",
        }]},
        _findings(),
        request=_request(),
    )

    assert packet.targets[0].classification == "discard_only"
    assert packet.targets[0].allowed_fields == ()
    assert packet.model_call_allowed is False


def test_unattributed_safe_drop_is_not_promoted_to_systemic_corruption():
    packet = build_repair_packet(
        {"dropped_resolved_unit_routes": [{
            "unresolved_id": "already-routed",
            "source_item_ids": ["source-1"],
        }]},
        _findings(),
        request=_request(),
    )

    assert packet.systemic_corruption is False
    assert packet.targets[0].classification == "discard_only"
    assert packet.model_call_allowed is False


def test_rejected_entity_evidence_is_dropped_instead_of_retried():
    packet = build_repair_packet(
        {"rejected_entity_evidence_ids": [{
            "entity_id": "remis", "source_item_id": "source-1",
        }]},
        _findings(),
        request=_request(),
    )

    assert packet.targets[0].classification == "discard_only"
    assert packet.targets[0].allowed_fields == ()
    assert packet.model_call_allowed is False


def test_systemic_failure_preserves_valid_results_and_blocks_model():
    packet = build_repair_packet(
        {"schema_validation": [{"detail": "invalid output"}]},
        _findings(),
        request=_request(),
    )

    assert packet.systemic_corruption is True
    assert packet.targets[-1].finding_type == "system"
    assert packet.preserve_valid_results is True
    assert packet.model_call_allowed is False


def test_repair_budget_is_at_most_two_attempts():
    diagnostics = {"unknown_entity_links": [{"chain_id": "crisis", "sequence": 1}]}
    assert build_repair_packet(diagnostics, _findings(), request=_request(), attempt=1).remaining_attempts == 1
    packet = build_repair_packet(diagnostics, _findings(), request=_request(), attempt=2)
    assert packet.remaining_attempts == 0
    assert packet.model_call_allowed is False
    with pytest.raises(ValueError, match="between zero and two"):
        build_repair_packet(diagnostics, _findings(), request=_request(), attempt=3)


def test_repairable_targets_are_planned_in_stable_eight_target_batches():
    findings = ContextResearchFindings.model_validate({
        "event_chains": [{
            "chain_id": "crisis", "sequence": sequence,
            "event": f"危机步骤 {sequence}",
            "local_unit_ids": [f"unit_{sequence}"],
            "source_item_ids": ["source-1"],
            "evidence": [{"source_item_ids": ["source-1"]}],
        } for sequence in range(13)],
    })
    packet = build_repair_packet(
        {"unknown_entity_links": [
            {"chain_id": "crisis", "sequence": sequence, "entity_id": "missing"}
            for sequence in range(13)
        ]},
        findings,
        request=_request(),
    )

    assert packet.batch_count == 2
    assert packet.batch_sizes == (8, 5)
    assert [len(batch.target_keys) for batch in packet.repair_batches] == [8, 5]
    assert packet.repair_batches[0].target_keys[0] == "event_chain:crisis:0"
    assert packet.repair_batches[1].target_keys[-1] == "event_chain:crisis:12"
    assert all(target.finding_id == "crisis" for target in packet.targets)


def test_coverage_gate_only_blocks_key_uninspected_shards():
    packet = build_repair_packet(
        {"coverage_dispositions": [
            {"shard_id": "key", "disposition": "uninspected"},
            {"shard_id": "optional", "disposition": "uninspected"},
            {"shard_id": "excluded", "disposition": "excluded_by_policy"},
        ]},
        _findings(),
        request=_request(),
        key_shards=("key",),
    )

    assert packet.coverage.blocking_uninspected_shards == ("key",)
    assert packet.coverage.blocks_key_shard_gate is True


def test_intentionally_unmodeled_shard_explains_uncovered_sources():
    packet = build_repair_packet(
        {
            "coverage_dispositions": [{
                "shard_id": "static-ui",
                "disposition": "intentionally_unmodeled",
                "source_item_ids": ["source-3"],
                "reason": "Mechanical label with no archive value.",
            }],
            "uncovered_source_item_ids": ["source-3"],
        },
        _findings(),
        request=_request(),
    )

    assert [item.shard_id for item in packet.coverage.dispositions] == ["static-ui"]
    assert packet.coverage.blocks_key_shard_gate is False


def test_coverage_dispositions_survive_compiler_diagnostics_envelope():
    packet = build_repair_packet(
        {
            "model": {"coverage_dispositions": [{
                "shard_id": "events/demo.yml",
                "disposition": "uninspected",
                "key_shard": True,
                "source_item_ids": ["source-1"],
            }]},
            "compiler": {"uncovered_source_item_ids": ["source-1"]},
        },
        _findings(),
        request=_request(),
    )

    assert packet.coverage.blocks_key_shard_gate is True
    assert packet.coverage.blocking_uninspected_shards == ("events/demo.yml",)


def test_same_chain_without_sequence_is_ambiguous_systemic_target():
    packet = build_repair_packet(
        {"unknown_entity_links": [{"chain_id": "crisis", "entity_id": "missing"}]},
        _findings(two_steps=True),
        request=_request(),
    )

    assert packet.systemic_corruption is True
    assert any(
        target.finding_type == "system"
        and "ambiguous_event_identity:crisis" in target.finding_id
        for target in packet.targets
    )
