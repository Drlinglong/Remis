"""Run a frozen Context Archive demo benchmark with one command.

Examples:
    python scripts/developer_tools/context_archive_demo_benchmark.py horizon-signal
    python scripts/developer_tools/context_archive_demo_benchmark.py toxic-god
    python scripts/developer_tools/context_archive_demo_benchmark.py toxic-god \
        --analysis-run-id <run-id> --database <recovery.sqlite>

The private benchmark corpus owns the copyrighted fixtures and human gold sets.
This runner owns target discovery, identity gates, scoring, baseline comparison,
and stable JSON/Markdown output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.developer_tools.context_archive_benchmark import (
    build_analysis_run_snapshot,
    build_snapshot,
    render_markdown,
)

@dataclass(frozen=True)
class DemoDefinition:
    name: str
    name_zh: str
    fixture_path: str
    fixture_sha256: str
    gold_path: str
    gold_sha256: str
    source_snapshot_hash: str
    expected_source_items: int
    expected_local_units: int
    baseline_target: str
    baseline: dict[str, float]


DEMOS = {
    "horizon-signal": DemoDefinition(
        name="Horizon Signal",
        name_zh="视界信号",
        fixture_path="projects/stellaris/horizonsignal_demo/horizonsignal_l_english.yml",
        fixture_sha256="aa3333a36f36492c8c4bdd62d9cde604babda9316f618dbfceace9a8abd896f1",
        gold_path=(
            "corpus/stellaris/context-archive-gold/horizon-signal/2026-08-04/"
            "horizon_signal_event_chain_gold.md"
        ),
        gold_sha256="43da9fee5345c2974ce7531af9bf6c35d8d09f160409acf0170f10b0495f6c4f",
        source_snapshot_hash="ad78458b26a12f71d46c2994d7ba96a2e16bcbcf93607a7492a252dba5a9e558",
        expected_source_items=347,
        expected_local_units=95,
        baseline_target="release:8a3c3a80-f939-459d-a617-5b82f123c5c2",
        baseline={
            "delivery_precision": 0.9767441860465116,
            "delivery_recall": 0.9032258064516129,
            "delivery_f1": 0.9385474860335196,
            "relaxed_chain_accuracy": 0.7849462365591398,
            "strict_clustering_pairwise_f1": 0.6552,
            "exact_relation_accuracy": 0.8842105263157894,
        },
    ),
    "toxic-god": DemoDefinition(
        name="Quest for the Toxic God",
        name_zh="毒圣骑士",
        fixture_path=(
            "corpus/stellaris/context-archive-gold/toxic-god/2026-08-04/"
            "toxic_god_context_benchmark_l_english.yml"
        ),
        fixture_sha256="1bce35fe8d34b995b473e5a3e59c71aec41bde8076ab8d3e90a16926ff54dad1",
        gold_path=(
            "corpus/stellaris/context-archive-gold/toxic-god/2026-08-04/"
            "toxic_god_context_archive_gold.md"
        ),
        gold_sha256="0fd12bb6e0c0359fbf84a991690994b50055ba4b594468c8a0c9226b78f0a66b",
        source_snapshot_hash="49790155728d9d88481d9255b125f23978342ee325515555e68fb4ce9e4eaa0c",
        expected_source_items=421,
        expected_local_units=201,
        baseline_target="analysis_run:b26e6ddb-07d5-4f7e-9182-e15752ed3810",
        baseline={
            "delivery_precision": 0.8235294117647058,
            "delivery_recall": 0.7777777777777778,
            "delivery_f1": 0.8,
            "relaxed_chain_accuracy": 0.6984126984126984,
            "strict_clustering_pairwise_f1": 0.432510885341074,
            "exact_relation_accuracy": 0.4577114427860697,
        },
    ),
}


def resolve_corpus_root(explicit: Path | None = None) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit)
    configured = os.environ.get("REMIS_AVENTINE_BENCHMARK_CORPUS")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            PROJECT_ROOT.parent / "remis-aventine-benchmark-corpus",
            PROJECT_ROOT.parent.parent / "remis-aventine-benchmark-corpus",
        ]
    )
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "corpus").is_dir() and (resolved / "projects").is_dir():
            return resolved
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise ValueError(
        "Remis Aventine benchmark corpus was not found. Pass --corpus-root or set "
        f"REMIS_AVENTINE_BENCHMARK_CORPUS. Searched: {searched}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_artifact(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"Missing {label}: {path}")
    actual = _sha256(path)
    if actual.casefold() != expected_sha256.casefold():
        raise ValueError(
            f"{label} identity mismatch: expected={expected_sha256}, actual={actual}, "
            f"path={path}"
        )


def _select_latest_target(database: Path, source_snapshot_hash: str) -> tuple[str, str]:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        release_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(context_releases)")
        }
        release_link_filter = (
            " AND analysis_run_id IS NOT NULL"
            if "analysis_run_id" in release_columns
            else ""
        )
        candidates = [
            ("release", str(row[0]), str(row[1]))
            for row in connection.execute(
                f"""
                SELECT release_id, created_at
                FROM context_releases
                WHERE source_snapshot_hash = ?
                {release_link_filter}
                """,
                (source_snapshot_hash,),
            )
        ]
        candidates.extend(
            ("analysis_run", str(row[0]), str(row[1]))
            for row in connection.execute(
                """
                SELECT run_id, created_at
                FROM context_analysis_runs
                WHERE source_snapshot_hash = ?
                """,
                (source_snapshot_hash,),
            )
        )
    finally:
        connection.close()
    if not candidates:
        raise ValueError(
            "No Context Release or Analysis Run matches source snapshot "
            f"{source_snapshot_hash}"
        )
    kind, target_id, _created_at = max(
        candidates,
        key=lambda item: (item[2], item[0] == "release"),
    )
    return kind, target_id


def _flat_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "delivery_precision": float(metrics["delivery_precision"]),
        "delivery_recall": float(metrics["delivery_recall"]),
        "delivery_f1": float(metrics["delivery_f1"]),
        "relaxed_chain_accuracy": float(metrics["relaxed_chain_accuracy"]),
        "strict_clustering_pairwise_f1": float(
            metrics["strict_clustering_pairwise"]["f1"]
        ),
        "exact_relation_accuracy": float(metrics["exact_relation_accuracy"]),
    }


def _baseline_comparison(
    metrics: dict[str, Any], baseline: dict[str, float]
) -> dict[str, dict[str, float]]:
    current = _flat_metrics(metrics)
    return {
        key: {
            "current": value,
            "baseline": float(baseline[key]),
            "delta_percentage_points": round((value - float(baseline[key])) * 100, 6),
        }
        for key, value in current.items()
    }


def _validate_snapshot(snapshot: dict[str, Any], demo: DemoDefinition) -> None:
    target = snapshot["target"]
    if target["source_snapshot_hash"] != demo.source_snapshot_hash:
        raise ValueError(
            "Benchmark target belongs to a different source snapshot: "
            f"expected={demo.source_snapshot_hash}, actual={target['source_snapshot_hash']}"
        )
    if int(target["source_item_count"]) != demo.expected_source_items:
        raise ValueError(
            "Benchmark source item count mismatch: "
            f"expected={demo.expected_source_items}, actual={target['source_item_count']}"
        )
    if int(snapshot["metrics"]["unit_count"]) != demo.expected_local_units:
        raise ValueError(
            "Benchmark local unit count mismatch: "
            f"expected={demo.expected_local_units}, "
            f"actual={snapshot['metrics']['unit_count']}"
        )


def render_demo_markdown(snapshot: dict[str, Any]) -> str:
    demo = snapshot["demo"]
    comparison = snapshot["baseline_comparison"]
    labels = {
        "delivery_precision": "投递 Precision",
        "delivery_recall": "投递 Recall",
        "delivery_f1": "投递 F1",
        "relaxed_chain_accuracy": "宽松事件链正确率",
        "strict_clustering_pairwise_f1": "严格聚类 Pairwise F1",
        "exact_relation_accuracy": "关系类型完全正确率",
    }
    lines = [
        f"# {demo['name_zh']} Context Archive Demo 成绩单",
        "",
        f"- Demo: `{demo['slug']}`",
        f"- Target: `{snapshot['target']['kind']}:{snapshot['target']['id']}`",
        f"- Baseline: `{demo['baseline_target']}`",
        f"- Fixture SHA-256: `{demo['fixture_sha256']}`",
        f"- Gold SHA-256: `{demo['gold_sha256']}`",
        "",
        "## 与冻结基线比较",
        "",
        "| 指标 | 当前 | 基线 | 差值 |",
        "|---|---:|---:|---:|",
    ]
    for key, label in labels.items():
        row = comparison[key]
        lines.append(
            f"| {label} | {row['current']:.2%} | {row['baseline']:.2%} | "
            f"{row['delta_percentage_points']:+.2f} pp |"
        )
    detail = render_markdown(snapshot).replace(
        "# Context Archive 金标审核报告", "## 完整逐单元审核", 1
    )
    lines.extend(["", detail.rstrip(), ""])
    return "\n".join(lines)


def run_demo(
    demo_slug: str,
    *,
    database: Path,
    corpus_root: Path,
    output_dir: Path,
    release_id: str | None = None,
    analysis_run_id: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    demo = DEMOS[demo_slug]
    fixture_path = corpus_root / demo.fixture_path
    gold_path = corpus_root / demo.gold_path
    _validate_artifact(fixture_path, demo.fixture_sha256, "demo fixture")
    _validate_artifact(gold_path, demo.gold_sha256, "demo gold")

    if release_id:
        target_kind, target_id = "release", release_id
    elif analysis_run_id:
        target_kind, target_id = "analysis_run", analysis_run_id
    else:
        target_kind, target_id = _select_latest_target(
            database, demo.source_snapshot_hash
        )
    if target_kind == "release":
        snapshot = build_snapshot(
            target_id, gold_path, {}, {}, database_path=database
        )
    else:
        snapshot = build_analysis_run_snapshot(
            target_id, gold_path, {}, {}, database_path=database
        )
    _validate_snapshot(snapshot, demo)
    snapshot["demo"] = {
        **asdict(demo),
        "slug": demo_slug,
        "corpus_root": str(corpus_root),
        "fixture_path": str(fixture_path),
        "gold_path": str(gold_path),
    }
    snapshot["baseline_comparison"] = _baseline_comparison(
        snapshot["metrics"], demo.baseline
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{demo_slug}-{target_kind}-{target_id[:8]}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_demo_markdown(snapshot), encoding="utf-8")
    return json_path, markdown_path, snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=sorted(DEMOS))
    parser.add_argument("--database", type=Path, default=Path(PROJECTS_DB_PATH))
    parser.add_argument("--corpus-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--release-id")
    target.add_argument("--analysis-run-id")
    args = parser.parse_args()

    corpus_root = resolve_corpus_root(args.corpus_root)
    output_dir = args.output_dir or (
        PROJECT_ROOT / "outputs" / "context-archive-benchmarks" / args.demo
    )
    json_path, markdown_path, snapshot = run_demo(
        args.demo,
        database=args.database,
        corpus_root=corpus_root,
        output_dir=output_dir,
        release_id=args.release_id,
        analysis_run_id=args.analysis_run_id,
    )
    print(
        json.dumps(
            {
                "demo": args.demo,
                "target": snapshot["target"],
                "metrics": _flat_metrics(snapshot["metrics"]),
                "json_output": str(json_path.resolve()),
                "markdown_output": str(markdown_path.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
