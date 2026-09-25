"""Preview and build multi-language Surviving Mars Lua delivery folders."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Any

from scripts.core import surviving_mars_csv
from scripts.core.services import mars_translation_package as package
from scripts.core.services import mars_lua_discovery
from scripts.core.mars_pipeline.overlay import OverlayProfileError, compile_overlay
from scripts.core.mars_pipeline.delivery_metadata import (
    DeliveryMetadataError, _append_loc_items, _append_metadata_loctables, _overlay_metadata_items,
    _remove_source_publication_ids, _text_only_metadata_items,
    _rewrite_owned_lua_namespace, _source_copy_mod_id,
)
from scripts.core.mars_pipeline.publication_metadata import (
    PublicationMetadataError, prepare_source_copy_publication,
)
from scripts.core.mars_pipeline.delivery_identity import apply_publication_binding

MAX_FILES = 20_000
MAX_SOURCE_FILE_BYTES = 128 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 512 * 1024 * 1024
MAX_TRANSLATED_IDS = 10_000
OUTPUT_SUBDIR = "Localization"

class MarsDeliveryError(ValueError):
    """Raised for unsafe, stale, incomplete, or unsupported delivery inputs."""

def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )

def _source_root(path: Path) -> Path:
    if _is_reparse(path) or not path.is_dir():
        raise MarsDeliveryError("Source Mod must be an existing, non-linked directory.")
    return path.resolve(strict=True)

def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for part in relative.parts:
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(char in part for char in '<>:"|?*')
                or part.split(".", 1)[0].upper() in reserved):
            raise MarsDeliveryError(f"Unsafe source path: {relative}")
    return PurePosixPath(*relative.parts).as_posix()

def _safe_output_relative(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise MarsDeliveryError(f"Unsafe generated output path: {value!r}")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for part in path.parts:
        if (part.endswith((".", " ")) or any(char in part for char in '<>:"|?*\\')
                or part.split(".", 1)[0].upper() in reserved):
            raise MarsDeliveryError(f"Unsafe generated output path: {value!r}")
    return path.parts

def _tree_files(root: Path) -> list[tuple[str, Path, int, str]]:
    files: list[tuple[str, Path, int, str]] = []
    total = 0
    for directory, names, names_files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            if _is_reparse(base / name):
                raise MarsDeliveryError(f"Linked source directory is unsupported: {name}")
        names[:] = sorted(names)
        for name in sorted(names_files):
            path = base / name
            if _is_reparse(path) or not path.is_file():
                raise MarsDeliveryError(f"Linked or non-regular source file is unsupported: {path.name}")
            relative = _safe_relative(path, root)
            size = path.stat().st_size
            if size > MAX_SOURCE_FILE_BYTES:
                raise MarsDeliveryError(f"Source file exceeds size limit: {relative}")
            with path.open("rb") as stream:
                raw = stream.read(MAX_SOURCE_FILE_BYTES + 1)
            if len(raw) != size or len(raw) > MAX_SOURCE_FILE_BYTES:
                raise MarsDeliveryError(f"Source file changed or grew while reading: {relative}")
            digest = hashlib.sha256(raw).hexdigest()
            total += size
            if total > MAX_SOURCE_TOTAL_BYTES:
                raise MarsDeliveryError("Source Mod exceeds the total size limit.")
            files.append((relative, path, size, digest))
            if len(files) > MAX_FILES:
                raise MarsDeliveryError("Source Mod file count exceeds the limit.")
    return files

def _verify_manifest(source_files: list[tuple[str, Path, int, str]], manifest: dict[str, Any]) -> str:
    expected = manifest.get("source_files")
    if not isinstance(expected, dict):
        raise MarsDeliveryError("Manifest does not contain source file hashes.")
    actual = {relative: digest for relative, _, _, digest in source_files}
    if actual != expected:
        raise MarsDeliveryError("Source Mod changed after localization preparation; scan it again.")
    computed = hashlib.sha256("\n".join(
        f"{path}\0{actual[path]}" for path in sorted(actual)
    ).encode("utf-8")).hexdigest()
    if manifest.get("source_fingerprint") != computed:
        raise MarsDeliveryError("Manifest source fingerprint does not match its file hash list.")
    return computed

def _manifest_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = manifest.get("entries")
    if isinstance(raw, dict):
        result = {str(key): row for key, row in raw.items() if isinstance(row, dict)}
    elif isinstance(raw, list):
        result = {str(row["id"]): row for row in raw if isinstance(row, dict) and "id" in row}
    else:
        raise MarsDeliveryError("Manifest entries are missing or malformed.")
    if len(result) > MAX_TRANSLATED_IDS:
        raise MarsDeliveryError("Manifest has too many localization entries.")
    for key, row in result.items():
        if not key.isascii() or not key.isdecimal() or str(row.get("id", key)) != key:
            raise MarsDeliveryError(f"Invalid stable numeric localization ID: {key!r}")
        if not isinstance(row.get("text", row.get("source")), str):
            raise MarsDeliveryError(f"Source English text is missing for ID {key}.")
    return result

def _language_tables(
    translations: dict[str, dict[str, str]], entries: dict[str, dict[str, Any]], selected_ids: set[str]
) -> dict[str, dict[str, str]]:
    if not isinstance(translations, dict) or not translations:
        raise MarsDeliveryError("At least one target language is required.")
    result: dict[str, dict[str, str]] = {}
    used_names: set[str] = set()
    for code, values in translations.items():
        game_language = package._language(code)
        if game_language.casefold() in used_names:
            raise MarsDeliveryError(f"Two language codes map to the same game language: {game_language}.")
        used_names.add(game_language.casefold())
        if not isinstance(values, dict):
            raise MarsDeliveryError(f"Translations for {code} must be an ID-to-text mapping.")
        if not selected_ids.issubset(values) or not set(values).issubset(entries):
            missing = sorted(selected_ids - set(values), key=int)
            extra = sorted(set(values) - set(entries))
            raise MarsDeliveryError(f"Translations for {code} differ from selected IDs; missing={missing[:5]}, extra={extra[:5]}.")
        normalized: dict[str, str] = {}
        for key in sorted(selected_ids, key=int):
            translated = values[key]
            english = entries[key].get("text", entries[key].get("source"))
            if not isinstance(translated, str) or not translated.strip():
                raise MarsDeliveryError(f"Missing translation for ID {key} in {code}.")
            if surviving_mars_csv.compare_newlines(english, translated).is_mismatch:
                raise MarsDeliveryError(f"Paragraph break mismatch for ID {key} in {code}.")
            tags = surviving_mars_csv.compare_tags(english, translated)
            if tags.is_mismatch:
                raise MarsDeliveryError(f"Tag mismatch for ID {key} in {code}: missing={list(tags.missing)}, unexpected={list(tags.unexpected)}.")
            normalized[key] = translated
        result[code] = normalized
    return result

def _entry_rows(entries: dict[str, dict[str, Any]], translations: dict[str, str], ids: set[str]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(surviving_mars_csv.HEADER)
    for key in sorted(ids, key=int):
        row = entries[key]
        refs = row.get("refs", row.get("source_refs", []))
        context = "; ".join(
            f"{ref.get('path')}:{ref.get('line')}" for ref in refs if isinstance(ref, dict)
        )
        writer.writerow([key, row.get("text", row.get("source")), translations[key], "", context])
    rendered = output.getvalue()
    surviving_mars_csv.parse_text(rendered)
    return rendered

def _optional_source_tables(source: Path) -> dict[str, Any]:
    try:
        return package._discover_source_tables(source)
    except ValueError as error:
        if "No recognized Surviving Mars localization CSVs were found in the source Mod" in str(error):
            return {}
        raise MarsDeliveryError(f"Source Mod localization CSVs could not be read safely: {error}") from error

def _copyable_rewrites(entries: dict[str, dict[str, Any]]) -> tuple[set[str], list[dict[str, str]]]:
    ids: set[str] = set()
    pending: list[dict[str, str]] = []
    for key, row in entries.items():
        rewrites = row.get("rewrites", [])
        if any(isinstance(item, dict) and item.get("replacement") for item in rewrites):
            ids.add(key)
        elif row.get("kind") == "existing_t":
            ids.add(key)
        else:
            pending.append({"id": key, "reason": str(row.get("review_reason") or "No approved source rewrite is available.")})
    return ids, pending

def _render_overlay_files(
    manifest: dict[str, Any], entries: dict[str, dict[str, Any]],
    translations: dict[str, dict[str, str]], source_id: str, source_root: Path,
) -> tuple[dict[str, bytes], dict[str, Any], list[dict[str, str]]]:
    compiled = compile_overlay(manifest, source_id, source_root)
    selected_ids = set(compiled["supported_ids"])
    language_names = {code: package._language(code) for code in translations}
    overlay_id = "RemisLua" + hashlib.sha256(
        f"{source_id}\0mars-overlay-v1".encode("utf-8")
    ).hexdigest()[:12]
    title = f"[Lua translations] {source_id}"
    language_tables = []
    files: dict[str, bytes] = {
        "Code/RemisOverlay.lua": compiled["lua"].encode("utf-8"),
    }
    for code, values in translations.items():
        filename = f"{OUTPUT_SUBDIR}/{language_names[code]}/RemisLua.csv"
        csv_text = _entry_rows(entries, values, selected_ids)
        files[filename] = csv_text.encode("utf-8")
        language_tables.append({"language": language_names[code], "filename": filename})
    try:
        meta, items = _overlay_metadata_items(overlay_id, source_id, title, language_tables)
    except DeliveryMetadataError as error:
        raise MarsDeliveryError(str(error)) from error
    files["metadata.lua"] = meta.encode("utf-8")
    files["items.lua"] = items.encode("utf-8")
    pending = [{"id": key, "reason": "No reviewed runtime overlay binding exists for this entry."}
               for key in compiled["uncovered_ids"]]
    return files, compiled, pending

def _render_text_only_files(
    entries: dict[str, dict[str, Any]], localized: dict[str, dict[str, str]],
    selected_ids: set[str], source_id: str, title: str,
) -> tuple[dict[str, bytes], str, set[str]]:
    selected = selected_ids & set(entries)
    if not selected:
        raise MarsDeliveryError("No approved existing_t manifest IDs are available for text-only delivery.")
    output_id = "RemisText" + hashlib.sha256(
        f"remis-text-only\0{source_id}".encode("utf-8")
    ).hexdigest()[:12]
    registrations: list[dict[str, str]] = []
    files: dict[str, bytes] = {}
    for code, values in localized.items():
        language = package._language(code)
        relative = f"{OUTPUT_SUBDIR}/{language}/RemisLua.csv"
        files[relative] = _entry_rows(entries, values, selected).encode("utf-8")
        registrations.append({"language": language, "path": relative})
    try:
        metadata, items = _text_only_metadata_items(
            output_id, source_id, f"[Remis text] {title}", registrations
        )
    except DeliveryMetadataError as error:
        raise MarsDeliveryError(str(error)) from error
    files["metadata.lua"] = metadata.encode("utf-8")
    files["items.lua"] = items.encode("utf-8")
    return files, output_id, selected

def _build_text_only_plan(
    source: Path, fingerprint: str, source_id: str, manifest: dict[str, Any],
    entries: dict[str, dict[str, Any]], translations: dict[str, dict[str, str]],
) -> dict[str, Any]:
    pending: list[dict[str, str]] = []
    approved_raw = manifest.get("approved_ids")
    approved = {str(value) for value in approved_raw} if isinstance(approved_raw, list) else set()
    if not isinstance(approved_raw, list):
        pending.append({"id": "", "reason": "No explicit text-only approved_ids snapshot is recorded."})
    eligible_ids = {key for key, row in entries.items() if row.get("kind") == "existing_t"}
    selected_ids = eligible_ids & approved
    if not selected_ids:
        pending.append({"id": "", "reason": "No approved existing_t manifest IDs are available."})
    localized = _language_tables(translations, entries, selected_ids)
    output_id = "RemisText" + hashlib.sha256(
        f"remis-text-only\0{source_id}".encode("utf-8")
    ).hexdigest()[:12]
    generated: dict[str, bytes] = {}
    if selected_ids:
        generated, output_id, selected_ids = _render_text_only_files(
            entries, localized, selected_ids, source_id,
            str(package.read_source_metadata(source).get("title") or source_id),
        )
    warnings = [{"id": key, "reason": "This hardcoded or unapproved entry is not covered by text-only delivery."}
                for key in sorted(set(entries) - selected_ids, key=int)]
    return {"mode": "text_only", "source_fingerprint": fingerprint, "source_id": source_id,
            "entries": entries, "selected_ids": selected_ids, "generated": generated,
            "pending": pending, "warnings": warnings,
            "complete": not pending, "profile": "text_only_existing_csv-v1",
            "runtime_verified": False, "mod_id": output_id}

def _build_overlay_plan(
    source: Path, source_files: list[tuple[str, Path, int, str]], fingerprint: str,
    source_id: str, manifest: dict[str, Any], entries: dict[str, dict[str, Any]],
    translations: dict[str, dict[str, str]],
) -> dict[str, Any]:
    try:
        compiled = compile_overlay(manifest, source_id, source)
    except OverlayProfileError as error:
        raise MarsDeliveryError(str(error)) from error
    selected_ids = set(compiled["supported_ids"])
    localized = _language_tables(translations, entries, selected_ids)
    generated, _, pending = _render_overlay_files(manifest, entries, localized, source_id, source)
    for code, values in localized.items():
        relative = f"{OUTPUT_SUBDIR}/{package._language(code)}/RemisLua.csv"
        generated[relative] = _entry_rows(entries, values, selected_ids).encode("utf-8")
    return {"mode": "overlay", "source_fingerprint": fingerprint, "source_id": source_id,
            "entries": entries, "selected_ids": selected_ids, "generated": generated,
            "source_files": source_files, "pending": pending, "complete": not pending,
            "warnings": [], "profile": compiled["profile"], "runtime_verified": False,
            "mod_id": "RemisLua" + hashlib.sha256(
                f"{source_id}\0mars-overlay-v1".encode("utf-8")
            ).hexdigest()[:12]}

def _build_plan(
    source: Path, manifest: dict[str, Any], translations: dict[str, dict[str, str]], mode: str,
    metadata_overrides: dict[str, Any] | None = None,
    publication_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_files = _tree_files(source)
    fingerprint = _verify_manifest(source_files, manifest)
    source_id = package.read_source_metadata(source).get("id", "").strip()
    if not source_id or source_id != manifest.get("mod_id"):
        raise MarsDeliveryError("Manifest Mod ID does not match source metadata.lua.")
    entries = _manifest_entries(manifest)
    has_metadata_overrides = any(value is not None for value in (metadata_overrides or {}).values())
    if publication_binding is not None and mode != "source_copy":
        raise MarsDeliveryError("Publication binding applies only to source-copy delivery.")
    if has_metadata_overrides and mode != "source_copy":
        raise MarsDeliveryError("Publication metadata overrides are available only for source-copy delivery.")
    if mode == "text_only":
        plan = _build_text_only_plan(source, fingerprint, source_id, manifest, entries, translations)
        plan["source_files"] = source_files
        return plan
    if mode == "overlay":
        return _build_overlay_plan(source, source_files, fingerprint, source_id,
                                   manifest, entries, translations)
    if mode != "source_copy":
        raise MarsDeliveryError("mode must be 'text_only', 'overlay', or 'source_copy'.")
    delivery_id = _source_copy_mod_id(source_id)
    rewrite_ids, pending = _copyable_rewrites(entries)
    approved_raw = manifest.get("approved_ids")
    if not isinstance(approved_raw, list):
        pending.extend({"id": key, "reason": "No explicit source-copy approved_ids snapshot is recorded."}
                       for key in sorted(rewrite_ids, key=int))
        rewrite_ids.clear()
    else:
        approved = {str(value) for value in approved_raw}
        unapproved = rewrite_ids - approved
        pending.extend({"id": key, "reason": "Source rewrite is not included in the manifest approved_ids snapshot."}
                       for key in sorted(unapproved, key=int))
        rewrite_ids.intersection_update(approved)
    localized = _language_tables(translations, entries, rewrite_ids)
    try:
        from scripts.core.mars_pipeline.prepare_source import rewrite_sources
    except ImportError as error:
        raise MarsDeliveryError("Source rewrite service is unavailable; source-copy delivery cannot run.") from error
    rewritten = rewrite_sources(source, manifest, approved_ids=rewrite_ids)
    generated: dict[str, bytes] = {}
    table_registrations: list[dict[str, str]] = []
    source_tables = _optional_source_tables(source)
    source_table_ids: set[str] = set()
    for _, (_, _, document) in source_tables.items():
        source_table_ids.update(entry.key for entry in document.entries)
    missing_table_ids = source_table_ids - rewrite_ids
    # Unmapped ModTexts rows can be inherited SDK text; omit them from the
    # added language table so the game's own keyed localization remains active.
    base_csv_ids = source_table_ids & rewrite_ids
    code_translation_ids = rewrite_ids - base_csv_ids
    for code, values in localized.items():
        language = package._language(code)
        for _, (source_path, _, source_doc) in sorted(source_tables.items()):
            relative = package._safe_relative_csv(source_path, source)
            rows = [list(row) for row in source_doc.rows[:source_doc.header_row_index + 1]]
            for row in source_doc.rows[source_doc.header_row_index + 1:]:
                if row:
                    key = row[0]
                    if key not in base_csv_ids:
                        continue
                    if key not in values:
                        raise MarsDeliveryError(f"Existing CSV ID {key} has no translation for {code}.")
                    translated_row = list(row)
                    manifest_text = entries[key].get("text", entries[key].get("source"))
                    if translated_row[1] != manifest_text:
                        raise MarsDeliveryError(f"Manifest English text differs for existing CSV ID {key}.")
                    translated_row[2] = values[key]
                    rows.append(translated_row)
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator=source_doc.line_ending)
            writer.writerows(rows)
            relative_target = f"{OUTPUT_SUBDIR}/{language}/{relative}"
            generated[relative_target] = output.getvalue().encode("utf-8")
            table_registrations.append({"language": language, "path": relative_target})
        relative = f"{OUTPUT_SUBDIR}/{package._language(code)}/RemisLua.csv"
        generated[relative] = _entry_rows(entries, values, code_translation_ids).encode("utf-8")
        table_registrations.append({"language": language, "path": relative})
    try:
        _rewrite_owned_lua_namespace(source_files, rewritten, source_id, delivery_id)
        original_items = (source / "items.lua").read_bytes()
        original_items = rewritten.get("items.lua", original_items)
        rewritten["items.lua"] = _append_loc_items(original_items, delivery_id, table_registrations)
        original_metadata = rewritten.get("metadata.lua", (source / "metadata.lua").read_bytes())
        original_metadata = _remove_source_publication_ids(original_metadata)
        original_metadata, cover_files = prepare_source_copy_publication(
            original_metadata, source_files, delivery_id, metadata_overrides
        )
        original_metadata = apply_publication_binding(
            original_metadata, publication_binding, source_id, delivery_id)
        rewritten.update(cover_files)
        rewritten["metadata.lua"] = _append_metadata_loctables(original_metadata, delivery_id, table_registrations)
    except (DeliveryMetadataError, PublicationMetadataError) as error:
        raise MarsDeliveryError(str(error)) from error
    rewritten.update(generated)
    return {"mode": mode, "source_fingerprint": fingerprint, "source_id": source_id,
            "entries": entries, "selected_ids": rewrite_ids, "generated": rewritten,
            "source_files": source_files, "pending": pending, "complete": not pending,
            "excluded_source_csv_ids": sorted(missing_table_ids, key=int),
            "profile": "full_source_copy-v1", "runtime_verified": False,
            "mod_id": delivery_id}

def inspect_delivery(
    source_root: Path, manifest: dict[str, Any], translations_by_language: dict[str, dict[str, str]],
    mode: str, *, metadata_overrides: dict[str, Any] | None = None,
    publication_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a no-write delivery preview, including explicit unhandled entries."""
    source = _source_root(Path(source_root))
    plan = _build_plan(source, manifest, translations_by_language, mode, metadata_overrides, publication_binding)
    file_facts = []
    for relative, content in sorted(plan["generated"].items()):
        _safe_output_relative(relative)
        if not isinstance(content, bytes):
            raise MarsDeliveryError(f"Generated file is not bytes: {relative}")
        file_facts.append({"path": relative, "size_bytes": len(content),
                           "sha256": hashlib.sha256(content).hexdigest()})
    if mode == "source_copy":
        rewritten_paths = set(plan["generated"])
        file_facts = [
            {"path": relative, "size_bytes": size if relative not in rewritten_paths else len(plan["generated"][relative]),
             "sha256": digest if relative not in rewritten_paths else hashlib.sha256(plan["generated"][relative]).hexdigest()}
            for relative, _, size, digest in plan["source_files"] if relative != ".remis_project.json"
        ] + [item for item in file_facts if item["path"] not in {row[0] for row in plan["source_files"]}]
    total = sum(item["size_bytes"] for item in file_facts)
    fingerprint_data = {"mode": mode, "source": plan["source_fingerprint"],
                        "files": file_facts, "languages": sorted(translations_by_language),
                        "pending": plan["pending"], "profile": plan["profile"]}
    if publication_binding is not None:
        fingerprint_data["publication_binding"] = publication_binding
    output_fingerprint = hashlib.sha256(json.dumps(
        fingerprint_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "mode": mode,
        "status": "ready" if plan["complete"] else "blocked",
        "source_mod_id": plan["source_id"],
        "output_mod_id": plan["mod_id"],
        "source_fingerprint": plan["source_fingerprint"],
        "fingerprint": output_fingerprint,
        "profile": plan["profile"],
        "localized_entry_count": len(plan["selected_ids"]),
        "languages": [{"code": code, "game_language": package._language(code),
                       "entry_count": len(plan["selected_ids"])}
                      for code in sorted(translations_by_language)],
        "pending_items": plan["pending"],
        "blockers": plan["pending"],
        "warnings": plan.get("warnings", []),
        "uncovered_entry_count": len(plan.get("warnings", [])),
        "excluded_source_csv_ids": plan.get("excluded_source_csv_ids", []),
        "files": file_facts,
        "file_count": len(file_facts),
        "total_size_bytes": total,
        "runtime_verified": False,
        "installation_steps": ([
            f"Keep original Mod {plan['source_id']} enabled; this overlay requires it.",
            "Install and enable this separate overlay alongside the original Mod.",
            "Runtime behavior and save-instance refresh are not verified.",
        ] if mode == "overlay" else [
            f"Keep original Mod {plan['source_id']} enabled; this translation Mod depends on it.",
            f"Install and enable translation Mod {plan['mod_id']} alongside the original.",
            f"Text-only delivery covers {len(plan['selected_ids'])} existing keyed strings; hardcoded Lua text remains English.",
            "Runtime behavior is not verified.",
        ] if mode == "text_only" else [
            f"Disable the Workshop copy of Mod {plan['source_id']} before enabling source copy {plan['mod_id']}.",
            f"The copy has a distinct Mod ID ({plan['mod_id']}) to avoid the Workshop selection collision.",
            "Existing saves may treat the copy as a different Mod; save migration and runtime behavior are not verified.",
        ]),
    }

def _assert_destination(destination: Path, source: Path) -> None:
    absolute = Path(os.path.abspath(destination))
    try:
        absolute.resolve(strict=False).relative_to(source.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise MarsDeliveryError("Delivery destination cannot be inside the source Mod.")
    cursor = absolute.parent
    while cursor != cursor.parent:
        if _is_reparse(cursor):
            raise MarsDeliveryError("Delivery destination cannot pass through a link or junction.")
        cursor = cursor.parent

def build_delivery(
    source_root: Path, manifest: dict[str, Any], translations_by_language: dict[str, dict[str, str]],
    destination_root: Path, mode: str, *, expected_fingerprint: str | None = None,
    metadata_overrides: dict[str, Any] | None = None,
    publication_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically build a new delivery directory and refuse overwrite."""
    source = _source_root(Path(source_root))
    destination = Path(os.path.abspath(destination_root))
    _assert_destination(destination, source)
    preview = inspect_delivery(source, manifest, translations_by_language, mode,
                               metadata_overrides=metadata_overrides, publication_binding=publication_binding)
    if expected_fingerprint and preview["fingerprint"] != expected_fingerprint:
        raise MarsDeliveryError("Delivery inputs changed after preview; inspect them again.")
    if preview["status"] != "ready":
        raise MarsDeliveryError("Delivery has unresolved blockers; finish review before building.")
    plan = _build_plan(source, manifest, translations_by_language, mode, metadata_overrides, publication_binding)
    if destination.exists() or _is_reparse(destination):
        raise FileExistsError(f"Delivery destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _is_reparse(destination.parent):
        raise MarsDeliveryError("Delivery destination parent cannot be a link or junction.")
    temp_root = Path(tempfile.mkdtemp(prefix=".mars-delivery-", dir=destination.parent))
    try:
        if mode == "source_copy":
            for relative, path, size, digest in plan["source_files"]:
                if relative == ".remis_project.json":
                    continue
                parts = _safe_output_relative(relative)
                target = temp_root.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                if _is_reparse(target.parent):
                    raise MarsDeliveryError("Delivery contains a linked output path.")
                with path.open("rb") as stream:
                    raw = stream.read(MAX_SOURCE_FILE_BYTES + 1)
                if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                    raise MarsDeliveryError(f"Source changed during copy: {relative}")
                with target.open("xb") as handle:
                    handle.write(raw)
            for relative, raw in plan["generated"].items():
                target = temp_root.joinpath(*_safe_output_relative(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                if _is_reparse(target.parent):
                    raise MarsDeliveryError("Delivery contains a linked output path.")
                with target.open("wb") as handle:
                    handle.write(raw)
        else:
            for relative, raw in plan["generated"].items():
                target = temp_root.joinpath(*_safe_output_relative(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle:
                    handle.write(raw)
        for item in preview["files"]:
            target = temp_root.joinpath(*PurePosixPath(item["path"]).parts)
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
                # Full source-copy input files are checked during copy below; changed generated files fail here.
                if item["path"] in plan["generated"]:
                    raise MarsDeliveryError(f"Delivery output verification failed: {item['path']}")
        os.rename(temp_root, destination)
    except Exception:
        if temp_root.exists() and not _is_reparse(temp_root) and temp_root.resolve().parent == destination.parent.resolve():
            shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return {
        "package_path": str(destination),
        "mode": mode,
        "output_mod_id": preview["output_mod_id"],
        "publication_binding": publication_binding,
        "file_count": preview["file_count"],
        "size_bytes": preview["total_size_bytes"],
        "fingerprint": preview["fingerprint"],
        "source_fingerprint": preview["source_fingerprint"],
        "pending_items": preview["pending_items"],
        "warnings": preview.get("warnings", []),
        "runtime_verified": False,
        "installation_steps": preview["installation_steps"],
        "manifest_receipt": {"schema_version": manifest.get("schema_version"),
                              "mod_id": plan["mod_id"],
                              "source_fingerprint": plan["source_fingerprint"],
                              "localized_ids": sorted(plan["selected_ids"], key=int),
                              "languages": sorted(translations_by_language)},
    }
