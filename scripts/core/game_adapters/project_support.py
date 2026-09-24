"""Read-only project discovery and capability projection for game adapters."""
from __future__ import annotations

import uuid
from pathlib import Path

from .registry import adapter_for_path, game_capabilities, resource_adapter


def inspect_support(game_id: str, root: str, language: str = "en",
                    game_version: str | None = None) -> dict:
    adapter = resource_adapter(game_id)
    response = {"game_id": game_id, "capabilities": game_capabilities(game_id),
                "diagnostics": [], "resources": [], "metadata": {}}
    if not adapter:
        return response
    try:
        discovery = adapter.discover(Path(root), {"code": language}, game_version)
        response["diagnostics"] = [d.as_dict() for d in discovery.diagnostics]
        response["metadata"] = discovery.metadata
        for resource in discovery.resources:
            try:
                document = adapter.parse(resource.path, {"source_root": root, **resource.metadata})
                response["resources"].append({"path": str(resource.path),
                                              "entry_count": len(document.entries)})
                response["diagnostics"].extend(document.metadata.get("diagnostics", []))
            except (OSError, ValueError) as exc:
                response["diagnostics"].append({"code": "resource_parse_error", "severity": "error",
                                                "path": str(resource.path), "message": str(exc)})
    except (OSError, ValueError) as exc:
        response["diagnostics"].append({"code": "resource_discovery_error", "severity": "error",
                                        "path": root, "message": str(exc)})
    return response


def discover_manifest(project_id: str, source_path: str, translation_dirs: list[str],
                      source_language: str, game_id: str, statuses: dict | None) -> dict:
    support = inspect_support(game_id, source_path, source_language)
    warnings = list(support["diagnostics"])
    resources = [(Path(item["path"]), "source", item["entry_count"])
                 for item in support["resources"]]
    seen = {str(path.resolve()).casefold() for path, _, _ in resources}
    for directory in translation_dirs:
        root = Path(directory)
        if not root.is_dir():
            warnings.append({"code": "directory_unavailable", "path": directory, "file_type": "translation"})
            continue
        for path in sorted(root.rglob("*")):
            resolved = path.resolve()
            if not path.is_file() or not resolved.is_relative_to(root.resolve()):
                continue
            identity = str(resolved).casefold()
            adapter = adapter_for_path(path)
            if identity in seen or not adapter or adapter.game_id != game_id:
                continue
            seen.add(identity)
            try:
                resources.append((path, "translation", len(adapter.parse(path).entries)))
            except (OSError, ValueError) as exc:
                warnings.append({"code": "resource_parse_error", "path": str(path),
                                 "file_type": "translation", "message": str(exc)})
    files = []
    for path, kind, count in resources:
        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(path).lower().replace("\\", "/")))
        status = (statuses or {}).get(file_id, "todo")
        if kind == "translation":
            from .output_records import output_record
            _, record = output_record(path)
            if any(entry.get("needs_review") for entry in record.get("entries", [])):
                status = "proofreading"
        files.append({"file_id": file_id, "project_id": project_id, "file_path": str(path),
                      "status": status, "original_key_count": count, "line_count": count, "file_type": kind})
    return {"project_id": project_id, "files": files, "file_count": len(files),
            "scanned_paths": [source_path, *translation_dirs], "warnings": warnings}
