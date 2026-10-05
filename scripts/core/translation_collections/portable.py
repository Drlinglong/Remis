"""Validated per-game inventories and collision reports for portable exports."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

from .paths import is_reparse, safe_relative


def tree_inventory(root: Path, game_id: str, project: dict, language: str) -> list[dict]:
    if is_reparse(root) or not root.is_dir():
        raise ValueError("Translation output must be an existing unlinked directory.")
    cursor = root.parent
    while cursor != cursor.parent:
        if is_reparse(cursor):
            raise ValueError("Translation output cannot pass through a linked directory or junction.")
        cursor = cursor.parent
    from scripts.core.game_adapters.registry import adapter_for_path
    from scripts.core.game_adapters.workflow_bridge import MANIFEST
    adapter = _game_adapter(game_id)
    metadata_paths = _metadata_paths(adapter, project, language, game_id)
    supported_records = _manifest_paths(root, game_id, language, MANIFEST)
    result, parsed_entry_count = [], 0
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in list(names):
            if is_reparse(base / name):
                raise ValueError("Linked directories are not allowed in translation outputs.")
        names.sort()
        for name in sorted(files):
            path = base / name
            info = path.lstat()
            if is_reparse(path) or not stat.S_ISREG(info.st_mode):
                raise ValueError("Linked or non-regular files are not allowed in translation outputs.")
            if info.st_size > 32_000_000:
                raise ValueError("Translation output file exceeds the 32 MB safety limit.")
            relative = path.relative_to(root).as_posix()
            safe_relative(relative)
            supported = (relative == MANIFEST or relative in metadata_paths
                         or relative in supported_records
                         or _is_translation_resource(path, game_id, adapter, adapter_for_path))
            if not supported:
                continue
            runtime_keys, resource_entry_count = {}, 0
            if relative != MANIFEST and relative not in metadata_paths:
                try:
                    entries = _runtime_entries(adapter, path)
                except (OSError, ValueError) as error:
                    raise ValueError(f"Invalid {game_id} translation resource {relative}: {error}") from error
                resource_entry_count = len(entries)
                parsed_entry_count += resource_entry_count
                records = supported_records.get(relative, {}).get("entries", [])
                source_values = {str(row.get("key")): str(row.get("source", ""))
                                 for row in records if isinstance(row, dict)}
                runtime_keys = {_runtime_key(entry): {"source": _text_hash(source_values[entry.key]) if entry.key in source_values else "",
                                            "target": _text_hash(entry.value), "path": relative}
                                for entry in entries}
                if not entries:
                    continue
            raw = path.read_bytes()
            try:
                raw.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise ValueError(f"Translation output is not UTF-8 text: {relative}") from error
            fact = {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": info.st_size}
            if resource_entry_count:
                fact["entry_count"] = resource_entry_count
            if runtime_keys:
                fact["runtime_keys"] = runtime_keys
            result.append(fact)
    if not parsed_entry_count:
        raise ValueError("Selected output contains no recognized localization entries.")
    return result


def _runtime_key(entry) -> str:
    # Paradox numeric versions are serialization metadata, not runtime identity.
    return getattr(entry, "base_key", entry.key)


def _runtime_entries(adapter, path: Path) -> tuple:
    """Inventory every runtime row, including values excluded from translation."""
    if adapter.id == "paradox":
        from scripts.core.paradox_localization_parser import parse_file
        report = parse_file(path)
        if report.diagnostics:
            raise ValueError("; ".join(issue.code for issue in report.diagnostics))
        entries = report.entries
    else:
        entries = adapter.parse(path).entries
    keys = [_runtime_key(entry) for entry in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate runtime localization keys in one resource")
    return entries


def _game_adapter(game_id: str):
    from scripts.app_settings import GAME_PROFILES_BY_ID
    from scripts.core.game_adapters.registry import get_adapter
    return get_adapter(GAME_PROFILES_BY_ID[game_id])


def _metadata_paths(adapter, project: dict, language: str, game_id: str) -> set[str]:
    from scripts.app_settings import LANGUAGE_BY_CODE
    try:
        return set(adapter.package_metadata(Path(project["source_path"]),
                                            LANGUAGE_BY_CODE.get(language, {"code": language})))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot validate {game_id} package metadata: {error}") from error


def _manifest_paths(root: Path, game_id: str, language: str, manifest_name: str) -> dict[str, dict]:
    manifest_path = root / manifest_name
    if not manifest_path.is_file():
        return {}
    if manifest_path.stat().st_size > 16_000_000:
        raise ValueError("Translation output manifest exceeds the 16 MB safety limit.")
    try:
        output_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Translation output manifest is malformed.") from error
    if output_manifest.get("game_id") != game_id or not isinstance(output_manifest.get("files"), dict):
        raise ValueError("Translation output manifest does not match its game or schema.")
    paths = {}
    for relative, record in output_manifest["files"].items():
        safe_relative(relative)
        if not isinstance(record, dict) or record.get("language") != language:
            raise ValueError("Translation output manifest has invalid language or resource metadata.")
        paths[relative] = record
    return paths


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def uses_global_paradox_keys(game_id: str) -> bool:
    return _game_adapter(game_id).id == "paradox"


def paradox_conflicts(snapshots: list[dict]) -> list[dict]:
    rows: dict[tuple[str, str], list[dict]] = {}
    for member in snapshots:
        for output in member.get("outputs", []):
            language = output["language_code"]
            for file in output["files"]:
                for key, hashes in file.get("runtime_keys", {}).items():
                    rows.setdefault((language, key), []).append({"project_id": member["project_id"], **hashes})
    conflicts = []
    for (language, key), owners in rows.items():
        by_project: dict[str, list[dict]] = {}
        for owner in owners:
            by_project.setdefault(owner["project_id"], []).append(owner)
        for project_id, entries in by_project.items():
            if len(entries) > 1:
                conflicts.append({"language_code": language, "key": key, "projects": [project_id],
                    "paths": sorted({row["path"] for row in entries}),
                    "source_conflict": len({row["source"] for row in entries if row["source"]}) > 1,
                    "translation_conflict": len({row["target"] for row in entries}) > 1,
                    "resolution": "same_member_duplicate"})
        project_rows = [entries[0] for entries in by_project.values()]
        for index, left in enumerate(project_rows):
            for right in project_rows[index + 1:]:
                source_differs = bool(left["source"] and right["source"] and left["source"] != right["source"])
                target_differs = left["target"] != right["target"]
                if source_differs or target_differs:
                    conflicts.append({"language_code": language, "key": key,
                        "projects": [left["project_id"], right["project_id"]],
                        "paths": [left["path"], right["path"]], "source_conflict": source_differs,
                        "translation_conflict": target_differs, "resolution": "mutually_exclusive"})
                elif not left["source"] or not right["source"]:
                    conflicts.append({"language_code": language, "key": key,
                        "projects": [left["project_id"], right["project_id"]],
                        "paths": [left["path"], right["path"]], "source_conflict": None,
                        "translation_conflict": False, "resolution": "source_unverified_overlap"})
    return conflicts


def _is_translation_resource(path: Path, game_id: str, adapter, adapter_for_path) -> bool:
    detected = adapter_for_path(path)
    if detected and detected.game_id == game_id:
        return True
    return adapter.id == "paradox" and path.suffix.casefold() in {".yml", ".yaml", ".csv", ".txt"}


async def portable_member(member: dict, languages: list[str], game_id: str) -> tuple[dict, dict]:
    project_id = str(member.get("project_id") or "")
    from scripts.core.translation_collections import sources
    project = await sources.project_by_id(project_id)
    if project.get("game_id") != game_id or game_id == "surviving_mars":
        raise ValueError("Member project game does not match the collection or is not portable.")
    selections = member.get("outputs")
    if not isinstance(selections, list):
        raise ValueError("Member outputs must be a list of project-owned output selections.")
    by_language = {item.get("language_code"): item for item in selections if isinstance(item, dict)}
    if set(by_language) != set(languages):
        raise ValueError("Every member must select exactly one output for every target language.")
    facts = []
    for language in languages:
        folder = sources.select_output(project, by_language[language])
        inventory = await asyncio.to_thread(tree_inventory, folder, game_id, project, language)
        facts.append({"language_code": language, "output_folder_name": folder.name, "files": inventory})
    snapshot = {"project_id": project_id, "game_id": project.get("game_id"), "outputs": facts}
    return snapshot, {"project": project, "folders": [sources.select_output(project, by_language[code]) for code in languages]}


def copy_portable(staging: Path, collection: dict, portable: list[dict], snapshots: list[dict], conflicts: list[dict]) -> int:
    manifest = {"collection_id": collection["collection_id"], "game_id": collection["game_id"],
                "title": collection["title"], "description": collection.get("description", ""),
                "target_languages": collection["target_languages"], "runtime_verified": False,
                "steam_id": str(collection.get("steam_id") or ""), "members": [], "key_overlaps": conflicts}
    count = 0
    for member, snapshot in zip(portable, snapshots):
        project = member["project"]
        project_id = str(project["project_id"])
        name = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
        row = {"project_id": project_id, "name": project.get("name", project_id), "outputs": []}
        for language, source, expected_output in zip(collection["target_languages"], member["folders"], snapshot["outputs"]):
            root = staging / "members" / name / language
            root.mkdir(parents=True, exist_ok=True)
            inventory = tree_inventory(source, collection["game_id"], project, language)
            if inventory != expected_output["files"]:
                raise ValueError("Translation output changed after collection preview.")
            row["outputs"].append({"language_code": language, "directory": f"members/{name}/{language}"})
            for item in inventory:
                destination = root.joinpath(*safe_relative(item["path"]))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source.joinpath(*safe_relative(item["path"])), destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("Translation output changed during collection copy.")
                count += 1
        manifest["members"].append(row)
    (staging / "collection.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    instructions = ["Install each member translation directory according to its game's normal mod-localization rules.",
                    "The collection does not include a shared runtime engine."]
    if conflicts:
        instructions.append("Paradox key overlaps were found; follow the conflict or review guidance in collection.json.")
    (staging / "README.txt").write_text("\n".join(instructions) + "\n", encoding="utf-8")
    return count + 2
