"""Score an immutable Context Release against a human-edited Markdown gold set.

This developer tool is deliberately read-only.  It reuses Remis repositories and
the canonical local-unit builder, reconstructs the release's unit assignments,
and emits an auditable JSON snapshot for review/report generation.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
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


def parse_gold(
    path: Path,
    relation_overrides: dict[str, str],
    note_overrides: dict[str, str] | None = None,
) -> dict[str, GoldAssignment]:
    text = path.read_text(encoding="utf-8-sig")
    note_overrides = note_overrides or {}
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
            relation=relation_overrides.get(unit_id, data["relation"].strip()),
            note=note_overrides.get(unit_id, _clean_markdown(data["note"])),
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
    repository: ContextRepository,
    release: Any,
    manifest: Any | None = None,
) -> list[BenchmarkSourceItem]:
    manifest = manifest if manifest is not None else repository.get_release_manifest(release.release_id)
    if manifest is not None:
        source_items = [
            BenchmarkSourceItem(
                source_item_id=item.source_item_id,
                relative_path=item.relative_path,
                item_key=item.item_key or "",
                source_order=item.source_order if item.source_order is not None else 0,
                content=item.content,
            )
            for item in manifest.source_items
        ]
        source_items.sort(
            key=lambda item: (
                item.relative_path.casefold(),
                item.source_order,
                item.item_key.casefold(),
            )
        )
        return source_items

    audit_items = release.metadata.analysis_config.get("source_items", [])
    if not isinstance(audit_items, list) or not audit_items:
        raise ValueError(
            "Context Release has no persisted source manifest; run the release manifest migration"
        )
    project_items = repository.list_source_items(release.project_id)
    source_items = [
        BenchmarkSourceItem(
            source_item_id=source.source_item_id,
            relative_path=str(audit.get("relative_path") or ""),
            item_key=str(audit.get("item_key") or ""),
            source_order=int(audit.get("source_order") or 0),
            content=source.content,
        )
        for audit in audit_items
        for source in project_items
        if (
            source.source_item_id == audit.get("source_item_id")
            and (
                not audit.get("source_sha256")
                or source.content_hash == audit.get("source_sha256")
            )
        )
        or (
            source.metadata.get("relative_path") == audit.get("relative_path")
            and source.metadata.get("item_key") == audit.get("item_key")
            and source.metadata.get("source_order") == audit.get("source_order")
            and source.content_hash == audit.get("source_sha256")
        )
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


def _release_local_units(
    source_items: list[BenchmarkSourceItem], manifest: Any | None,
) -> tuple[LocalTextUnit, ...]:
    if manifest is None:
        return ContextLocalUnitBuilder.build(source_items)
    by_source_id = {item.source_item_id: item for item in source_items}
    return tuple(
        LocalTextUnit(
            unit_id=unit.local_unit_id,
            unit_key=unit.unit_key,
            items=tuple(by_source_id[source_id] for source_id in unit.source_item_ids),
        )
        for unit in sorted(manifest.local_units, key=lambda item: item.unit_order)
    )


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


def _score_snapshot(
    *,
    target: dict[str, Any],
    units: tuple[LocalTextUnit, ...],
    gold: dict[str, GoldAssignment],
    predicted: dict[str, tuple[PredictedLink, ...]],
    gold_path: Path,
    relation_overrides: dict[str, str],
    note_overrides: dict[str, str],
) -> dict[str, Any]:
    if len(units) != len(gold):
        raise ValueError(f"Local unit count mismatch: target={len(units)}, gold={len(gold)}")
    unit_ids = {unit.unit_id for unit in units}
    if unit_ids != set(gold):
        missing = sorted(set(gold) - unit_ids, key=_unit_number)
        unexpected = sorted(unit_ids - set(gold), key=_unit_number)
        raise ValueError(
            f"Local unit identity mismatch: missing={missing}, unexpected={unexpected}"
        )
    mapping = _best_chain_mapping(gold, predicted)
    results = [
        _unit_result(unit, gold[unit.unit_id], predicted.get(unit.unit_id, ()), mapping)
        for unit in units
    ]
    snapshot = {
        "target": target,
        "gold": {
            "path": str(gold_path.resolve()),
            "relation_overrides": relation_overrides,
            "note_overrides": note_overrides,
        },
        "predicted_to_gold_chain_mapping": mapping,
        "metrics": _metrics(results),
        "units": [asdict(result) for result in results],
    }
    if target["kind"] == "release":
        snapshot["release"] = {
            "release_id": target["id"],
            "project_id": target["project_id"],
            "source_snapshot_hash": target["source_snapshot_hash"],
            "provider_id": target["provider_id"],
            "model_id": target["model_id"],
            "prompt_version": target["prompt_version"],
            "schema_version": target["schema_version"],
            "created_at": target["created_at"],
        }
    return snapshot


def build_snapshot(
    release_id: str,
    gold_path: Path,
    relation_overrides: dict[str, str],
    note_overrides: dict[str, str] | None = None,
    *,
    database_path: str | Path = PROJECTS_DB_PATH,
) -> dict[str, Any]:
    repository = ContextRepository(str(database_path))
    release = repository.get_release(release_id)
    if release is None:
        raise ValueError(f"Unknown Context Release: {release_id}")
    manifest = repository.get_release_manifest(release_id)
    source_items = _release_source_items(repository, release, manifest)
    units = _release_local_units(source_items, manifest)
    note_overrides = note_overrides or {}
    gold = parse_gold(gold_path, relation_overrides, note_overrides)
    predicted = _membership_links(
        repository.list_release_delivery_memberships(release_id), units
    )
    return _score_snapshot(
        target={
            "kind": "release",
            "id": release.release_id,
            "project_id": release.project_id,
            "source_snapshot_hash": release.metadata.source_snapshot_hash,
            "provider_id": release.metadata.provider_id,
            "model_id": release.metadata.model_id,
            "prompt_version": release.metadata.prompt_version,
            "schema_version": release.metadata.schema_version,
            "created_at": release.metadata.created_at,
            "status": "published",
            "source_item_count": len(source_items),
            "local_unit_count": len(units),
        },
        units=units,
        gold=gold,
        predicted=predicted,
        gold_path=gold_path,
        relation_overrides=relation_overrides,
        note_overrides=note_overrides,
    )


def build_analysis_run_snapshot(
    run_id: str,
    gold_path: Path,
    relation_overrides: dict[str, str],
    note_overrides: dict[str, str] | None = None,
    *,
    database_path: str | Path = PROJECTS_DB_PATH,
) -> dict[str, Any]:
    """Score persisted final assignments even when publication did not finish."""

    database = Path(database_path).resolve()
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        run = connection.execute(
            """
            SELECT run_id, project_id, source_snapshot_hash, config_json,
                   status, publication_status, created_at, updated_at
            FROM context_analysis_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if run is None:
            raise ValueError(f"Unknown Context Analysis Run: {run_id}")
        assignments = _analysis_run_assignments(connection, run_id)
        units, predicted, source_item_count = _analysis_units_and_predictions(
            connection,
            str(run["project_id"]),
            str(run["source_snapshot_hash"]),
            assignments,
        )
    finally:
        connection.close()

    note_overrides = note_overrides or {}
    gold = parse_gold(gold_path, relation_overrides, note_overrides)
    config = json.loads(run["config_json"] or "{}")
    return _score_snapshot(
        target={
            "kind": "analysis_run",
            "id": str(run["run_id"]),
            "project_id": str(run["project_id"]),
            "source_snapshot_hash": str(run["source_snapshot_hash"]),
            "provider_id": str(config.get("provider") or ""),
            "model_id": str(config.get("model") or ""),
            "prompt_version": str(config.get("prompt_version") or ""),
            "schema_version": str(config.get("schema_version") or ""),
            "created_at": str(run["created_at"]),
            "updated_at": str(run["updated_at"]),
            "status": str(run["status"]),
            "publication_status": str(run["publication_status"]),
            "source_item_count": source_item_count,
            "local_unit_count": len(units),
        },
        units=units,
        gold=gold,
        predicted=predicted,
        gold_path=gold_path,
        relation_overrides=relation_overrides,
        note_overrides=note_overrides,
    )


