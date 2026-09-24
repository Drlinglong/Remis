"""Map adapter entries to the existing source/translation archive contract."""
from pathlib import Path

from .registry import adapter_for_path, resource_adapter
from .workflow_bridge import build_snapshot


def scan_source(source_path: str, source_language: str, game_id: str):
    from scripts.core.services.translation_archive_service import SourceScanIssue, SourceScanResult
    result = SourceScanResult()
    try:
        files = build_snapshot(source_path, {"id": game_id}, {"code": source_language})
        for item in files:
            item["key_map"] = list(item["key_map"].values())
        result.files = files
        result.scanned_file_count = len(files)
    except (OSError, ValueError) as exc:
        result.issues.append(SourceScanIssue(source_path, "resource_scan_error", str(exc)))
    return result


def scan_translations(source_files: list[dict], translation_dirs: list[str], game_id: str):
    from scripts.app_settings import LANGUAGES
    adapter = resource_adapter(game_id)
    candidates = {}
    for item in source_files:
        for index, info in enumerate(item["key_map"]):
            candidates.setdefault(info["key_part"], []).append((item, index))
    results, matched = {}, set()
    for directory in translation_dirs:
        root = Path(directory)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                continue
            detected = adapter_for_path(path)
            if not detected or detected.game_id != game_id:
                continue
            languages = [lang["code"] for lang in LANGUAGES.values()
                         if adapter.language_folder(lang).casefold() in [part.casefold() for part in path.parts]]
            if len(languages) != 1:
                continue
            language = languages[0]
            for entry in adapter.parse(path).entries:
                matches = candidates.get(entry.key, [])
                if len(matches) > 1 and entry.value.strip():
                    raise ValueError(f"Ambiguous source resource for existing translation {entry.key}; review candidates")
                if len(matches) != 1 or not entry.value.strip():
                    continue
                item, index = matches[0]
                identity = language, item["file_path"], index
                values = results.setdefault(language, {}).setdefault(
                    item["file_path"], ["" for _ in item["texts_to_translate"]])
                if identity in matched and values[index] != entry.value:
                    raise ValueError(f"Conflicting existing translations for {entry.key}")
                values[index] = entry.value
                matched.add(identity)
    return results, len(matched)
