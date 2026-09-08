"""Case-level aggregation for the Issue #198 archive A/B benchmark."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import random
from typing import Any, Iterable, Mapping, Sequence

from scripts.developer_tools.archive_ab_contract import Usage
from scripts.developer_tools.archive_ab_runner import BlindResult


def _case_value(result: BlindResult, arm: str) -> float:
    return 1.0 if result.winner == arm else 0.0


def _bootstrap(values: Sequence[float], seed: int, samples: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    low = means[max(0, int(samples * 0.025))]
    high = means[min(samples - 1, int(samples * 0.975))]
    return low, high


def _group_results(results: Iterable[BlindResult], case_kind_by_id: Mapping[str, str]) -> dict[str, list[BlindResult]]:
    groups: dict[str, list[BlindResult]] = {}
    for result in results:
        groups.setdefault(case_kind_by_id.get(result.case_id, "unknown"), []).append(result)
    return groups


def _collapse_clusters(results: Sequence[BlindResult], cluster_by_id: Mapping[str, str]) -> list[BlindResult]:
    clusters: dict[str, list[BlindResult]] = {}
    for result in results:
        clusters.setdefault(cluster_by_id.get(result.case_id, result.case_id), []).append(result)
    collapsed: list[BlindResult] = []
    for cluster_results in clusters.values():
        if len(cluster_results) == 1:
            collapsed.append(cluster_results[0])
            continue
        winners = {item.winner for item in cluster_results}
        representative = cluster_results[0]
        usage = _usage_sum(cluster_results)
        collapsed.append(replace(
            representative,
            winner=next(iter(winners)) if len(winners) == 1 else "tie",
            confidence=min(item.confidence for item in cluster_results),
            error_tags=tuple(sorted({tag for item in cluster_results for tag in item.error_tags})),
            needs_adjudication=representative.needs_adjudication or len(winners) > 1,
            usage=usage,
            translation_usage_by_arm={
                arm: _usage_values(item.translation_usage_by_arm.get(arm, Usage()) for item in cluster_results)
                for arm in ("A", "B")
            },
            judge_usage=_usage_values(item.judge_usage for item in cluster_results),
            error_tags_by_arm={
                arm: tuple(sorted({tag for item in cluster_results for tag in item.error_tags_by_arm.get(arm, ())}))
                for arm in ("A", "B")
            },
        ))
    return collapsed


def _group_summary(results: Sequence[BlindResult], seed: int) -> dict[str, Any]:
    counts = Counter(result.winner for result in results)
    a_rate = [_case_value(result, "A") for result in results]
    b_rate = [_case_value(result, "B") for result in results]
    return {
        "case_count": len(results),
        "winner_counts": {key: counts.get(key, 0) for key in ("A", "B", "tie")},
        "win_rate": {
            "A": sum(a_rate) / len(a_rate) if a_rate else 0.0,
            "B": sum(b_rate) / len(b_rate) if b_rate else 0.0,
        },
        "bootstrap_95_ci": {
            "A": _bootstrap(a_rate, seed, 1000),
            "B": _bootstrap(b_rate, seed + 1, 1000),
        },
        "major_context_error_cases": sum(bool(set(result.error_tags) & {
            "wrong_referent", "broken_causality", "branch_misread", "missing_story_context",
        }) for result in results),
        "major_context_error_cases_by_arm": {
            arm: sum(bool(set(result.error_tags_by_arm.get(arm, ())) & {
                "wrong_referent", "broken_causality", "branch_misread", "missing_story_context",
            }) for result in results)
            for arm in ("A", "B")
        },
        "hard_format_error_cases": sum(not all(check.passed for check in result.hard_checks.values()) for result in results),
        "judge_disagreement_cases": sum(result.needs_adjudication for result in results),
    }


def _usage_sum(results: Sequence[BlindResult]) -> Usage:
    total = Usage()
    for result in results:
        total += result.usage
    return total


def _usage_values(values: Iterable[Usage]) -> Usage:
    total = Usage()
    for value in values:
        total += value
    return total


def summarize(
    results: Sequence[BlindResult],
    case_kind_by_id: Mapping[str, str],
    *,
    archive_generation: Usage = Usage(),
    baseline_major_errors: int | None = None,
    case_cluster_by_id: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Aggregate one vote per chain/batch case and calculate incremental cost."""

    canonical_results = _collapse_clusters(results, case_cluster_by_id or {})
    groups = _group_results(canonical_results, case_kind_by_id)
    translation_by_arm = {
        arm: _usage_values(result.translation_usage_by_arm.get(arm, Usage()) for result in canonical_results)
        for arm in ("A", "B")
    }
    translation = translation_by_arm["A"] + translation_by_arm["B"]
    judge = _usage_values(result.judge_usage for result in canonical_results)
    experiment_total = translation + judge + archive_generation
    major_errors_by_arm = {
        arm: sum(bool(set(result.error_tags_by_arm.get(arm, ())) & {
            "wrong_referent", "broken_causality", "branch_misread", "missing_story_context",
        }) for result in canonical_results)
        for arm in ("A", "B")
    }
    avoided = max(0, major_errors_by_arm["A"] - major_errors_by_arm["B"])
    feature_incremental_cost = (
        translation_by_arm["B"].cost_usd - translation_by_arm["A"].cost_usd + archive_generation.cost_usd
    )
    return {
        "schema_version": "remis-archive-ab-score-v1",
        "unit_of_vote": "event_chain_case_or_reference_batch_case",
        "overall": _group_summary(canonical_results, 198),
        "by_case_kind": {key: _group_summary(value, 198 + index * 10) for index, (key, value) in enumerate(sorted(groups.items()))},
        "usage": {
            "translation": translation.as_dict(),
            "translation_by_arm": {
                arm: usage.as_dict() for arm, usage in translation_by_arm.items()
            },
            "judge": judge.as_dict(),
            "archive_generation": archive_generation.as_dict(),
            "experiment_total": experiment_total.as_dict(),
            "experiment_total_cost_usd": experiment_total.cost_usd,
            "incremental_cost_usd": feature_incremental_cost,
            "b_over_a_incremental_cost_usd": feature_incremental_cost,
            "avoided_major_context_errors": avoided,
            "major_context_error_delta_b_minus_a": major_errors_by_arm["B"] - major_errors_by_arm["A"],
            "cost_per_avoided_major_error_usd": (feature_incremental_cost / avoided) if avoided else None,
        },
        "case_ids": [result.case_id for result in canonical_results],
    }


__all__ = ["summarize"]
