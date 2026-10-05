"""Preview and build safe packages from project-owned translation outputs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from . import portable as _portable
from .paths import is_reparse as _is_reparse, safe_relative as _safe_relative

_tree_inventory = _portable.tree_inventory
_paradox_conflicts = _portable.paradox_conflicts
_portable_member = _portable.portable_member
_copy_portable = _portable.copy_portable
_uses_global_paradox_keys = _portable.uses_global_paradox_keys


def _diagnostic(code: str, message: str, project_id: str | None = None) -> dict:
    item = {"code": code, "message": message, "severity": "error"}
    if project_id:
        item["project_id"] = project_id
    return item


def _collection_identity(collection: dict) -> None:
    mod_id = str(collection.get("mod_id") or "")
    if not re.fullmatch(r"RemisCollection[a-f0-9]+", mod_id):
        raise ValueError("Collection mod_id must use the stable RemisCollection+hex identity.")
    if not collection.get("collection_id"):
        raise ValueError("Collection collection_id is required.")
    steam_id = str(collection.get("steam_id") or "")
    if steam_id and not steam_id.isdecimal():
        raise ValueError("Collection steam_id must be empty or numeric.")
    if not collection.get("title") or not collection.get("game_id"):
        raise ValueError("Collection title and game_id are required.")


def _targets(collection: dict) -> list[str]:
    values = collection.get("target_languages")
    if (not isinstance(values, list) or not values
            or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9-]{2,20}", x) for x in values)):
        raise ValueError("Select at least one target language.")
    if len(set(values)) != len(values):
        raise ValueError("Target languages must be unique.")
    return values


async def _mars_member(collection: dict, member: dict, language_selections: list[dict]) -> tuple[dict, dict, dict]:
    from scripts.core.mars_pipeline import delivery, workflow_delivery

    project_id = str(member.get("project_id") or "")
    project, receipt = await workflow_delivery._context(project_id)
    if project.get("game_id") != "surviving_mars":
        raise ValueError("Member is not a prepared Surviving Mars project.")
    manifest = receipt["manifest"]
    entries = manifest.get("entries", {})
    approved = set(map(str, manifest.get("approved_ids", [])))
    if any(key not in approved or row.get("kind") != "existing_t" for key, row in entries.items()):
        raise ValueError("Collection text mods require every manifest entry to be approved existing_t; hardcoded/source-copy entries are uncovered.")
    selections = []
    for target in language_selections:
        selections.append({"language_code": target["language_code"], "output_folder_name": target["output_folder_name"]})
    translations = workflow_delivery._read_translations(project, manifest, selections, "text_only")
    preview = await asyncio.to_thread(delivery.inspect_delivery, receipt["source_path"], manifest, translations, "text_only")
    if preview.get("status") != "ready":
        raise ValueError("Prepared member has incomplete or uncovered text-only entries.")
    source_id = str(manifest.get("mod_id") or "")
    if not source_id:
        raise ValueError("Prepared member manifest has no stable Mod ID.")
    snapshot = {"project_id": project_id, "run_id": receipt["run_id"], "mod_id": source_id,
                "outputs": [{"language_code": selection["language_code"],
                             "output_folder_name": selection["output_folder_name"]}
                            for selection in selections],
                "source_fingerprint": preview["source_fingerprint"],
                "output_fingerprint": preview["fingerprint"]}
    rows = {key: {"source": entries[key].get("text", entries[key].get("source")),
                  "translations": {lang: values[key] for lang, values in translations.items()},
                  "owners": {source_id}} for key in entries}
    return snapshot, rows, {"receipt": receipt, "manifest": manifest, "translations": translations}


def _merge_rows(target: dict, incoming: dict) -> None:
    for key, row in incoming.items():
        existing = target.get(key)
        if existing and existing["source"] != row["source"]:
            raise ValueError(f"Collection source conflict for translation ID {key}.")
        if existing:
            for language, text in row["translations"].items():
                if language in existing["translations"] and existing["translations"][language] != text:
                    raise ValueError(f"Collection target conflict for translation ID {key} ({language}).")
                existing["translations"][language] = text
            existing["owners"].update(row["owners"])
        else:
            target[key] = {"source": row["source"], "translations": dict(row["translations"]),
                           "owners": set(row["owners"])}


async def _inspect(collection: dict) -> tuple[dict, list[dict]]:
    _collection_identity(collection)
    languages = _targets(collection)
    members = collection.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("Collection must include at least one member.")
    project_ids = [str(member.get("project_id") or "") for member in members]
    if not all(project_ids) or len(set(project_ids)) != len(project_ids):
        raise ValueError("Collection members require unique project IDs.")
    snapshots, merged, portable = [], {}, []
    if collection["game_id"] == "surviving_mars":
        for member in members:
            selections = member.get("outputs")
            if not isinstance(selections, list):
                raise ValueError("Each Mars member requires project-owned outputs.")
            by_language = {item.get("language_code"): item for item in selections if isinstance(item, dict)}
            if set(by_language) != set(languages):
                raise ValueError("Every Mars member must select exactly one output for every target language.")
            ordered = [by_language[language] for language in languages]
            snapshot, rows, _ = await _mars_member(collection, member, ordered)
            snapshots.append(snapshot)
            _merge_rows(merged, rows)
        mode = "mars_text_mod"
        entry_count = sum(len({k for k, row in merged.items() if lang in row["translations"]}) for lang in languages)
        file_count = len(_render_mars(collection, snapshots, merged))
    else:
        for member in members:
            if member.get("game_id", collection["game_id"]) != collection["game_id"]:
                raise ValueError("All collection members must use the collection game.")
            snapshot, fact = await _portable_member(member, languages, collection["game_id"])
            snapshots.append(snapshot)
            portable.append(fact)
        mode = "portable_translations"
        entry_count = sum(item.get("entry_count", 0) for snap in snapshots
                          for output in snap["outputs"] for item in output["files"])
        file_count = sum(len(output["files"]) for snap in snapshots for output in snap["outputs"]) + 2
    payload = {"collection": {key: collection.get(key) for key in
                ("collection_id", "mod_id", "game_id", "title", "description", "target_languages", "steam_id", "revision")},
               "members": snapshots, "mode": mode}
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode("utf-8")).hexdigest()
    conflicts = (_paradox_conflicts(snapshots) if mode == "portable_translations"
                 and _uses_global_paradox_keys(collection["game_id"]) else [])
    diagnostics = ([] if mode == "mars_text_mod" else [{
        "code": "coverage_unverified", "message": "Portable export verifies owned files and selected languages; translation completeness is not independently verified.",
        "severity": "warning"}])
    blocking_duplicates = [item for item in conflicts if item["resolution"] == "same_member_duplicate"]
    if blocking_duplicates:
        diagnostics.append({"code": "duplicate_member_keys",
            "message": f"{len(blocking_duplicates)} localization keys occur more than once within a member output.",
            "severity": "error"})
    runtime_conflicts = [item for item in conflicts if item["resolution"] == "mutually_exclusive"]
    if runtime_conflicts:
        diagnostics.append({"code": "mutually_exclusive_key_conflicts",
            "message": f"{len(runtime_conflicts)} same-language Paradox key conflicts were found. Conflicting member Mods cannot safely be enabled together.",
            "severity": "warning"})
    unknown_overlaps = [item for item in conflicts if item["resolution"] == "source_unverified_overlap"]
    if unknown_overlaps:
        diagnostics.append({"code": "key_overlap_source_unverified",
            "message": f"{len(unknown_overlaps)} same-language Paradox key overlaps lack source text in their output manifests; review compatibility before enabling both Mods.",
            "severity": "warning"})
    return {"fingerprint": fingerprint, "members": snapshots, "diagnostics": diagnostics,
            "can_export": not bool(blocking_duplicates),
            "mode": mode, "file_count": file_count, "entry_count": entry_count,
            "conflicts": conflicts, "runtime_verified": False}, portable


async def inspect_collection(collection: dict) -> dict:
    try:
        result, _ = await _inspect(collection)
        return result
    except Exception as error:
        return {"fingerprint": "", "members": [], "diagnostics": [_diagnostic("collection_invalid", str(error))],
                "can_export": False, "mode": "mars_text_mod" if collection.get("game_id") == "surviving_mars" else "portable_translations",
                "file_count": 0, "entry_count": 0, "conflicts": [], "runtime_verified": False}


def _render_mars(collection: dict, members: list[dict], merged: dict) -> dict[str, bytes]:
    from scripts.core.mars_pipeline import delivery, workflow_delivery_companions as companions
    from scripts.core.services import mars_translation_package as package

    mod_id = collection["mod_id"]
    files = {}
    tables = []
    for language in collection["target_languages"]:
        owners_map: dict[tuple[str, ...], list[str]] = {}
        for key, row in merged.items():
            if language in row["translations"]:
                owners_map.setdefault(tuple(sorted(row["owners"])), []).append(key)
        for owners, ids in sorted(owners_map.items()):
            digest = hashlib.sha256((language + "\0" + "\0".join(owners)).encode("utf-8")).hexdigest()[:12]
            rel = f"Localization/{package._language(language)}/RemisCollection-{digest}.csv"
            entries = {key: {"text": merged[key]["source"]} for key in ids}
            values = {key: merged[key]["translations"][language] for key in ids}
            files[rel] = delivery._entry_rows(entries, values, set(ids)).encode("utf-8")
            tables.append({"owners": list(owners), "ids": sorted(ids, key=int),
                           "language": package._language(language), "path": f"Mod/{mod_id}/{rel}"})
    digest = hashlib.sha256(json.dumps(members, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    files["Code/RemisCollection.lua"] = companions._render_loader(tables, digest)
    title = str(collection["title"])
    description = str(collection.get("description") or "")
    steam = str(collection.get("steam_id") or "")
    fields = ["return PlaceObj('ModDef', {", f"  'title', {package._lua_string(title)},",
              f"  'id', {package._lua_string(mod_id)},", "  'lua_revision', 350453,",
              f"  'description', {package._lua_string(description)},", "  'optional_mod', true,",
              f"  'steam_id', {package._lua_string(steam)},",
              "  'code', { 'Code/RemisCollection.lua', },", "})", ""]
    files["metadata.lua"] = "\n".join(fields).encode("utf-8")
    files["items.lua"] = ("return {\n  PlaceObj('ModItemCode', { 'name', 'RemisCollection', }),\n}\n").encode("utf-8")
    files["collection.json"] = (json.dumps({"collection_id": collection["collection_id"],
        "mod_id": mod_id, "game_id": collection["game_id"], "target_languages": collection["target_languages"],
        "members": members, "runtime_verified": False}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    member_ids = ", ".join(str(item["mod_id"]) for item in members)
    files["README.txt"] = (f"Keep the original Mods enabled for their translations to load.\n"
        f"This collection loads each member's IDs only while that member is active: {member_ids}.\n"
        "Install and enable this collection Mod. Runtime behavior has not been verified.\n").encode("utf-8")
    return files


def _write_files(staging: Path, files: dict[str, bytes]) -> None:
    for relative, content in files.items():
        target = staging.joinpath(*_safe_relative(relative))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)


async def build_collection(collection: dict, destination: Path, expected_fingerprint: str) -> dict:
    inspection, portable = await _inspect(collection)
    if not inspection["can_export"] or inspection["fingerprint"] != expected_fingerprint:
        raise ValueError("Collection changed after preview or is not exportable.")
    destination = Path(os.path.abspath(destination))
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Collection destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cursor = destination.parent
    while cursor != cursor.parent:
        if _is_reparse(cursor):
            raise ValueError("Collection destination cannot pass through a linked directory or junction.")
        cursor = cursor.parent
    staging = Path(tempfile.mkdtemp(prefix=".remis-collection-", dir=destination.parent))
    try:
        if inspection["mode"] == "mars_text_mod":
            merged = {}
            current_snapshots = []
            for member in collection["members"]:
                selections = member["outputs"]
                snapshot, rows, _ = await _mars_member(collection, member, [next(x for x in selections if x["language_code"] == lang) for lang in collection["target_languages"]])
                current_snapshots.append(snapshot)
                _merge_rows(merged, rows)
            if current_snapshots != inspection["members"]:
                raise ValueError("A Mars member changed after collection preview.")
            files = _render_mars(collection, inspection["members"], merged)
            _write_files(staging, files)
            count = len(files)
        else:
            count = _copy_portable(staging, collection, portable, inspection["members"], inspection.get("conflicts", []))
        refreshed, _ = await _inspect(collection)
        if refreshed["fingerprint"] != expected_fingerprint:
            raise ValueError("Collection changed while files were being staged.")
        os.rename(staging, destination)
    except BaseException:
        _remove_staging(staging, destination.parent)
        raise
    return {"package_path": str(destination), "file_count": count, "mode": inspection["mode"],
            "members": inspection["members"], "runtime_verified": False}


def _remove_staging(staging: Path, expected_parent: Path) -> None:
    if (staging.name.startswith(".remis-collection-") and not _is_reparse(staging)
            and staging.parent.resolve() == expected_parent.resolve()):
        shutil.rmtree(staging)
