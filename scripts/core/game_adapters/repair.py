"""Validated single-entry writeback for structured game resources."""
from __future__ import annotations

import re
from pathlib import Path

from .output_records import output_record
from .registry import resource_adapter


def _parse_metadata(game_id: str, path: Path) -> dict:
    parts = [part.casefold() for part in path.parts]
    if game_id == "project_zomboid":
        translate = next((index for index, part in enumerate(parts) if part == "translate"), -1)
        start = next((index for index in range(translate) if parts[index] == "common"), -1)
        if start < 0:
            start = next((index for index in range(translate) if parts[index] == "media"), -1)
        stable_path = Path(*path.parts[start:]).as_posix() if start >= 0 else path.name
        language = path.parts[translate + 1] if translate >= 0 and translate + 1 < len(path.parts) else ""
        category = re.sub(r"_[A-Z]{2,5}$", "", path.stem, flags=re.IGNORECASE)
        category = re.sub(r"_[A-Z]{2,5}$", "", category, flags=re.IGNORECASE)
        return {"stable_relative_path": stable_path, "language_folder": language,
                "category": category}
    if "languages" in parts:
        index = parts.index("languages")
        if index + 1 < len(path.parts):
            return {"source_language": path.parts[index + 1]}
    return {}


def _entry_matches(document, key: str):
    exact = [entry for entry in document.entries if entry.key == key]
    if exact:
        return exact if len(exact) == 1 else []
    raw = [entry for entry in document.entries
           if entry.metadata.get("resource_key") == key or entry.key.rsplit("::", 1)[-1] == key]
    return raw if len(raw) == 1 else []


def _protected_by_manifest(path: Path, key: str) -> bool:
    _, record = output_record(path)
    protected = {item["key"] for item in record.get("entries", [])
                 if item.get("needs_review") and isinstance(item.get("key"), str)}
    return key in protected or any(item.rsplit("::", 1)[-1] == key for item in protected)


def _language(path: Path, target_lang: str | None) -> dict:
    parts = [part.casefold() for part in path.parts]
    for index, part in enumerate(parts[:-1]):
        if part in {"translate", "languages"}:
            return {"folder": path.parts[index + 1]}
    return {"code": target_lang or "en"}


def read_value(path: Path, game_id: str, key: str) -> str | None:
    adapter = resource_adapter(game_id)
    if not adapter:
        return None
    document = adapter.parse(path, _parse_metadata(game_id, path))
    matches = _entry_matches(document, key)
    return matches[0].value if len(matches) == 1 else None


def apply_fix(path: Path, game_id: str, key: str, value: str,
              target_lang: str | None = None) -> bool:
    adapter = resource_adapter(game_id)
    if not adapter or _protected_by_manifest(path, key):
        return False
    metadata = _parse_metadata(game_id, path)
    document = adapter.parse(path, metadata)
    matches = _entry_matches(document, key)
    if len(matches) != 1:
        return False
    entry = matches[0]
    translations = {item.key: item.value for item in document.entries}
    translations[entry.key] = value
    rendered = adapter.render(document, translations, _language(path, target_lang))
    if len(rendered) != 1:
        return False
    content = next(iter(rendered.values()))
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    return True
