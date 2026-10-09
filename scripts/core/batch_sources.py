"""Freeze registered project resources using the existing game adapters."""
from pathlib import Path, PurePosixPath

from scripts.core.batch_artifacts import digest_file, fingerprint
from scripts.core.batch_repository import BatchConflict
from scripts.core.game_adapters.registry import get_adapter


def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("..", ".") or ":" in part for part in path.parts):
        raise BatchConflict("unsafe_resource_path", "Resource paths must remain inside the output package.")
    return path.as_posix()


def language_configuration(locale, slot=None):
    from scripts.app_settings import LANGUAGES
    from scripts.schemas.common import LanguageCode
    try:
        actual = LanguageCode.from_str(locale).value
    except ValueError as exc:
        raise BatchConflict("unsupported_locale", "Select a supported content locale.", 400) from exc
    if actual == "custom":
        raise BatchConflict("ambiguous_locale", "A batch requires an explicit content locale.", 400)
    existing = next((dict(item) for item in LANGUAGES.values() if item.get("code") == actual), None)
    if existing:
        return existing
    if actual == "zh-TW":
        if slot not in ("Schinese", "l_simp_chinese", "simp_chinese"):
            raise BatchConflict("engine_slot_required", "zh-TW requires an explicit Chinese engine loading slot.", 400)
        config = next(dict(item) for item in LANGUAGES.values() if item.get("code") == "zh-CN")
        config.update(code="zh-TW", name="正體中文", name_en="Traditional Chinese (Taiwan usage)")
        return config
    raise BatchConflict("unsupported_locale", "No rendering profile exists for this content locale.", 400)


async def freeze_sources(manager, request):
    from scripts.app_settings import GAME_PROFILES_BY_ID
    project = await manager.get_project(request.project_id)
    if not project:
        raise BatchConflict("project_not_found", "Project not found.", 404)
    profile = GAME_PROFILES_BY_ID.get(project["game_id"])
    if not profile:
        raise BatchConflict("game_not_supported", "No game adapter is available.", 400)
    root = Path(project["source_path"]).resolve(strict=True)
    source_lang = language_configuration(project.get("source_language", "en"))
    adapter = get_adapter(profile)
    registered = [item for item in await manager.get_project_files(request.project_id) if item.get("file_type", "source") == "source"]
    requested = set(request.file_ids)
    if len(requested) != len(request.file_ids) or not requested.issubset({item["file_id"] for item in registered}):
        raise BatchConflict("invalid_source_selection", "Select unique registered source file IDs.", 400)
    files = []
    for item in sorted(registered, key=lambda row: row["file_path"]):
        path = Path(item["file_path"]).resolve(strict=True)
        if not path.is_relative_to(root) or path.stat().st_size > 128 * 1024 * 1024:
            raise BatchConflict("source_path_blocked", "Registered source is outside the source root or exceeds bounds.")
        before = digest_file(path)
        metadata = {"source_root": str(root), "source_language": source_lang}
        document = adapter.parse(path, metadata)
        relative = safe_relative(path.relative_to(root).as_posix())
        translations, contexts = {}, {}
        if adapter.id == "surviving_mars_csv":
            from scripts.core import surviving_mars_csv
            csv_doc = surviving_mars_csv.parse_text(document.source_text)
            contexts = {row[0]: row[4] for row in csv_doc.rows[csv_doc.header_row_index + 1:] if row}
            if request.source_column == "Translation":
                translations = {row[0]: row[2] for row in csv_doc.rows[csv_doc.header_row_index + 1:] if row}
        elif request.source_column != "Text":
            raise BatchConflict("unsupported_source_column", "Translation source column is only supported for Mars CSV.", 400)
        entries = []
        for entry in document.entries:
            value = translations.get(entry.key, entry.value)
            if request.source_column == "Translation" and not value.strip():
                raise BatchConflict("source_translation_missing", "The selected source-language column has an empty eligible value.")
            entries.append({"id": "e_" + fingerprint([relative, entry.key])[:24], "key": entry.key,
                            "source": value, "original_text": entry.value,
                            "context": f"{relative}:{entry.line_number} {contexts.get(entry.key, '')}"})
        if len({entry["key"] for entry in entries}) != len(entries):
            raise BatchConflict("duplicate_source_key", "Source keys must be unique within each file.")
        if digest_file(path) != before:
            raise BatchConflict("source_revision_conflict", "Source changed while the plan was created.")
        files.append({"file_id": item["file_id"], "relative_path": relative, "path": str(path),
                      "sha256": before, "content": document.source_text, "entries": entries,
                      "selected": item["file_id"] in requested})
    selected = [entry for item in files if item["selected"] for entry in item["entries"]]
    if not selected or len(selected) > 500000 or len({entry["id"] for entry in selected}) != len(selected):
        raise BatchConflict("source_entries_blocked", "No eligible entries, excessive scope, or duplicate entry identity.")
    return {"project_id": request.project_id, "project_name": project["name"], "game_id": project["game_id"],
            "source_root": str(root), "source_locale": source_lang["code"], "source_language": source_lang,
            "adapter_id": adapter.id, "source_column": request.source_column, "files": files}


async def require_current_sources(manager, snapshot):
    project = await manager.get_project(snapshot["project_id"])
    if not project or project.get("game_id") != snapshot["game_id"] or Path(project["source_path"]).resolve() != Path(snapshot["source_root"]):
        raise BatchConflict("source_revision_conflict", "Project source identity changed.")
    if project.get("source_language", "en") != snapshot["source_locale"]:
        raise BatchConflict("source_revision_conflict", "Project source language changed.")
    current = {row["file_id"]: row for row in await manager.get_project_files(snapshot["project_id"]) if row.get("file_type", "source") == "source"}
    if set(current) != {row["file_id"] for row in snapshot["files"]}:
        raise BatchConflict("source_revision_conflict", "The registered source file set changed.")
    for item in snapshot["files"]:
        path = Path(current[item["file_id"]]["file_path"]).resolve()
        if str(path) != item["path"] or not path.is_file() or digest_file(path) != item["sha256"]:
            raise BatchConflict("source_revision_conflict", "A source resource changed while the batch waited.")
