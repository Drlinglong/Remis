"""Keep source-change review requirements with generated translation packages."""
import json
from pathlib import Path

from .output_records import output_record
from .workflow_bridge import MANIFEST, atomic_write


def pending_keys(file_data: dict, language: str) -> set[str]:
    first = next(iter(file_data.get("adapter_key_map", {}).values()), {})
    document = first.get("adapter_document")
    if not document:
        return set()
    root = Path(document.metadata.get("project_root", document.metadata.get("source_root", document.path.parent)))
    sidecar = root / ".remis_project.json"
    if not sidecar.is_file():
        return set()
    from scripts.app_settings import resolve_path
    config = json.loads(sidecar.read_text(encoding="utf-8")).get("config", {})
    latest = {}
    sources = {entry.key: entry.value for entry in document.entries}
    for directory in config.get("translation_dirs", []):
        for path in Path(resolve_path(directory)).rglob(MANIFEST):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            for record in manifest.get("files", {}).values():
                if record.get("source_path") != document.path.resolve().relative_to(root.resolve()).as_posix():
                    continue
                if record.get("language") != language:
                    continue
                for entry in record.get("entries", []):
                    key = entry["key"]
                    if key not in sources or sources[key] != entry["source"]:
                        continue
                    timestamp = path.stat().st_mtime_ns
                    if key not in latest or timestamp > latest[key][0]:
                        latest[key] = timestamp, entry.get("needs_review", False)
    return {key for key, (_, pending) in latest.items() if pending}


def acknowledge(path: Path, keys: list[str]) -> None:
    root, _ = output_record(path)
    if root is None:
        return
    manifest_path = root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"][path.resolve().relative_to(root).as_posix()].get("entries", []):
        if entry["key"] in keys:
            entry["needs_review"] = False
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
