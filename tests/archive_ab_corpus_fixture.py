"""Hermetic corpus fixture for archive A/B tests."""

from __future__ import annotations

import json
from pathlib import Path


def materialize_archive_ab_corpus(
    tmp_path: Path, *, rows_per_case: int = 24,
) -> tuple[Path, Path]:
    """Build the small corpus shape required by the checked-in A/B manifest."""

    manifest_path = Path(__file__).parent / "fixtures/remis_archive_ab_v1/cases.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_root = tmp_path / "archive-ab-corpus"
    source_lines: dict[str, list[str]] = {}
    gold_rows: dict[str, list[dict[str, object]]] = {}

    for definition in document["cases"]:
        case_id = str(definition["case_id"])
        case_kind = str(definition["case_kind"])
        selection = definition["selection"]
        source_path = str(definition["source_path"])
        gold_path = str(definition["gold_path"])
        chain_id = str(selection.get("chain_id") or "")
        group_prefix = str(selection.get("group_prefix") or "")
        source_lines.setdefault(source_path, [])
        gold_rows.setdefault(gold_path, [])
        for index in range(rows_per_case):
            source_id = f"fixture_{case_id}_{index}:0"
            source_lines[source_path].append(f'{source_id} "Fixture entry {index}"')
            gold_rows[gold_path].append({
                "unit_id": f"unit-{case_id}-{index}",
                "content_role": (
                    "static_reference" if case_kind == "reference_batch" else "event_chain"
                ),
                "group_key": f"{group_prefix}{index}" if group_prefix else f"{case_id}-group",
                "chain_memberships": [chain_id] if chain_id else [],
                "item_keys": [source_id],
            })

    for relative_path, lines in source_lines.items():
        path = corpus_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("l_english:\n" + "\n".join(lines) + "\n", encoding="utf-8")
    for relative_path, assignments in gold_rows.items():
        path = corpus_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"assignments": assignments}, ensure_ascii=False),
            encoding="utf-8",
        )
    return manifest_path, corpus_root
