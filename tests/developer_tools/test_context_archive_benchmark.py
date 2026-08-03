from pathlib import Path

import pytest

from scripts.developer_tools.context_archive_benchmark import (
    BenchmarkSourceItem,
    GoldAssignment,
    PredictedLink,
    UnitResult,
    _best_chain_mapping,
    _release_local_units,
    _release_source_items,
    _metrics,
    parse_gold,
    render_markdown,
)
from scripts.schemas.context import (
    ContextReleaseLocalUnit,
    ContextReleaseManifest,
    ContextReleaseSourceItem,
)


def test_parse_gold_accepts_contiguous_project_sized_unit_set(tmp_path: Path):
    gold = tmp_path / "gold.md"
    gold.write_text(
        "\n".join(
            [
                "| Unit | Keys | Chain | Relation | Note | Confidence |",
                "|---|---|---|---|---|---|",
                "| `unit_0` | `a` | `arc_a` | `primary_member` | first | `high` |",
                "| `unit_1` | `b` | `arc_b` | `theme_related` | second | `medium` |",
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_gold(
        gold,
        {"unit_1": "supporting_context"},
        {"unit_1": "人工确认其为事件链推进所需的 supporting context。"},
    )

    assert list(rows) == ["unit_0", "unit_1"]
    assert rows["unit_1"].relation == "supporting_context"
    assert rows["unit_1"].note == "人工确认其为事件链推进所需的 supporting context。"


def test_best_chain_mapping_allows_multiple_predictions_to_one_gold_chain():
    gold = {
        "unit_0": GoldAssignment("unit_0", "a", "coils", "primary_member", "", "high"),
        "unit_1": GoldAssignment("unit_1", "b", "coils", "primary_member", "", "high"),
    }
    predicted = {
        "unit_0": (PredictedLink("coils_branch_a", "primary_member", 1.0, 1),),
        "unit_1": (PredictedLink("coils_branch_b", "primary_member", 1.0, 1),),
    }

    assert _best_chain_mapping(gold, predicted) == {
        "coils_branch_a": "coils",
        "coils_branch_b": "coils",
    }


def test_metrics_separate_delivery_recall_from_strict_clustering():
    results = [
        _result("unit_0", "arc_a", "predicted_merged"),
        _result("unit_1", "arc_a", "predicted_merged"),
        _result("unit_2", "arc_b", "predicted_merged"),
    ]

    metrics = _metrics(results)

    assert metrics["delivery_recall"] == 1.0
    strict = metrics["strict_clustering_pairwise"]
    assert strict["true_positive_pairs"] == 1
    assert strict["false_positive_pairs"] == 2
    assert strict["false_negative_pairs"] == 0
    assert strict["precision"] == pytest.approx(1 / 3)


def test_render_markdown_keeps_gold_prediction_and_editable_review_fields():
    result = _result("unit_0", "arc_a", "predicted_a")
    snapshot = {
        "release": {
            "release_id": "release-1",
            "source_snapshot_hash": "sha256",
            "model_id": "model",
            "prompt_version": "prompt-v1",
        },
        "metrics": {
            **_metrics([result]),
        },
        "predicted_to_gold_chain_mapping": {"predicted_a": "arc_a"},
        "units": [
            {
                **result.__dict__,
                "predicted_links": [result.predicted_links[0].__dict__],
            }
        ],
    }

    report = render_markdown(snapshot)

    assert "Context Release: `release-1`" in report
    assert "`predicted_a` | `arc_a`" in report
    assert "Human verdict: `未审核`" in report
    assert "unit_0: text" not in report
    assert "text" in report


def test_historical_benchmark_uses_persisted_unit_manifest_after_builder_change(
    monkeypatch,
):
    manifest_source_items = [
        ContextReleaseSourceItem(
            source_item_id="source-1",
            source_revision_id="revision-source-1",
            relative_path="localisation/main.yml",
            item_key="first",
            source_order=0,
            source_ref="localisation/main.yml::0",
            content="Persisted first",
            content_hash="hash-source-1",
        ),
        ContextReleaseSourceItem(
            source_item_id="source-2",
            source_revision_id="revision-source-2",
            relative_path="localisation/main.yml",
            item_key="second",
            source_order=1,
            source_ref="localisation/main.yml::1",
            content="Persisted second",
            content_hash="hash-source-2",
        ),
    ]
    manifest = ContextReleaseManifest(
        source_items=manifest_source_items,
        local_units=[
            ContextReleaseLocalUnit(
                local_unit_id="persisted-unit",
                unit_key="persisted-key",
                unit_order=0,
                source_item_ids=["source-2", "source-1"],
            )
        ],
    )

    def fail_if_builder_runs(_items):
        pytest.fail("historical benchmark rebuilt a persisted local-unit manifest")

    monkeypatch.setattr(
        "scripts.developer_tools.context_archive_benchmark.ContextLocalUnitBuilder.build",
        fail_if_builder_runs,
    )

    class ManifestOnlyRepository:
        def get_release_manifest(self, _release_id):
            return manifest

        def list_source_items(self, _project_id):
            pytest.fail("historical benchmark consulted mutable project source rows")

    release = type(
        "Release",
        (),
        {
            "release_id": "release-1",
            "project_id": "project-1",
            "metadata": type("Metadata", (), {"analysis_config": {}})(),
        },
    )()
    source_items = _release_source_items(ManifestOnlyRepository(), release)
    units = _release_local_units(source_items, manifest)

    assert [unit.unit_id for unit in units] == ["persisted-unit"]
    assert [item.content for item in source_items] == [
        "Persisted first", "Persisted second"
    ]
    assert [item.source_item_id for item in units[0].items] == [
        "source-2", "source-1"
    ]


def _result(unit_id: str, gold_chain: str, predicted_chain: str) -> UnitResult:
    return UnitResult(
        unit_id=unit_id,
        unit_key=unit_id,
        item_keys=(unit_id,),
        source_text="text",
        gold_chain=gold_chain,
        gold_relation="primary_member",
        gold_confidence="high",
        gold_note="",
        predicted_links=(
            PredictedLink(predicted_chain, "primary_member", 1.0, 1),
        ),
        predicted_state="assigned",
        delivery_verdict="correct_delivery",
        relaxed_chain_verdict="correct",
        relation_verdict="exact",
    )
