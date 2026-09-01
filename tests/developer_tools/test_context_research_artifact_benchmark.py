from __future__ import annotations

import json
from pathlib import Path

from scripts.developer_tools.context_research_artifact_benchmark import score_artifact


def _gold(path: Path) -> None:
    path.write_text(
        "\n".join((
            "| Unit | Keys | Chain | Relation | Note | Confidence |",
            "| --- | --- | --- | --- | --- | --- |",
            "| `unit_0` | a | `chain-a` | `primary_member` | event | `high` |",
            "| `unit_1` | b | `chain-a` | `primary_member` | event | `high` |",
            "| `unit_2` | c | `reference` | `reference_asset` | lore | `high` |",
        )),
        encoding="utf-8",
    )


def test_scores_routes_cost_and_clustering(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.md"
    trace = tmp_path / "trace.json"
    _gold(gold)
    artifact.write_text(json.dumps({
        "draft": {
            "event_chains": [{"chain_id": "predicted", "local_unit_ids": ["unit_0", "unit_1"]}],
            "reference_assets": [{"local_unit_id": "unit_2"}],
            "diagnostics": [],
        },
        "execution": {"elapsed_seconds": 12.5},
    }), encoding="utf-8")
    trace.write_text(json.dumps({
        "usage": {"summary": {"totals": {"cost": 0.125}}},
    }), encoding="utf-8")

    result = score_artifact(artifact, gold, trace_path=trace, label="perfect")

    assert result["metrics"]["primary"]["f1"] == 1.0
    assert result["metrics"]["reference"]["f1"] == 1.0
    assert result["metrics"]["strict_clustering_pairwise"]["f1"] == 1.0
    assert result["metrics"]["relaxed_chain_accuracy"] == 1.0
    assert result["cost_usd"] == 0.125
    assert result["elapsed_seconds"] == 12.5


def test_scores_native_three_axis_gold_and_independent_entities(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({
        "assignments": [
            {
                "unit_id": "unit_0", "chain_id": "chain-a",
                "content_role": "event_narrative", "delivery_route": "event",
            },
            {
                "unit_id": "unit_1", "chain_id": "archive",
                "content_role": "background_narrative", "delivery_route": "none",
            },
            {
                "unit_id": "unit_2", "chain_id": "reference",
                "content_role": "static_reference", "delivery_route": "reference",
            },
        ],
        "entities": [{
            "canonical_name": "Syamelle", "source_unit_ids": ["unit_0", "unit_1"],
        }],
    }), encoding="utf-8")
    artifact.write_text(json.dumps({
        "draft": {
            "event_chains": [{"chain_id": "predicted", "local_unit_ids": ["unit_0"]}],
            "reference_assets": [{"local_unit_id": "unit_2"}],
            "entities": [{
                "name": "夏梅尔", "aliases": ["Syamelle"],
                "local_unit_ids": ["unit_0", "unit_1"],
            }],
            "diagnostics": {"model": {"route_resolution": {
                "content_roles": {
                    "unit_0": "event_narrative",
                    "unit_1": "background_narrative",
                    "unit_2": "static_reference",
                },
                "delivery_routes": {
                    "unit_0": "event", "unit_1": "none", "unit_2": "reference",
                },
            }}},
        },
    }), encoding="utf-8")

    result = score_artifact(artifact, gold)

    assert result["corpus"]["native_three_axis_gold"] is True
    assert result["metrics"]["content_role"]["accuracy"] == 1.0
    assert result["metrics"]["delivery_route"]["accuracy"] == 1.0
    assert result["metrics"]["entity_names"]["f1"] == 1.0
    assert result["metrics"]["entity_unit_mentions"]["f1"] == 1.0


def test_reports_wrong_route_as_precision_and_recall_loss(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.md"
    _gold(gold)
    artifact.write_text(json.dumps({
        "draft": {
            "event_chains": [{"chain_id": "wrong", "local_unit_ids": ["unit_0", "unit_2"]}],
            "reference_assets": [],
            "diagnostics": ["context_research_incomplete: missing memo"],
        },
    }), encoding="utf-8")

    result = score_artifact(artifact, gold)

    assert result["metrics"]["primary"]["true_positive"] == 1
    assert result["metrics"]["primary"]["false_positive"] == 1
    assert result["metrics"]["primary"]["false_negative"] == 1
    assert result["metrics"]["reference"]["recall"] == 0.0
    assert result["publishable"] is False


def test_publishable_reads_run_diagnostics_and_conflicts_are_not_double_correct(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.md"
    _gold(gold)
    artifact.write_text(json.dumps({
        "draft": {
            "event_chains": [{
                "chain_id": "predicted",
                "local_unit_ids": ["unit_0", "unit_1", "unit_2"],
            }],
            "reference_assets": [{"local_unit_id": "unit_2"}],
            "diagnostics": {
                "compiler": {"published_counts": {"event_chains": 1}},
                "run": {"status": "incomplete", "publishable": False},
            },
        },
    }), encoding="utf-8")

    result = score_artifact(artifact, gold)

    assert result["publishable"] is False
    assert result["metrics"]["route_conflict_count"] == 1
    assert result["metrics"]["route_accuracy"] == 2 / 3


def test_cost_fallback_preserves_zero_and_sums_smoke_usage_records(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.md"
    _gold(gold)
    artifact.write_text(json.dumps({
        "draft": {"diagnostics": {"run": {"status": "complete", "publishable": True}}},
        "usage": [
            {"event": "lead", "usage": {"cost": 0.0}},
            {"event": "repair", "usage": {"cost": 0.25}},
        ],
        "elapsed_seconds": 3.5,
    }), encoding="utf-8")

    result = score_artifact(artifact, gold)

    assert result["cost_usd"] == 0.25
    assert result["elapsed_seconds"] == 3.5


def test_scores_corpus_read_amplification_and_legacy_denominator_only(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    gold = tmp_path / "gold.md"
    _gold(gold)
    artifact.write_text(json.dumps({
        "source_items": [{"source_item_id": "source-1", "text": "alpha beta"}],
        "draft": {"diagnostics": {"run": {"status": "complete", "publishable": True}}},
    }), encoding="utf-8")

    result = score_artifact(artifact, gold)

    metric = result["metrics"]["corpus_read_amplification"]
    assert metric["numerator_tokens"] is None
    assert metric["denominator_tokens"] == 2
    assert metric["value"] is None
    assert metric["backfill_status"] == "denominator_only"
