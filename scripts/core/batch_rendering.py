"""Render complete selected resources, then verify their actual output column."""
from pathlib import Path

from .batch_repository import BatchConflict
from .batch_sources import safe_relative
from .game_adapters.registry import get_adapter


def render_outputs(snapshot, selected, translations, target_language):
    from scripts.app_settings import GAME_PROFILES_BY_ID
    adapter = get_adapter(GAME_PROFILES_BY_ID[snapshot["game_id"]])
    outputs = {}
    for file in snapshot["files"]:
        if file["file_id"] not in selected:
            continue
        document = adapter.parse_text(file["content"], Path(file["path"]),
            {"source_root": snapshot["source_root"], "source_language": snapshot["source_language"]})
        values = {entry["key"]: translations[entry["id"]] for entry in file["entries"]}
        rendered = adapter.render(document, values, target_language)
        if snapshot["adapter_id"] == "surviving_mars_csv":
            from scripts.core import surviving_mars_csv
            if len(rendered) != 1:
                raise BatchConflict("render_integrity_error", "CSV rendering produced an unexpected resource count.")
            parsed = surviving_mars_csv.parse_text(next(iter(rendered.values())))
            actual = {row[0]: row[2] for row in parsed.rows[parsed.header_row_index + 1:] if row}
            for key, value in values.items():
                if actual.get(key) != value:
                    raise BatchConflict("render_integrity_error", "CSV Translation values do not match the accepted results.")
            original = surviving_mars_csv.parse_text(file["content"])
            if len(original.rows) != len(parsed.rows) or any(before[:2] + before[3:] != after[:2] + after[3:] for before, after in zip(original.rows, parsed.rows)):
                raise BatchConflict("render_integrity_error", "CSV rendering changed a protected column.")
        else:
            merged = {}
            for relative, content in rendered.items():
                parsed = adapter.parse_text(content, Path(relative))
                merged.update({entry.key: entry.value for entry in parsed.entries})
            if any(merged.get(key) != value for key, value in values.items()):
                raise BatchConflict("render_integrity_error", "Rendered resource values differ from the accepted results.")
        for relative, content in rendered.items():
            relative = safe_relative(relative)
            if relative in outputs:
                raise BatchConflict("output_path_collision", "Two source resources render to the same output path.")
            outputs[relative] = content
    if not outputs:
        raise BatchConflict("empty_apply_selection", "No complete resources were selected.")
    return outputs
