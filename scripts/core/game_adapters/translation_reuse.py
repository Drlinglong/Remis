"""Conservative reuse of explicit on-disk translations within one Mod."""
import json
from pathlib import Path

from .registry import resource_adapter


def existing_translations(file_data: dict, target_lang: dict) -> dict[int, str]:
    key_map = file_data.get("key_map", {})
    first = next(iter(key_map.values()), {}) if isinstance(key_map, dict) else {}
    document = first.get("adapter_document")
    adapter = resource_adapter(first.get("adapter_id"))
    if not document or not adapter:
        return {}
    source_root = Path(document.metadata.get("source_root", document.path.parent))
    roots = [source_root]
    config_path = Path(document.metadata.get("project_root", source_root)) / ".remis_project.json"
    if config_path.is_file():
        from scripts.app_settings import resolve_path
        config = json.loads(config_path.read_text(encoding="utf-8")).get("config", {})
        roots.extend(Path(resolve_path(path)) for path in config.get("translation_dirs", []))
    expected = adapter.render(document, {e.key: e.value for e in document.entries}, target_lang)
    folder = adapter.language_folder(target_lang).casefold()
    candidates = {}
    for root in roots:
        for relative in expected:
            name = Path(relative).name
            for path in root.rglob(name) if root.is_dir() else ():
                if folder not in [part.casefold() for part in path.parts]:
                    continue
                if path.resolve() == document.path.resolve() or not path.resolve().is_relative_to(root.resolve()):
                    continue
                try:
                    target = adapter.parse(path)
                except (OSError, ValueError):
                    continue
                for entry in target.entries:
                    if entry.value.strip():
                        candidates.setdefault(entry.key, set()).add(entry.value)
    ambiguous = [entry.key for entry in document.entries if len(candidates.get(entry.key, set())) > 1]
    if ambiguous:
        raise ValueError("Conflicting existing translations require review: " + ", ".join(ambiguous))
    return {index: next(iter(candidates[entry.key])) for index, entry in enumerate(document.entries)
            if len(candidates.get(entry.key, set())) == 1}
