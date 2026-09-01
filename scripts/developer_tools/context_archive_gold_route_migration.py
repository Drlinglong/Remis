"""Create route-aware Context Archive gold versions without changing frozen gold.

The migration keeps canonical local units intact. Event-localization units remain
``primary_member`` narrative; names, assets, rules text, projects, modifiers,
technology, and other non-event units become ``reference_asset`` supporting text.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


SOURCE_VERSION = "2026-08-04"
SUPPORTING_CHAIN = "supporting_text"
UNIT_HEADING = re.compile(r"^###\s+`(?P<unit>unit_\d+)`")
DETAIL_GOLD = re.compile(
    r"^- Gold: `(?P<chain>[^`]+)` / `(?P<relation>[^`]+)` / `(?P<confidence>[^`]+)`$"
)
RELATION_BULLET = re.compile(r"^- \*\*relation：\*\* `(?P<relation>[^`]+)`$")
GENERATED_AT = re.compile(r'^generated_at: "[^"]+"$')


def _unit_range(start: int, end: int, *, exclude: set[int] | None = None) -> set[str]:
    excluded = exclude or set()
    return {f"unit_{index}" for index in range(start, end + 1) if index not in excluded}


NARRATIVE_UNITS = {
    "horizon-signal": _unit_range(36, 94, exclude={38}),
    "toxic-god": {
        "unit_103", "unit_104", "unit_105", "unit_106", "unit_107", "unit_108",
        "unit_109", "unit_110", "unit_111", "unit_112", "unit_113", "unit_114",
        "unit_115", "unit_116", "unit_117", "unit_118", "unit_119", "unit_120",
        "unit_121", "unit_122", "unit_123", "unit_124", "unit_125", "unit_126",
        "unit_127", "unit_128", "unit_129", "unit_130", "unit_131", "unit_132",
        "unit_133", "unit_134", "unit_135", "unit_136", "unit_137", "unit_138",
        "unit_139", "unit_140", "unit_141", "unit_143", "unit_144", "unit_145",
        "unit_146", "unit_147", "unit_148", "unit_149", "unit_150", "unit_152",
        "unit_153", "unit_154", "unit_155", "unit_156", "unit_157", "unit_158",
        "unit_159", "unit_160", "unit_162", "unit_163", "unit_164", "unit_165",
        "unit_166", "unit_167", "unit_168", "unit_169", "unit_171", "unit_172",
        "unit_173", "unit_174", "unit_176",
    },
}

FIXTURES = {
    "horizon-signal": {
        "path": "projects/stellaris/horizonsignal_demo/horizonsignal_l_english.yml",
        "sha256": "aa3333a36f36492c8c4bdd62d9cde604babda9316f618dbfceace9a8abd896f1",
        "eligible_source_item_count": 347,
        "unit_count": 95,
    },
    "toxic-god": {
        "path": "toxic_god_context_benchmark_l_english.yml",
        "sha256": "1bce35fe8d34b995b473e5a3e59c71aec41bde8076ab8d3e90a16926ff54dad1",
        "eligible_source_item_count": 421,
        "unit_count": 201,
    },
}


def _support_note(note: str, related_chain: str) -> str:
    prefix = f"支持性文本；原关联链：`{related_chain}`。"
    return note if note.startswith(prefix) else f"{prefix}{note}"


def _transform_table_row(line: str, narrative: set[str]) -> tuple[str, str | None]:
    if not line.startswith("| `unit_"):
        return line, None
    parts = line.split("|")
    if len(parts) != 8:
        raise ValueError(f"Unexpected gold row: {line}")
    unit_id = parts[1].strip().strip("`")
    if unit_id in narrative:
        parts[4] = " `primary_member` "
        return "|".join(parts), unit_id
    if parts[4].strip().strip("`") == "reference_asset":
        return line, unit_id
    related_chain = parts[3].strip().strip("`")
    note = parts[5].strip()
    parts[3] = f" `{SUPPORTING_CHAIN}` "
    parts[4] = " `reference_asset` "
    parts[5] = f" {_support_note(note, related_chain)} "
    return "|".join(parts), unit_id


def _transform_markdown(path: Path, narrative: set[str], target_version: str) -> int:
    current_unit: str | None = None
    seen: set[str] = set()
    output: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        heading = UNIT_HEADING.match(line)
        if heading:
            current_unit = heading.group("unit")
        line, table_unit = _transform_table_row(line, narrative)
        if table_unit:
            seen.add(table_unit)
        detail = DETAIL_GOLD.match(line)
        if detail and current_unit and current_unit not in narrative:
            line = (
                f"- Gold: `{SUPPORTING_CHAIN}` / `reference_asset` / "
                f"`{detail.group('confidence')}`"
            )
        relation_bullet = RELATION_BULLET.match(line)
        if relation_bullet and current_unit:
            relation = (
                "primary_member" if current_unit in narrative else "reference_asset"
            )
            line = f"- **relation：** `{relation}`"
        line = line.replace(
            f"Gold generated: `{SOURCE_VERSION}`",
            f"Gold generated: `{target_version}`",
        )
        line = (
            line.replace(
                "## Parent-story metadata（父故事 UI 元数据）",
                "## Supporting text（父故事 UI 元数据）",
            )
            .replace(
                "## Primary members（直接事件成员）",
                "## Event narrative and related supporting text（以 unit relation 为准）",
            )
            .replace(
                "## Supporting context（直接关联静态资源）",
                "## Additional supporting text（直接关联静态资源）",
            )
            .replace(
                "## Theme related（仅主题关联）",
                "## Additional supporting text（原主题关联）",
            )
            .replace("标记为 supporting_context", "标记为 reference_asset")
            .replace("作为 supporting_context", "作为 reference_asset")
            .replace("`supporting_context`", "`reference_asset`")
        )
        if GENERATED_AT.match(line):
            line = f'generated_at: "{target_version}"'
        output.append(line)
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")
    return len(seen)


def _transform_manifest(path: Path, narrative: set[str], target_version: str) -> int:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    document["provenance"]["generated_at"] = target_version
    document["provenance"]["classification_policy"] = (
        "route-aware-v2: event prose remains narrative; non-event and non-literary "
        "text is reference_asset supporting text"
    )
    for assignment in document["assignments"]:
        if assignment["unit_id"] in narrative:
            assignment["relation"] = "primary_member"
            assignment.pop("related_chain", None)
            continue
        related_chain = assignment.get("related_chain") or assignment["chain"]
        assignment["related_chain"] = related_chain
        assignment["chain"] = SUPPORTING_CHAIN
        assignment["relation"] = "reference_asset"
        assignment["note"] = _support_note(assignment.get("note", ""), related_chain)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(document["assignments"])


def _manifest_from_markdown(
    path: Path, demo: str, target_version: str, output: Path,
) -> int:
    assignments = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("| `unit_"):
            continue
        parts = line.split("|")
        if len(parts) != 8:
            raise ValueError(f"Unexpected gold row: {line}")
        item_keys = [
            value.strip().strip("`")
            for value in re.split(r"[;,]", parts[2])
            if value.strip().strip("`")
        ]
        assignments.append({
            "unit_id": parts[1].strip().strip("`"),
            "group_key": item_keys[0] if item_keys else parts[1].strip().strip("`"),
            "item_keys": item_keys,
            "chain": parts[3].strip().strip("`"),
            "relation": parts[4].strip().strip("`"),
            "note": parts[5].strip(),
            "confidence": parts[6].strip().strip("`"),
        })
    document = {
        "provenance": {
            "generated_at": target_version,
            "classification_policy": (
                "route-aware-v2: event prose remains narrative; non-event and "
                "non-literary text is reference_asset supporting text"
            ),
        },
        "fixture": FIXTURES[demo],
        "assignments": assignments,
    }
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(assignments)


def migrate(corpus_root: Path, target_version: str) -> dict[str, dict[str, int]]:
    gold_root = corpus_root / "corpus" / "stellaris" / "context-archive-gold"
    results: dict[str, dict[str, int]] = {}
    for demo, narrative in NARRATIVE_UNITS.items():
        source = gold_root / demo / SOURCE_VERSION
        destination = gold_root / demo / target_version
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite route-aware gold: {destination}")
        shutil.copytree(source, destination)
        markdown_units = 0
        for path in destination.glob("*gold*.md"):
            markdown_units = max(
                markdown_units,
                _transform_markdown(path, narrative, target_version),
            )
        manifest_units = 0
        for path in destination.glob("*gold*manifest.json"):
            manifest_units = _transform_manifest(path, narrative, target_version)
        if demo == "horizon-signal" and manifest_units == 0:
            manifest_units = _manifest_from_markdown(
                destination / "horizon_signal_event_chain_gold.md",
                demo,
                target_version,
                destination / "horizon_signal_event_chain_gold_manifest.json",
            )
        total_units = manifest_units or markdown_units
        results[demo] = {
            "total_units": total_units,
            "narrative_units": len(narrative),
            "reference_asset_units": total_units - len(narrative),
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--target-version", required=True)
    arguments = parser.parse_args()
    result = migrate(arguments.corpus_root.resolve(), arguments.target_version)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
