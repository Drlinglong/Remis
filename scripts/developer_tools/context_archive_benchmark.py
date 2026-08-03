"""Score an immutable Context Release against a human-edited Markdown gold set.

This developer tool is deliberately read-only.  It reuses Remis repositories and
the canonical local-unit builder, reconstructs the release's unit assignments,
and emits an auditable JSON snapshot for review/report generation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.repositories.context_repository import ContextRepository


DELIVERY_RELATIONS = {"primary_member", "supporting_context"}
GOLD_ROW = re.compile(
    r"^\|\s*`(?P<unit>unit_\d+)`\s*\|(?P<keys>.*?)\|\s*`(?P<chain>[^`]+)`\s*\|"
    r"\s*`(?P<relation>[^`]+)`\s*\|(?P<note>.*?)\|\s*`(?P<confidence>[^`]+)`\s*\|\s*$"
)


@dataclass(frozen=True)
class GoldAssignment:
    unit_id: str
    key_hint: str
    chain_id: str
    relation: str
    note: str
    confidence: str


@dataclass(frozen=True)
class PredictedLink:
    chain_id: str
    relation: str
    confidence: float
    source_item_count: int


@dataclass(frozen=True)
class BenchmarkSourceItem:
    source_item_id: str
    relative_path: str
    item_key: str
    source_order: int
    content: str


@dataclass(frozen=True)
class UnitResult:
    unit_id: str
    unit_key: str
    item_keys: tuple[str, ...]
    source_text: str
    gold_chain: str
    gold_relation: str
    gold_confidence: str
    gold_note: str
    predicted_links: tuple[PredictedLink, ...]
    predicted_state: str
    delivery_verdict: str
    relaxed_chain_verdict: str
    relation_verdict: str


def parse_gold(path: Path, overrides: dict[str, str]) -> dict[str, GoldAssignment]:
    text = path.read_text(encoding="utf-8-sig")
    rows: dict[str, GoldAssignment] = {}
    for raw_line in text.splitlines():
        match = GOLD_ROW.match(raw_line)
        if not match:
            continue
        data = match.groupdict()
        unit_id = data["unit"]
        if unit_id in rows:
            raise ValueError(f"Duplicate gold assignment: {unit_id}")
        rows[unit_id] = GoldAssignment(
            unit_id=unit_id,
            key_hint=_clean_markdown(data["keys"]),
            chain_id=data["chain"].strip(),
            relation=overrides.get(unit_id, data["relation"].strip()),
            note=_clean_markdown(data["note"]),
            confidence=data["confidence"].strip(),
        )
    expected = {f"unit_{index}" for index in range(len(rows))}
    if set(rows) != expected:
        missing = sorted(expected - set(rows), key=_unit_number)
        unexpected = sorted(set(rows) - expected, key=_unit_number)
        raise ValueError(f"Gold unit set mismatch: missing={missing}, unexpected={unexpected}")
    return rows


def _clean_markdown(value: str) -> str:
    return value.replace("`", "").replace("**", "").strip()


def _unit_number(unit_id: str) -> int:
    try:
        return int(unit_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 10**9


def _release_source_items(
    repository: ContextRepository, release: Any
) -> list[BenchmarkSourceItem]:
    snapshot = release.metadata.source_snapshot_hash
    source_items = [
        BenchmarkSourceItem(
            source_item_id=item.source_item_id,
            relative_path=str(item.metadata.get("relative_path") or ""),
            item_key=str(item.metadata.get("item_key") or ""),
            source_order=int(item.metadata.get("source_order") or 0),
            content=item.content,
        )
        for item in repository.list_source_items(release.project_id)
        if item.metadata.get("source_snapshot_hash") == snapshot
    ]
    source_items.sort(
        key=lambda item: (
            item.relative_path.casefold(),
            item.source_order,
            item.item_key.casefold(),
        )
    )
    expected = int(
        release.metadata.analysis_config.get("analysis_report", {})
        .get("input_and_chunking", {})
        .get("source_items", 0)
    )
    if expected and len(source_items) != expected:
        raise ValueError(
            "Release source snapshot mismatch: "
            f"expected={expected}, reconstructed={len(source_items)}"
        )
    return source_items


def _membership_links(
    memberships: Iterable[dict[str, Any]], units: Iterable[LocalTextUnit]
) -> dict[str, tuple[PredictedLink, ...]]:
    source_to_unit = {
        item.source_item_id: unit.unit_id for unit in units for item in unit.items
    }
    grouped: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for edge in memberships:
        source_id = edge["membership"]["source_item_id"]
        unit_id = source_to_unit.get(source_id)
        if unit_id is None:
            raise ValueError(f"Delivery membership references unknown source item: {source_id}")
        chain_id = str(edge["aggregate"]["aggregate_key"]).removeprefix("event:")
        role = str(edge["membership"]["role"])
        grouped[unit_id][(chain_id, role)].append(edge)
    return {
        unit_id: tuple(
            PredictedLink(
                chain_id=chain_id,
                relation=role,
                confidence=max(float(edge["membership"]["confidence"]) for edge in edges),
                source_item_count=len(edges),
            )
            for (chain_id, role), edges in sorted(links.items())
        )
        for unit_id, links in grouped.items()
    }


def _best_chain_mapping(
    gold: dict[str, GoldAssignment], predicted: dict[str, tuple[PredictedLink, ...]]
) -> dict[str, str]:
    overlap: dict[str, Counter[str]] = defaultdict(Counter)
    for unit_id, links in predicted.items():
        gold_row = gold[unit_id]
        if gold_row.relation not in DELIVERY_RELATIONS:
            continue
        for link in links:
            if link.relation in DELIVERY_RELATIONS:
                overlap[link.chain_id][gold_row.chain_id] += 1
    return {
        chain_id: counts.most_common(1)[0][0]
        for chain_id, counts in overlap.items()
        if counts
    }


def _unit_result(
    unit: LocalTextUnit,
    gold: GoldAssignment,
    links: tuple[PredictedLink, ...],
    chain_mapping: dict[str, str],
) -> UnitResult:
    gold_delivery = gold.relation in DELIVERY_RELATIONS
    delivery_links = tuple(link for link in links if link.relation in DELIVERY_RELATIONS)
    predicted_delivery = bool(delivery_links)
    if gold_delivery and predicted_delivery:
        delivery_verdict = "correct_delivery"
    elif gold_delivery:
        delivery_verdict = "missed_delivery"
    elif predicted_delivery:
        delivery_verdict = "unexpected_delivery"
    else:
        delivery_verdict = "correct_no_delivery"

    mapped_gold = {chain_mapping.get(link.chain_id) for link in delivery_links}
    if not gold_delivery:
        chain_verdict = "not_applicable"
    elif not predicted_delivery:
        chain_verdict = "missing"
    elif gold.chain_id in mapped_gold:
        chain_verdict = "correct"
    else:
        chain_verdict = "wrong_chain"

    predicted_relations = {link.relation for link in links}
    if gold.relation in predicted_relations:
        relation_verdict = "exact"
    elif gold_delivery and predicted_delivery:
        relation_verdict = "wrong_delivery_role"
    elif not gold_delivery and not predicted_delivery and predicted_relations:
        relation_verdict = "wrong_non_delivery_role"
    else:
        relation_verdict = "missing"

    return UnitResult(
        unit_id=unit.unit_id,
        unit_key=unit.unit_key.split("::", 1)[-1],
        item_keys=tuple(str(item.item_key) for item in unit.items),
        source_text="\n\n".join(
            f"{item.item_key}: {item.content}" for item in unit.items
        ),
        gold_chain=gold.chain_id,
        gold_relation=gold.relation,
        gold_confidence=gold.confidence,
        gold_note=gold.note,
        predicted_links=links,
        predicted_state="assigned" if links else "unassigned",
        delivery_verdict=delivery_verdict,
        relaxed_chain_verdict=chain_verdict,
        relation_verdict=relation_verdict,
    )


def _metrics(results: list[UnitResult]) -> dict[str, Any]:
    delivery = Counter(result.delivery_verdict for result in results)
    chain = Counter(result.relaxed_chain_verdict for result in results)
    relation = Counter(result.relation_verdict for result in results)
    true_positive = delivery["correct_delivery"]
    false_positive = delivery["unexpected_delivery"]
    false_negative = delivery["missed_delivery"]
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    f1 = _ratio(2 * precision * recall, precision + recall)
    correct_chain = chain["correct"]
    evaluated_chain = correct_chain + chain["wrong_chain"] + chain["missing"]
    return {
        "unit_count": len(results),
        "delivery": dict(delivery),
        "delivery_precision": precision,
        "delivery_recall": recall,
        "delivery_f1": f1,
        "relaxed_chain": dict(chain),
        "relaxed_chain_accuracy": _ratio(correct_chain, evaluated_chain),
        "strict_clustering_pairwise": _pairwise_clustering_metrics(results),
        "relation": dict(relation),
        "exact_relation_accuracy": _ratio(relation["exact"], len(results)),
    }


def _pairwise_clustering_metrics(results: list[UnitResult]) -> dict[str, Any]:
    relevant = [
        result for result in results if result.gold_relation in DELIVERY_RELATIONS
    ]
    labels = []
    for result in relevant:
        delivered = sorted(
            link.chain_id
            for link in result.predicted_links
            if link.relation in DELIVERY_RELATIONS
        )
        predicted_label = ";".join(delivered) if delivered else f"missing:{result.unit_id}"
        labels.append((result.gold_chain, predicted_label))
    true_positive = false_positive = false_negative = 0
    for left in range(len(labels)):
        for right in range(left + 1, len(labels)):
            same_gold = labels[left][0] == labels[right][0]
            same_predicted = labels[left][1] == labels[right][1]
            if same_gold and same_predicted:
                true_positive += 1
            elif same_predicted:
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
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_snapshot(
    release_id: str, gold_path: Path, overrides: dict[str, str]
) -> dict[str, Any]:
    repository = ContextRepository(PROJECTS_DB_PATH)
    release = repository.get_release(release_id)
    if release is None:
        raise ValueError(f"Unknown Context Release: {release_id}")
    source_items = _release_source_items(repository, release)
    units = ContextLocalUnitBuilder.build(source_items)
    gold = parse_gold(gold_path, overrides)
    if len(units) != len(gold):
        raise ValueError(f"Local unit count mismatch: release={len(units)}, gold={len(gold)}")
    predicted = _membership_links(
        repository.list_release_delivery_memberships(release_id), units
    )
    mapping = _best_chain_mapping(gold, predicted)
    results = [
        _unit_result(unit, gold[unit.unit_id], predicted.get(unit.unit_id, ()), mapping)
        for unit in units
    ]
    return {
        "release": {
            "release_id": release.release_id,
            "project_id": release.project_id,
            "source_snapshot_hash": release.metadata.source_snapshot_hash,
            "provider_id": release.metadata.provider_id,
            "model_id": release.metadata.model_id,
            "prompt_version": release.metadata.prompt_version,
            "schema_version": release.metadata.schema_version,
            "created_at": release.metadata.created_at,
        },
        "gold": {
            "path": str(gold_path.resolve()),
            "relation_overrides": overrides,
        },
        "predicted_to_gold_chain_mapping": mapping,
        "metrics": _metrics(results),
        "units": [asdict(result) for result in results],
    }


def _parse_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        unit_id, separator, relation = value.partition("=")
        if not separator or relation not in {
            "primary_member",
            "supporting_context",
            "theme_related",
            "parent_story_metadata",
        }:
            raise ValueError(f"Invalid relation override: {value}")
        overrides[unit_id] = relation
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--relation-override",
        action="append",
        default=[],
        metavar="UNIT=RELATION",
    )
    args = parser.parse_args()
    snapshot = build_snapshot(
        args.release_id,
        args.gold,
        _parse_overrides(args.relation_override),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(snapshot["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