def _analysis_run_assignments(
    connection: sqlite3.Connection, run_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT batch_index, payload_json
        FROM context_analysis_batches
        WHERE run_id = ? AND phase = 'aggregation' AND status = 'succeeded'
        ORDER BY batch_index
        """,
        (run_id,),
    ).fetchall()
    assignments: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = json.loads(row["payload_json"] or "{}")
        for assignment in payload.get("assignment_batch", {}).get("assignments", []):
            unit_id = str(assignment.get("local_unit_id") or "")
            if not unit_id:
                raise ValueError("Aggregation assignment is missing local_unit_id")
            if unit_id in assignments:
                raise ValueError(f"Duplicate final assignment: {unit_id}")
            assignments[unit_id] = assignment
    if not assignments:
        raise ValueError(
            f"Context Analysis Run has no persisted final assignments: {run_id}"
        )
    return sorted(
        assignments.values(),
        key=lambda item: _unit_number(str(item["local_unit_id"])),
    )


def _analysis_units_and_predictions(
    connection: sqlite3.Connection,
    project_id: str,
    source_snapshot_hash: str,
    assignments: list[dict[str, Any]],
) -> tuple[
    tuple[LocalTextUnit, ...], dict[str, tuple[PredictedLink, ...]], int
]:
    source_ids = {
        str(source_id)
        for assignment in assignments
        for source_id in assignment.get("source_item_ids", [])
    }
    rows = connection.execute(
        """
        SELECT source_item_id, source_ref, content, metadata_json
        FROM context_source_items
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    source_items: dict[str, BenchmarkSourceItem] = {}
    for row in rows:
        source_id = str(row["source_item_id"])
        if source_id not in source_ids:
            continue
        metadata = json.loads(row["metadata_json"] or "{}")
        item_snapshot = str(metadata.get("source_snapshot_hash") or "")
        if item_snapshot and item_snapshot != source_snapshot_hash:
            raise ValueError(
                f"Analysis source snapshot mismatch for {source_id}: "
                f"run={source_snapshot_hash}, item={item_snapshot}"
            )
        source_items[source_id] = BenchmarkSourceItem(
            source_item_id=source_id,
            relative_path=str(metadata.get("relative_path") or ""),
            item_key=str(metadata.get("item_key") or ""),
            source_order=int(metadata.get("source_order") or 0),
            content=str(row["content"]),
        )
    missing_sources = sorted(source_ids - set(source_items))
    if missing_sources:
        raise ValueError(
            f"Analysis assignments reference missing source items: {missing_sources}"
        )

    units: list[LocalTextUnit] = []
    predicted: dict[str, tuple[PredictedLink, ...]] = {}
    for assignment in assignments:
        unit_id = str(assignment["local_unit_id"])
        unit_source_ids = tuple(str(value) for value in assignment.get("source_item_ids", []))
        if not unit_source_ids:
            raise ValueError(f"Analysis assignment has no source items: {unit_id}")
        units.append(
            LocalTextUnit(
                unit_id=unit_id,
                unit_key=unit_id,
                items=tuple(source_items[source_id] for source_id in unit_source_ids),
            )
        )
        predicted[unit_id] = tuple(
            PredictedLink(
                chain_id=str(link["event_chain_id"]),
                relation=str(link["relation"]),
                confidence=float(link["confidence"]),
                source_item_count=len(unit_source_ids),
            )
            for link in assignment.get("links", [])
        )
    return tuple(units), predicted, len(source_items)


def render_markdown(snapshot: dict[str, Any]) -> str:
    metrics = snapshot["metrics"]
    strict = metrics["strict_clustering_pairwise"]
    target = snapshot.get("target")
    if target is None:
        release = snapshot["release"]
        target = {
            "kind": "release",
            "id": release["release_id"],
            "source_snapshot_hash": release["source_snapshot_hash"],
            "model_id": release["model_id"],
            "prompt_version": release["prompt_version"],
            "status": "published",
        }
    target_label = (
        "Context Release" if target["kind"] == "release" else "Context Analysis Run"
    )
    lines = [
        "# Context Archive 金标审核报告",
        "",
        f"- {target_label}: `{target['id']}`",
        f"- Target status: `{target.get('status', '')}`",
        f"- Source snapshot: `{target['source_snapshot_hash']}`",
        f"- Model: `{target['model_id']}`",
        f"- Prompt: `{target['prompt_version']}`",
        "",
        "## 总体指标",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| Unit | {metrics['unit_count']} |",
        f"| 投递精确率 | {metrics['delivery_precision']:.2%} |",
        f"| 投递召回率 | {metrics['delivery_recall']:.2%} |",
        f"| 投递 F1 | {metrics['delivery_f1']:.2%} |",
        f"| 宽松事件链正确率 | {metrics['relaxed_chain_accuracy']:.2%} |",
        f"| 严格聚类 Pairwise F1 | {strict['f1']:.2%} |",
        f"| 关系类型完全正确率 | {metrics['exact_relation_accuracy']:.2%} |",
        "",
        "## Remis 事件链映射",
        "",
        "| Remis chain | 默认接受的 Gold chain |",
        "|---|---|",
    ]
    for predicted, gold in sorted(snapshot["predicted_to_gold_chain_mapping"].items()):
        lines.append(f"| `{predicted}` | `{gold}` |")
    lines.extend(["", "## 逐单元审核", ""])
    for unit in snapshot["units"]:
        links = unit["predicted_links"]
        predicted = "; ".join(
            f"{link['chain_id']} / {link['relation']} / {link['confidence']:.2f}"
            for link in links
        ) or "unassigned"
        lines.extend(
            [
                f"### `{unit['unit_id']}` · `{', '.join(unit['item_keys'])}`",
                "",
                f"- Gold: `{unit['gold_chain']}` / `{unit['gold_relation']}` / "
                f"`{unit['gold_confidence']}`",
                f"- Remis: `{predicted}`",
                f"- Verdict: `{unit['delivery_verdict']}` / "
                f"`{unit['relaxed_chain_verdict']}` / `{unit['relation_verdict']}`",
                f"- Gold note: {unit['gold_note'] or '—'}",
                "- Human verdict: `未审核`",
                "- Human notes:",
                "",
                "<details><summary>展开英文原文</summary>",
                "",
                "```text",
                unit["source_text"].replace("```", "` ` `"),
                "```",
                "",
                "</details>",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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


def _parse_note_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        unit_id, separator, note = value.partition("=")
        if not separator or not re.fullmatch(r"unit_\d+", unit_id) or not note.strip():
            raise ValueError(f"Invalid note override: {value}")
        overrides[unit_id] = note.strip()
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--release-id")
    target.add_argument("--analysis-run-id")
    parser.add_argument("--database", type=Path, default=Path(PROJECTS_DB_PATH))
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--relation-override",
        action="append",
        default=[],
        metavar="UNIT=RELATION",
    )
    parser.add_argument(
        "--note-override",
        action="append",
        default=[],
        metavar="UNIT=NOTE",
    )
    args = parser.parse_args()
    relation_overrides = _parse_overrides(args.relation_override)
    note_overrides = _parse_note_overrides(args.note_override)
    if args.release_id:
        snapshot = build_snapshot(
            args.release_id,
            args.gold,
            relation_overrides,
            note_overrides,
            database_path=args.database,
        )
    else:
        snapshot = build_analysis_run_snapshot(
            args.analysis_run_id,
            args.gold,
            relation_overrides,
            note_overrides,
            database_path=args.database,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            render_markdown(snapshot), encoding="utf-8"
        )
    print(json.dumps(snapshot["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
