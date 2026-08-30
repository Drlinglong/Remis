import sqlite3
from pathlib import Path

from scripts.developer_tools.context_archive_demo_benchmark import (
    DEMOS,
    _baseline_comparison,
    _select_latest_target,
    resolve_corpus_root,
)


def test_demo_catalog_keeps_gold_fixtures_separate():
    horizon = DEMOS["horizon-signal"]
    toxic = DEMOS["toxic-god"]

    assert horizon.source_snapshot_hash != toxic.source_snapshot_hash
    assert horizon.fixture_sha256 != toxic.fixture_sha256
    assert horizon.gold_path != toxic.gold_path
    assert horizon.expected_local_units == 95
    assert toxic.expected_local_units == 201


def test_resolve_corpus_root_accepts_explicit_private_corpus(tmp_path: Path):
    (tmp_path / "corpus").mkdir()
    (tmp_path / "projects").mkdir()

    assert resolve_corpus_root(tmp_path) == tmp_path.resolve()


def test_select_latest_target_uses_exact_source_snapshot(tmp_path: Path):
    database = tmp_path / "context.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE context_releases (
            release_id TEXT PRIMARY KEY,
            source_snapshot_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE context_analysis_runs (
            run_id TEXT PRIMARY KEY,
            source_snapshot_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO context_releases VALUES (
            'release-exact', 'snapshot-exact', '2026-08-04T00:00:00Z'
        );
        INSERT INTO context_analysis_runs VALUES (
            'run-other', 'snapshot-other', '2026-08-04T02:00:00Z'
        );
        INSERT INTO context_analysis_runs VALUES (
            'run-exact', 'snapshot-exact', '2026-08-04T01:00:00Z'
        );
        """
    )
    connection.commit()
    connection.close()

    assert _select_latest_target(database, "snapshot-exact") == (
        "analysis_run",
        "run-exact",
    )


def test_select_latest_target_ignores_unlinked_legacy_release(tmp_path: Path):
    database = tmp_path / "context.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE context_releases (
            release_id TEXT PRIMARY KEY,
            source_snapshot_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            analysis_run_id TEXT
        );
        CREATE TABLE context_analysis_runs (
            run_id TEXT PRIMARY KEY,
            source_snapshot_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO context_releases VALUES (
            'legacy-release', 'snapshot-exact', '2026-08-04T02:00:00Z', NULL
        );
        INSERT INTO context_analysis_runs VALUES (
            'persisted-run', 'snapshot-exact', '2026-08-04T01:00:00Z'
        );
        """
    )
    connection.commit()
    connection.close()

    assert _select_latest_target(database, "snapshot-exact") == (
        "analysis_run",
        "persisted-run",
    )


def test_baseline_comparison_reports_percentage_point_delta():
    comparison = _baseline_comparison(
        {
            "delivery_precision": 0.82,
            "delivery_recall": 0.78,
            "delivery_f1": 0.80,
            "relaxed_chain_accuracy": 0.70,
            "strict_clustering_pairwise": {"f1": 0.43},
            "exact_relation_accuracy": 0.46,
        },
        {
            "delivery_precision": 0.80,
            "delivery_recall": 0.75,
            "delivery_f1": 0.77,
            "relaxed_chain_accuracy": 0.68,
            "strict_clustering_pairwise_f1": 0.40,
            "exact_relation_accuracy": 0.45,
        },
    )

    assert comparison["delivery_f1"]["delta_percentage_points"] == 3.0
    assert comparison["strict_clustering_pairwise_f1"]["current"] == 0.43
