"""Expose existing P社 and Mars parsers through the same small adapter contract.

Their proven workflow paths remain compatible; no format is converted to another.
"""
from pathlib import Path
import re

from .contracts import Discovery, Document, Entry, Resource


class LegacyAdapter:
    def __init__(self, profile: dict):
        self.profile = profile
        self.game_id = profile["id"]
        self.id = profile.get("format_adapter_id", "paradox")

    def discover(self, root: Path, source_lang: dict, game_version=None) -> Discovery:
        from scripts.core.services.initial_translation_discovery_service import discover_localizable_files
        files = discover_localizable_files(root.name, self.profile, source_lang, override_path=str(root))
        return Discovery(tuple(Resource(Path(item["path"]), item["file_path"],
                                         {"source_root": str(root), "file_info": item,
                                          "source_language": source_lang}) for item in files))

    def parse(self, path: Path, metadata=None) -> Document:
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        return self.parse_text(text, path, metadata)

    def parse_text(self, text: str, path: Path, metadata=None) -> Document:
        if self.id == "surviving_mars_csv":
            from scripts.core import surviving_mars_csv
            parsed = surviving_mars_csv.parse_text(text)
            entries = tuple(Entry(e.key, e.value, e.line_number, {"row_index": e.row_index}) for e in parsed.entries)
        else:
            from scripts.core.paradox_localization_parser import parse_text
            report = parse_text(text)
            if report.diagnostics:
                raise ValueError("; ".join(d.code for d in report.diagnostics))
            entries = tuple(Entry(e.key, e.value, e.line_number, {"entry": e}) for e in report.eligible_entries)
        return Document(path, text, entries, dict(metadata or {}))

    def render(self, document: Document, translations: dict[str, str], target_lang: dict) -> dict[str, str]:
        root = Path(document.metadata.get("source_root", document.path.parent))
        relative = document.path.relative_to(root).as_posix()
        values = [translations.get(e.key, e.value) for e in document.entries]
        if self.id == "surviving_mars_csv":
            from scripts.core.surviving_mars_csv import rewrite_text
            key_map = {i: {"key_part": e.key, **e.metadata} for i, e in enumerate(document.entries)}
            return {relative: rewrite_text(document.source_text, values, key_map)}
        from scripts.core.paradox_localization_parser import patch_text
        content = patch_text(document.source_text, [(entry.metadata["entry"], value)
                             for entry, value in zip(document.entries, values)])
        content = re.sub(r"(?m)^([\ufeff \t]*)l_[\w-]+:",
                         lambda match: match[1] + target_lang["key"] + ":", content, count=1)
        source_key = document.metadata.get("source_language", {}).get("key", "l_english")
        relative = relative.replace(source_key, target_lang["key"])
        relative = re.sub(r"(^|/)" + re.escape(source_key.removeprefix("l_")) + r"/",
                          lambda match: match[1] + target_lang["key"].removeprefix("l_") + "/", relative)
        return {relative: content}

    def package_metadata(self, root: Path, target_lang: dict, game_version=None) -> dict[str, str]:
        return {}

    def language_folder(self, language: dict) -> str:
        return language.get("key", "l_english").removeprefix("l_")

    def validate(self, source: str, target: str):
        from scripts.utils.post_process_validator import validate_text
        from .contracts import Diagnostic
        return [Diagnostic(result.code or "format_error", result.message, severity=result.level.value)
                for result in validate_text(self.game_id, target, source_text=source)]
