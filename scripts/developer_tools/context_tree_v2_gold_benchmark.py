"""Score a published context-tree-v2 archive against a legacy unit gold manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from scripts.core.repositories.context_tree_v2_repository import (
    ContextTreeV2Repository,
)


DELIVERY_RELATIONS = frozenset({"primary_member", "supporting_context"})


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _load_json(path: str | None, url: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not url:
        raise ValueError("tree JSON path or URL is required")
    with urlopen(url, timeout=15) as response:  # noqa: S310 - localhost tooling
        return json.loads(response.read().decode("utf-8-sig"))


def _load_tree(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.database:
        tree = ContextTreeV2Repository(arguments.database).get_latest_release_tree(
            arguments.project_id,
        )
        return tree.model_dump(mode="json")
    return _load_json(arguments.tree_json, arguments.tree_url)


def _unit_groups(tree: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    fragment_group = {
        fragment_id: group["group_id"]
        for group in tree.get("groups", [])
        for fragment_id in group.get("fragment_ids", [])
    }
    units: dict[str, dict[str, Any]] = {}
    for route in tree.get("unit_routes", []):
        groups = tuple(dict.fromkeys(
            fragment_group[fragment_id]
            for fragment_id in route.get("fragment_ids", [])
            if fragment_id in fragment_group
        ))
        units[route["local_unit_id"]] = {
            "route": route.get("route", "no_context"),
            "group_ids": groups,
            "delivered": route.get("route") == "narrative" and bool(groups),
        }
    return units, fragment_group


def _best_group_mapping(
    gold: dict[str, dict[str, Any]],
    predicted: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], dict[str, Counter[str]]]:
    overlap: dict[str, Counter[str]] = defaultdict(Counter)
    for unit_id, prediction in predicted.items():
        gold_row = gold[unit_id]
        if gold_row["relation"] not in DELIVERY_RELATIONS:
            continue
        for group_id in prediction["group_ids"]:
            overlap[group_id][gold_row["chain"]] += 1
    mapping = {
        group_id: counts.most_common(1)[0][0]
        for group_id, counts in overlap.items()
        if counts
    }
    return mapping, overlap


def _pairwise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    true_positive = false_positive = false_negative = 0
    labels = [
        (row["gold_chain"], ";".join(row["predicted_group_ids"]) or f"missing:{row['unit_id']}")
        for row in rows
        if row["gold_relation"] in DELIVERY_RELATIONS
    ]
    for left, right in combinations(labels, 2):
        same_gold = left[0] == right[0]
        same_prediction = left[1] == right[1]
        if same_gold and same_prediction:
            true_positive += 1
        elif same_prediction:
            false_positive += 1
        elif same_gold:
            false_negative += 1
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "true_positive_pairs": true_positive,
        "false_positive_pairs": false_positive,
        "false_negative_pairs": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def score(tree: dict[str, Any], gold_document: dict[str, Any]) -> dict[str, Any]:
    gold = {row["unit_id"]: row for row in gold_document["assignments"]}
    predicted, _ = _unit_groups(tree)
    if set(predicted) != set(gold):
        raise ValueError(
            "unit mismatch: "
            f"missing={sorted(set(gold) - set(predicted))}, "
            f"unexpected={sorted(set(predicted) - set(gold))}"
        )
    mapping, overlap = _best_group_mapping(gold, predicted)
    rows = []
    for unit_id in sorted(gold, key=lambda value: int(value.rsplit("_", 1)[1])):
        gold_row = gold[unit_id]
        prediction = predicted[unit_id]
        gold_delivery = gold_row["relation"] in DELIVERY_RELATIONS
        delivered = prediction["delivered"]
        mapped_chains = {mapping.get(group_id) for group_id in prediction["group_ids"]}
        rows.append({
            "unit_id": unit_id,
            "group_key": gold_row["group_key"],
            "gold_chain": gold_row["chain"],
            "gold_relation": gold_row["relation"],
            "predicted_route": prediction["route"],
            "predicted_group_ids": prediction["group_ids"],
            "delivery_verdict": (
                "correct_delivery" if gold_delivery and delivered
                else "missed_delivery" if gold_delivery
                else "unexpected_delivery" if delivered
                else "correct_no_delivery"
            ),
            "chain_verdict": (
                "not_applicable" if not gold_delivery
                else "missing" if not delivered
                else "correct" if gold_row["chain"] in mapped_chains
                else "wrong_chain"
            ),
        })
    delivery = Counter(row["delivery_verdict"] for row in rows)
    chain = Counter(row["chain_verdict"] for row in rows)
    tp, fp, fn = (
        delivery["correct_delivery"],
        delivery["unexpected_delivery"],
        delivery["missed_delivery"],
    )
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    primary_rows = [row for row in rows if row["gold_relation"] == "primary_member"]
    primary_chain = Counter(row["chain_verdict"] for row in primary_rows)
    by_relation = {
        relation: {
            "count": len(selected),
            "delivered": sum(row["delivery_verdict"] == "correct_delivery" for row in selected),
            "delivery_recall": _ratio(
                sum(row["delivery_verdict"] == "correct_delivery" for row in selected),
                len(selected),
            ) if relation in DELIVERY_RELATIONS else None,
            "predicted_routes": dict(Counter(row["predicted_route"] for row in selected)),
        }
        for relation in sorted({row["gold_relation"] for row in rows})
        for selected in [[row for row in rows if row["gold_relation"] == relation]]
    }
    group_units: dict[str, list[str]] = defaultdict(list)
    for unit_id, prediction in predicted.items():
        for group_id in prediction["group_ids"]:
            group_units[group_id].append(unit_id)
    group_composition = {}
    for group_id, unit_ids in sorted(group_units.items()):
        gold_rows = [gold[unit_id] for unit_id in unit_ids]
        group_composition[group_id] = {
            "unit_count": len(unit_ids),
            "mapped_gold_chain": mapping.get(group_id),
            "gold_chains": dict(Counter(row["chain"] for row in gold_rows)),
            "gold_relations": dict(Counter(row["relation"] for row in gold_rows)),
            "unit_ids": sorted(unit_ids, key=lambda value: int(value.rsplit("_", 1)[1])),
        }
    return {
        "benchmark_version": "legacy-gold-v1/tree-v2-projection-v1",
        "tree_id": tree.get("tree_id"),
        "release_id": tree.get("release_id"),
        "gold_fixture": gold_document.get("fixture"),
        "prediction": {
            "unit_count": len(predicted),
            "route_counts": dict(Counter(item["route"] for item in predicted.values())),
            "event_group_count": len(tree.get("groups", [])),
            "best_overlap_mapping": mapping,
            "group_composition": group_composition,
        },
        "metrics": {
            "delivery": dict(delivery),
            "delivery_precision": precision,
            "delivery_recall": recall,
            "delivery_f1": _f1(precision, recall),
            "relaxed_chain": dict(chain),
            "relaxed_chain_accuracy": _ratio(
                chain["correct"], chain["correct"] + chain["wrong_chain"] + chain["missing"],
            ),
            "strict_clustering_pairwise": _pairwise(rows),
            "primary_only": {
                "unit_count": len(primary_rows),
                "delivered": sum(
                    row["delivery_verdict"] == "correct_delivery"
                    for row in primary_rows
                ),
                "chain": dict(primary_chain),
                "chain_accuracy": _ratio(
                    primary_chain["correct"],
                    primary_chain["correct"] + primary_chain["wrong_chain"]
                    + primary_chain["missing"],
                ),
                "strict_clustering_pairwise": _pairwise(primary_rows),
            },
            "by_gold_relation": by_relation,
        },
        "errors": {
            "missed_delivery": [row for row in rows if row["delivery_verdict"] == "missed_delivery"],
            "unexpected_delivery": [row for row in rows if row["delivery_verdict"] == "unexpected_delivery"],
            "wrong_chain": [row for row in rows if row["chain_verdict"] == "wrong_chain"],
        },
        "units": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tree-json")
    source.add_argument("--tree-url")
    source.add_argument("--database")
    parser.add_argument("--project-id")
    parser.add_argument("--output")
    arguments = parser.parse_args()
    if arguments.database and not arguments.project_id:
        parser.error("--project-id is required with --database")
    result = score(
        _load_tree(arguments),
        _load_json(arguments.gold, None),
    )
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    print(json.dumps({
        "benchmark_version": result["benchmark_version"],
        "tree_id": result["tree_id"],
        "prediction": result["prediction"],
        "metrics": result["metrics"],
        "error_counts": {key: len(value) for key, value in result["errors"].items()},
        "output": arguments.output,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
