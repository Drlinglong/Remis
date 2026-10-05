"""Select translation input without changing original Lua text or stable IDs."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath

from scripts.core import surviving_mars_csv as adapter
from scripts.core.services.mars_translation_package import LANGUAGE_NAMES


def translation_source(entry: dict) -> str:
    return entry.get("translation_source_text", entry.get("text", entry.get("source", "")))


def _tables(root: Path) -> tuple[list[dict], dict]:
    inventory, documents = [], {}
    for path in sorted(root.rglob("*.csv")):
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError("Source table cannot traverse redirected paths")
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Source localization CSV exceeds the text input budget")
        try:
            document = adapter.parse_file(path)
        except adapter.NotSurvivingMarsCsv:
            continue
        relative = path.relative_to(root).as_posix()
        rows = [row for row in document.rows[document.header_row_index + 1:] if row]
        documents[relative] = rows
        inventory.append({"path": relative, "row_count": len(rows), "samples": [
            {"id": row[0], "text": row[1][:300], "translation": row[2][:300]}
            for row in rows[:2]]})
    return inventory, documents


def _add_table_entries(manifest: dict, rows: list, relative: str) -> None:
    """CSV-only keyed strings are valid even when the static Lua scan misses calls."""
    shared = {str(row["id"]) for row in manifest.get("shared_references", [])}
    for row in rows:
        key, original = row[:2]
        if key in manifest["entries"] or key in shared:
            continue
        manifest["entries"][key] = {
            "id": key, "text": original, "kind": "existing_t", "identity": f"existing-t\0{key}",
            "context": row[4], "params": {}, "refs": [{"path": relative}],
            "rewrites": [], "review_required": False, "review_reason": None,
        }


def select_source(root: Path, manifest: dict, request: dict) -> dict:
    """Bind source language, table, column and selected values to the plan fingerprint."""
    result = copy.deepcopy(manifest)
    language = request.get("source_language")
    column = request.get("source_column") or "Text"
    table = request.get("source_table") or None
    blockers = []
    if language not in LANGUAGE_NAMES:
        blockers.append({"code": "source_language_required", "message": "Choose the actual source language; it is not inferred from a CSV filename."})
    if column not in {"Text", "Translation"}:
        raise ValueError("Source column must be Text or Translation")
    inventory, documents = _tables(root)
    result["source_tables"] = inventory
    selection = {"language": language, "table": table, "column": column}
    result["source_selection"] = selection
    if column == "Translation" and not table:
        blockers.append({"code": "source_table_required", "message": "Select a localization CSV before using its Translation column."})
    if table:
        relative = PurePosixPath(table)
        if relative.is_absolute() or ".." in relative.parts or "\\" in table or table not in documents:
            raise ValueError("Choose a source_table relative path from this archive's inspected CSV tables")
        rows = documents[table]
        _add_table_entries(result, rows, table)
        values = {row[0]: row[1 if column == "Text" else 2] for row in rows}
        selection["ids"] = sorted(set(values) & set(result["entries"]), key=int)
        if not selection["ids"]:
            blockers.append({"code": "empty_source_table", "message": "The selected source table has no usable localization IDs."})
        required = set(selection["ids"])
        if request.get("delivery_mode", "source_copy") != "text_only":
            required.update(result["entries"])
        for key in sorted(required, key=int):
            value = values.get(key)
            if not value or not value.strip():
                blockers.append({"id": key, "code": "missing_source_value", "message": f"Selected {column} source is missing for ID {key}; no fallback to another language is allowed."})
                continue
            entry = result["entries"][key]
            entry["translation_source_text"] = value
            entry["translation_source_sha256"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
        omitted = sorted(set(result["entries"]) - set(selection["ids"]), key=int)
        if omitted and request.get("delivery_mode") == "text_only":
            result.setdefault("diagnostics", []).append({"code": "outside_selected_source_table", "ids": omitted,
                "message": "These Lua candidates are outside the selected CSV and will remain unchanged; inspect their role before claiming full coverage."})
    result["source_blockers"] = blockers
    return result


def write_prepared_source(destination: Path, manifest: dict, approved_ids: list[str]) -> None:
    """Create the isolated translation input; original source text stays in the manifest."""
    destination.mkdir(parents=True, exist_ok=False)
    selected = set(approved_ids)
    if selected - set(manifest["entries"]):
        raise ValueError("Preparation contains unknown selected IDs")
    manifest["approved_ids"] = sorted(selected, key=int)
    with (destination / "ModTexts.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(adapter.HEADER)
        for key in sorted(selected, key=int):
            entry = manifest["entries"][key]
            writer.writerow([key, translation_source(entry), "", "", entry.get("context", "")])
    (destination / "mars_lua_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
