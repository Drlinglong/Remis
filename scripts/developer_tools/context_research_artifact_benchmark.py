"""Score a developer Context Research artifact against route-aware gold.

The scorer is deliberately independent of Remis persistence. It reads the
immutable smoke artifact plus its optional trace ledger, computes delivery and
clustering metrics, and can append one compact experiment record to JSONL.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import sys
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.developer_tools.context_research_three_axis_benchmark import (
    CONTENT_ROLES,
    DELIVERY_ROUTES,
    categorical_score,
    load_three_axis_gold,
    predicted_entities,
    predicted_unit_axes,
)


@dataclass(frozen=True)
class BinaryScore:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


def _binary_score(predicted: set[str], expected: set[str]) -> BinaryScore:
    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / (true_positive + false_positive) if predicted else 0.0
    recall = true_positive / (true_positive + false_negative) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BinaryScore(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _draft_routes(draft: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    primary_chains: dict[str, set[str]] = {}
    for chain in draft.get("event_chains") or ():
        chain_id = str(chain.get("chain_id") or "")
        for unit_id in chain.get("local_unit_ids") or ():
            if chain_id:
                primary_chains.setdefault(str(unit_id), set()).add(chain_id)
    # A unit is one route decision.  Preserve multiple event memberships in a
    # stable label for clustering, but never create a second primary vote.
    primary = {
        unit_id: ";".join(sorted(chain_ids))
        for unit_id, chain_ids in primary_chains.items()
    }
    reference = {
        str(asset.get("local_unit_id"))
        for asset in draft.get("reference_assets") or ()
        if asset.get("local_unit_id")
    }
    return primary, reference


def _chain_metrics(
    predicted: dict[str, str], expected: dict[str, str],
) -> tuple[float, BinaryScore, dict[str, Any], dict[str, Any]]:
    overlaps: dict[str, dict[str, int]] = {}
    for unit_id, predicted_chain in predicted.items():
        expected_chain = expected.get(unit_id)
        if expected_chain is None:
            continue
        counts = overlaps.setdefault(predicted_chain, {})
        counts[expected_chain] = counts.get(expected_chain, 0) + 1
    mapping = {
        predicted_chain: max(counts, key=lambda key: (counts[key], key))
        for predicted_chain, counts in overlaps.items()
        if counts
    }
    relaxed_correct = sum(
        mapping.get(predicted_chain) == expected_chain
        for unit_id, expected_chain in expected.items()
        if (predicted_chain := predicted.get(unit_id)) is not None
    )
    relaxed_accuracy = relaxed_correct / len(expected) if expected else 0.0

    units = sorted(set(predicted) | set(expected))
    predicted_pairs = {
        pair for pair in combinations(units, 2)
        if pair[0] in predicted and pair[1] in predicted
        and predicted[pair[0]] == predicted[pair[1]]
    }
    expected_pairs = {
        pair for pair in combinations(units, 2)
        if pair[0] in expected and pair[1] in expected
        and expected[pair[0]] == expected[pair[1]]
    }
    return (
        relaxed_accuracy,
        _binary_score(predicted_pairs, expected_pairs),
        _bcubed_metrics(predicted, expected),
        _chain_attribution(predicted, expected),
    )


def _cluster_label(value: str | None, unit_id: str) -> str:
    return value or f"missing:{unit_id}"


def _bcubed_metrics(
    predicted: Mapping[str, str], expected: Mapping[str, str],
) -> dict[str, Any]:
    """Compute BCubed over gold event units without pairwise explosion."""

    units = sorted(expected)
    if not units:
        return {"unit_count": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    gold_clusters: dict[str, set[str]] = {}
    predicted_clusters: dict[str, set[str]] = {}
    labels = {
        unit_id: _cluster_label(predicted.get(unit_id), unit_id) for unit_id in units
    }
    for unit_id in units:
        gold_clusters.setdefault(expected[unit_id], set()).add(unit_id)
        predicted_clusters.setdefault(labels[unit_id], set()).add(unit_id)
    precisions = []
    recalls = []
    for unit_id in units:
        overlap = len(
            gold_clusters[expected[unit_id]] & predicted_clusters[labels[unit_id]]
        )
        precisions.append(
            overlap / len(predicted_clusters[labels[unit_id]])
        )
        recalls.append(overlap / len(gold_clusters[expected[unit_id]]))
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    return {
        "unit_count": len(units),
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def _chain_attribution(
    predicted: Mapping[str, str], expected: Mapping[str, str], worst_limit: int = 10,
) -> dict[str, Any]:
    """Attribute false-positive pairs and BCubed error to predicted chains."""

    units = sorted(expected)
    chain_members: dict[str, set[str]] = {}
    for unit_id in units:
        for chain_id in _split_chain_label(predicted.get(unit_id)):
            chain_members.setdefault(chain_id, set()).add(unit_id)
    rows = []
    for chain_id, members in sorted(chain_members.items()):
        pairs = list(combinations(sorted(members), 2))
        true_positive = sum(expected[left] == expected[right] for left, right in pairs)
        false_positive = len(pairs) - true_positive
        precision_errors = []
        recall_errors = []
        for unit_id in sorted(members):
            predicted_members = {
                other for other in units
                if chain_id in _split_chain_label(predicted.get(other))
            }
            overlap = len(
                predicted_members
                & {other for other in units if expected[other] == expected[unit_id]}
            )
            precision_errors.append(1.0 - overlap / len(predicted_members))
            recall_errors.append(
                1.0 - overlap / len({
                    other for other in units if expected[other] == expected[unit_id]
                })
            )
        row = {
            "predicted_chain_id": chain_id,
            "unit_count": len(members),
            "gold_chain_ids": sorted({expected[unit_id] for unit_id in members}),
            "true_positive_pair_count": true_positive,
            "false_positive_pair_count": false_positive,
            "bcubed_precision_error": sum(precision_errors) / len(precision_errors),
            "bcubed_recall_error": sum(recall_errors) / len(recall_errors),
        }
        row["bcubed_item_error"] = (
            row["bcubed_precision_error"] + row["bcubed_recall_error"]
        ) / 2.0
        rows.append(row)
    worst = sorted(
        rows,
        key=lambda row: (
            -row["bcubed_item_error"],
            -row["false_positive_pair_count"],
            row["predicted_chain_id"],
        ),
    )[:worst_limit]
    return {"by_predicted_chain": rows, "worst_bcubed_chains": worst}


def _split_chain_label(value: str | None) -> tuple[str, ...]:
    return tuple(sorted({part for part in str(value or "").split(";") if part}))


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _read_trace_cost(artifact: dict[str, Any], trace_path: Path | None) -> float | None:
    if trace_path and trace_path.is_file():
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        cost = _usage_cost(trace)
        if cost is not None:
            return cost
    # Smoke artifacts contain a compact trace summary, while older artifacts
    # may only retain the per-call usage list at the root.
    cost = _usage_cost(artifact.get("trace"))
    return cost if cost is not None else _usage_cost(artifact.get("usage"))


def _usage_cost(payload: Any) -> float | None:
    """Extract a reported total, preserving a real zero as valid evidence."""

    if isinstance(payload, Mapping):
        usage = payload.get("usage")
        if isinstance(usage, Mapping):
            summary = usage.get("summary")
            cost = _usage_cost(summary)
            if cost is not None:
                return cost
            records = usage.get("records")
            cost = _sum_record_costs(records)
            if cost is not None:
                return cost
            direct = _first_cost(usage)
            if direct is not None:
                return direct
        totals = payload.get("totals") or payload.get("total")
        cost = _first_cost(totals)
        if cost is not None:
            return cost
        summary = payload.get("summary")
        if isinstance(summary, Mapping):
            totals = summary.get("totals") or summary.get("total")
            cost = _first_cost(totals)
            if cost is not None:
                return cost
        records = payload.get("records")
        cost = _sum_record_costs(records)
        if cost is not None:
            return cost
        direct = _first_cost(payload)
        if direct is not None:
            return direct
        return None
    if isinstance(payload, (list, tuple)):
        return _sum_record_costs(payload)
    return None


def _sum_record_costs(records: Any) -> float | None:
    if not isinstance(records, (list, tuple)):
        return None
    values: list[float] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        nested = record.get("usage")
        cost = _first_cost(nested if isinstance(nested, Mapping) else record)
        if cost is not None:
            values.append(cost)
    return sum(values) if values else None


def _first_cost(values: Any) -> float | None:
    if not isinstance(values, Mapping):
        return None
    for key in ("cost", "actual_cost"):
        if key in values and values[key] is not None:
            return float(values[key])
    return None


def _publishable(draft: Mapping[str, Any]) -> bool:
    """Read the run gate from the real draft diagnostics envelope."""

    diagnostics = draft.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        run = diagnostics.get("run")
        if isinstance(run, Mapping):
            if "publishable" in run:
                return bool(run["publishable"])
            if str(run.get("status", "")).casefold() == "incomplete":
                return False
            # A run record without an explicit gate is not publishable evidence.
            return False
        # Compiler diagnostics alone do not establish a publication gate.
        return False
    # Keep compatibility with the original developer-only smoke shape.
    if isinstance(diagnostics, (list, tuple, set)):
        return not any(str(item).startswith("context_research_incomplete") for item in diagnostics)
    return False


def _resolve_trace_path(artifact_path: Path, configured: Any) -> Path | None:
    if not configured:
        return None
    candidate = Path(str(configured))
    return candidate if candidate.is_absolute() else artifact_path.parent / candidate


def _corpus_read_metric(artifact: Mapping[str, Any], trace_path: Path | None) -> dict[str, Any]:
    """Read observed metric data, or safely mark legacy artifacts denominator-only."""

    if trace_path and trace_path.is_file():
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        metric = trace.get("corpus_read")
        if isinstance(metric, Mapping):
            return _compact_corpus_read_metric(metric)
    metric = artifact.get("corpus_read_amplification")
    if isinstance(metric, Mapping):
        return _compact_corpus_read_metric(metric)
    denominator = _legacy_denominator(artifact.get("source_items"))
    return {
        "schema_version": "corpus-read-amplification-v1",
        "metric_name": "Corpus Read Amplification",
        "numerator_tokens": None,
        "denominator_tokens": denominator,
        "value": None,
        "complete": False,
        "unique_coverage_tokens": None,
        "unique_coverage": None,
        "reread_tokens": None,
        "p50_tokens_per_call": None,
        "p95_tokens_per_call": None,
        "max_tokens_per_call": None,
        "observation_count": 0,
        "backfill_status": "denominator_only" if denominator is not None else "unavailable",
        "tokenizer": {
            "library": "tiktoken", "encoding": "o200k_base", "version": "0.13.0",
        },
    }


def _compact_corpus_read_metric(metric: Mapping[str, Any]) -> dict[str, Any]:
    """Keep experiment rows aggregate-only; event observations stay in trace."""

    return {
        str(key): value for key, value in metric.items() if key != "observations"
    }


def _legacy_denominator(source_items: Any) -> int | None:
    if not isinstance(source_items, (list, tuple)):
        return None
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("o200k_base")
        return sum(
            len(encoder.encode(str(item.get("text", ""))))
            for item in source_items if isinstance(item, Mapping)
        )
    except Exception:
        return None


def score_artifact(
    artifact_path: Path,
    gold_path: Path,
    *,
    trace_path: Path | None = None,
    label: str | None = None,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    draft = artifact.get("draft") or {}
    axis_gold = load_three_axis_gold(gold_path)
    gold = axis_gold.units
    expected_primary = {
        unit_id: row.chain_id for unit_id, row in gold.items()
        if row.delivery_route == "event"
    }
    expected_reference = {
        unit_id for unit_id, row in gold.items() if row.delivery_route == "reference"
    }
    predicted_primary, predicted_reference = _draft_routes(draft)
    primary = _binary_score(set(predicted_primary), set(expected_primary))
    reference = _binary_score(predicted_reference, expected_reference)
    relaxed_chain_accuracy, pairwise, bcubed, attribution = _chain_metrics(
        predicted_primary, expected_primary,
    )
    predicted_routes = set(predicted_primary) | predicted_reference
    route_conflicts = set(predicted_primary) & predicted_reference
    # A local unit has one gold route.  A malformed draft that emits both
    # routes is ambiguous and must not earn a route-accuracy point through
    # either side of the union.
    predicted_roles, predicted_delivery = predicted_unit_axes(draft)
    expected_roles = {key: item.content_role for key, item in gold.items()}
    expected_delivery = {key: item.delivery_route for key, item in gold.items()}
    role_score = categorical_score(predicted_roles, expected_roles, CONTENT_ROLES)
    delivery_score = categorical_score(
        predicted_delivery, expected_delivery, DELIVERY_ROUTES,
    )
    predicted_entity_names, predicted_entity_pairs = predicted_entities(
        draft, axis_gold.entity_names,
    )
    entity_names = _optional_binary_score(predicted_entity_names, axis_gold.entity_names)
    entity_mentions = _optional_binary_score(
        predicted_entity_pairs, axis_gold.entity_unit_pairs,
    )
    trace_candidate = trace_path
    if trace_candidate is None:
        trace_metadata = artifact.get("trace")
        configured = trace_metadata.get("trace_output") if isinstance(trace_metadata, Mapping) else None
        trace_candidate = _resolve_trace_path(artifact_path, configured)
    execution = artifact.get("execution") or {}
    elapsed_seconds = execution.get("elapsed_seconds") if isinstance(execution, Mapping) else None
    if elapsed_seconds is None:
        elapsed_seconds = artifact.get("elapsed_seconds")
    corpus_read = _corpus_read_metric(artifact, trace_candidate)
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "label": label or artifact_path.stem,
        "artifact": str(artifact_path.resolve()),
        "trace": str(trace_candidate.resolve()) if trace_candidate else None,
        "gold": str(gold_path.resolve()),
        "configuration": configuration or {},
        "corpus": {
            "gold_units": len(gold),
            "gold_primary": len(expected_primary),
            "gold_reference": len(expected_reference),
            "predicted_primary": len(predicted_primary),
            "predicted_reference": len(predicted_reference),
            "routed_units": len(predicted_routes),
            "coverage": len(predicted_routes) / len(gold) if gold else 0.0,
            "classified_units": len(predicted_roles),
            "classification_coverage": len(predicted_roles) / len(gold) if gold else 0.0,
            "native_three_axis_gold": axis_gold.native_three_axis,
        },
        "metrics": {
            "primary": asdict(primary),
            "reference": asdict(reference),
            "macro_route_f1": (primary.f1 + reference.f1) / 2,
            "route_accuracy": delivery_score["accuracy"],
            "route_conflict_count": len(route_conflicts),
            "content_role": role_score,
            "delivery_route": delivery_score,
            "entity_names": entity_names,
            "entity_unit_mentions": entity_mentions,
            "relaxed_chain_accuracy": relaxed_chain_accuracy,
            "strict_clustering_pairwise": asdict(pairwise),
            "strict_clustering_bcubed": bcubed,
            "chain_attribution": attribution,
            "corpus_read_amplification": corpus_read,
        },
        "corpus_read_amplification": corpus_read,
        "cost_usd": _read_trace_cost(artifact, trace_candidate),
        "elapsed_seconds": elapsed_seconds,
        "publishable": _publishable(draft),
    }


def _optional_binary_score(predicted: set[Any], expected: frozenset[Any]) -> dict[str, Any]:
    if not expected:
        return {"available": False, "predicted_count": len(predicted)}
    return {"available": True, **asdict(_binary_score(predicted, set(expected)))}


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--configuration", help="JSON object describing this run")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ledger", type=Path)
    arguments = parser.parse_args()
    configuration = json.loads(arguments.configuration) if arguments.configuration else {}
    if not isinstance(configuration, dict):
        raise ValueError("--configuration must decode to a JSON object")
    record = score_artifact(
        arguments.artifact,
        arguments.gold,
        trace_path=arguments.trace,
        label=arguments.label,
        configuration=configuration,
    )
    rendered = json.dumps(record, ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    if arguments.ledger:
        _append_jsonl(arguments.ledger, record)
    print(rendered)


if __name__ == "__main__":
    main()
