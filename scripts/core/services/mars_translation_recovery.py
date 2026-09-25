"""Approval-gated recovery of archived Surviving Mars translations."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any

from scripts.app_settings import DEST_DIR, LANGUAGES
from scripts.core import surviving_mars_csv
from scripts.core.agent_service import agent_registry
from scripts.core.archive_manager import archive_manager
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services.game_language_policy import supported_language_codes
from scripts.shared.services import project_manager


class RecoveryError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


PLAN_KIND = "mars_archived_translation_recovery"


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _assert_plain_tree(path: Path) -> None:
    for candidate in (path, *path.parents):
        if _is_reparse(candidate):
            raise RecoveryError(403, "redirected_path", "Recovery paths cannot pass through links or junctions.")


def _source_fingerprint(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.name == ".remis_project.json":
            continue
        if _is_reparse(path):
            raise RecoveryError(409, "source_redirected", "The project source contains a link or junction.")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{relative}\0{digest}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _source_table(root: Path) -> tuple[Path, bytes, surviving_mars_csv.CsvDocument]:
    candidates = [path for path in root.rglob("*.csv") if surviving_mars_csv.is_table_file(path)]
    if len(candidates) != 1:
        raise RecoveryError(409, "source_table_ambiguous", "Recovery requires exactly one source ModItemLocTable CSV.")
    path = candidates[0]
    _assert_plain_tree(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        document = surviving_mars_csv.parse_text(text)
    except (UnicodeDecodeError, surviving_mars_csv.SurvivingMarsCsvError) as exc:
        raise RecoveryError(409, "source_table_invalid", "The source localization CSV is not a valid UTF-8 ModItemLocTable.") from exc
    if not document.entries:
        raise RecoveryError(409, "source_table_empty", "The source localization CSV has no entries to recover.")
    return path, raw, document


def _archive_for_language(project_id: str, source_file: Path, document: Any, language: str) -> dict[str, Any]:
    version = archive_manager.get_latest_version(project_id=project_id, language=language)
    if not version:
        raise RecoveryError(409, "archive_language_missing", f"No archived translation is available for {language}.")
    records = archive_manager.get_entries(project_id=project_id, file_path=str(source_file), language=language)
    source_by_key = {entry.key: entry.value for entry in document.entries}
    translated: dict[str, str] = {}
    for record in records:
        key = str(record.get("key", ""))
        if key in translated or key not in source_by_key:
            raise RecoveryError(409, "archive_keys_mismatch", f"Archived {language} keys do not match the project source table.")
        if record.get("original") != source_by_key[key]:
            raise RecoveryError(409, "archive_source_mismatch", f"Archived source text changed for {language} key {key}.")
        value = record.get("translation")
        if not isinstance(value, str) or not value.strip():
            raise RecoveryError(409, "archive_translation_missing", f"Archived {language} translation is empty for key {key}.")
        translated[key] = value
    if set(translated) != set(source_by_key):
        raise RecoveryError(409, "archive_keys_mismatch", f"Archived {language} entries are incomplete for this source table.")
    diagnostics = []
    for entry in document.entries:
        value = translated[entry.key]
        tags = surviving_mars_csv.compare_tags(entry.value, value)
        newlines = surviving_mars_csv.compare_newlines(entry.value, value)
        if tags.is_mismatch:
            diagnostics.append({"code": "tag_mismatch", "id": entry.key,
                                "missing": list(tags.missing), "unexpected": list(tags.unexpected)})
        if newlines.is_mismatch:
            diagnostics.append({"code": "newline_mismatch", "id": entry.key,
                                "source_runs": list(newlines.source_runs),
                                "translation_runs": list(newlines.translation_runs),
                                "escaped_newlines": newlines.unexpected_escaped})
    archive_facts = {"language": language, "version_id": version["id"],
                     "entries": [[key, source_by_key[key], translated[key]] for key in sorted(translated)]}
    digest = hashlib.sha256(json.dumps(archive_facts, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"version_id": version["id"], "translations": translated,
            "archive_fingerprint": digest, "diagnostics": diagnostics}


def _read_snapshot(project: dict, languages: tuple[str, ...]) -> dict[str, Any]:
    original_root = Path(project["source_path"]).absolute()
    _assert_plain_tree(original_root)
    root = original_root.resolve(strict=True)
    if not root.is_dir():
        raise RecoveryError(409, "source_missing", "The project source folder is unavailable.")
    _assert_plain_tree(root)
    source_file, raw, document = _source_table(root)
    archives = {language: _archive_for_language(project["project_id"], source_file, document, language)
                for language in languages}
    combined = hashlib.sha256(json.dumps(
        {language: {"version_id": archives[language]["version_id"],
                   "fingerprint": archives[language]["archive_fingerprint"]}
         for language in languages}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {"root": root, "source_file": source_file, "raw": raw, "document": document,
            "source_fingerprint": _source_fingerprint(root), "archives": archives,
            "archive_fingerprint": combined}


def _output_root() -> Path:
    original_root = Path(DEST_DIR).absolute()
    _assert_plain_tree(original_root)
    root = original_root.resolve()
    if not root.is_dir():
        raise RecoveryError(409, "output_root_missing", "The Remis translation output folder is unavailable.")
    _assert_plain_tree(root)
    return root


def _output_name(language: str, source_name: str) -> str:
    target = next((value for value in LANGUAGES.values() if value.get("code") == language), None)
    if target is None:
        raise RecoveryError(400, "unsupported_language", "The selected language is not in the configured language catalog.")
    from scripts.core.services.initial_translation_run_service import language_output_folder_name
    return language_output_folder_name(source_name, target)


async def _project(project_id: str) -> dict:
    project = await project_manager.get_project(project_id)
    if not project:
        raise RecoveryError(404, "project_not_found", "Project not found.")
    if project.get("game_id") != "surviving_mars":
        raise RecoveryError(409, "unsupported_game", "Archive recovery supports only Surviving Mars CSV projects.")
    return project


def _inspect(project: dict, languages: tuple[str, ...]) -> dict[str, Any]:
    snapshot = _read_snapshot(project, languages)
    output_root = _output_root()
    outputs = []
    for language in languages:
        name = _output_name(language, snapshot["root"].name)
        destination = output_root / name
        _assert_plain_tree(destination)
        if destination.exists():
            raise RecoveryError(409, "output_exists", f"Refusing to overwrite existing recovery output {name}.")
        archive = snapshot["archives"][language]
        outputs.append({"language": language, "output_folder_name": name,
                        "output_path": str(destination),
                        "entry_count": len(archive["translations"]),
                        "archive_version_id": archive["version_id"],
                        "validation_diagnostics": archive["diagnostics"]})
    return {"snapshot": snapshot, "inspection": {
        "project_id": project["project_id"], "source_file": snapshot["source_file"].relative_to(snapshot["root"]).as_posix(),
        "source_sha256": hashlib.sha256(snapshot["raw"]).hexdigest(),
        "source_fingerprint": snapshot["source_fingerprint"],
        "archive_fingerprint": snapshot["archive_fingerprint"],
        "outputs": outputs, "runtime_verified": False,
    }}


async def plan_recovery(project_id: str, languages: list[str]) -> dict[str, Any]:
    project = await _project(project_id)
    normalized = tuple(languages)
    allowed = set(supported_language_codes(project["game_id"]))
    if not normalized or len(normalized) > 9 or len(set(normalized)) != len(normalized):
        raise RecoveryError(400, "language_selection_invalid", "Select one to nine unique language codes.")
    if set(normalized) - allowed:
        raise RecoveryError(400, "unsupported_language", "One or more selected languages are not supported by this game.")
    result = await asyncio.to_thread(_inspect, project, normalized)
    inspection = result["inspection"]
    record = agent_registry.create_plan(
        project_id=project_id, kind=PLAN_KIND, dry_run=False,
        execution_args={"languages": list(normalized), "source_path": str(Path(project["source_path"]).resolve()),
                        "source_file": inspection["source_file"], "source_sha256": inspection["source_sha256"],
                        "source_fingerprint": inspection["source_fingerprint"],
                        "archive_fingerprint": inspection["archive_fingerprint"],
                        "outputs": [item["output_folder_name"] for item in inspection["outputs"]]},
        inspection=inspection,
        summary="Restore archived French and German CSV translations into separate project outputs without model calls.",
    )
    return {**inspection, "plan_id": record["plan_id"], "expires_at": record["expires_at"],
            "requires_approval": True, "risk": {"may_use_paid_api": False, "writes_output": True,
            "overwrites_existing_output": False, "installs_to_game_directory": False},
            "allowed_actions": ["approve_archive_recovery"]}


def _render(snapshot: dict[str, Any], language: str) -> bytes:
    document = snapshot["document"]
    values = [snapshot["archives"][language]["translations"][entry.key] for entry in document.entries]
    key_map = {index: {"key_part": entry.key, "row_index": entry.row_index}
               for index, entry in enumerate(document.entries)}
    text = surviving_mars_csv.rewrite_text(document.source_text, values, key_map)
    prefix = b"\xef\xbb\xbf" if snapshot["raw"].startswith(b"\xef\xbb\xbf") else b""
    return prefix + text.encode("utf-8")


def _restore_sidecar(source_root: Path, original_dirs: list[str]) -> None:
    manager = ProjectJsonManager(str(source_root))
    manager.update_config({"translation_dirs": original_dirs})


async def _publish(staged: dict[str, Path], destinations: dict[str, Path], languages: tuple[str, ...],
                   project_id: str, source_root: Path, original_dirs: list[str]) -> dict[str, Any]:
    created: list[Path] = []
    try:
        for language in languages:
            destinations[language].mkdir()
            created.append(destinations[language])
            for item in staged[language].iterdir():
                os.replace(item, destinations[language] / item.name)
        for language in languages:
            await project_manager.add_translation_path(project_id, str(destinations[language]))
        index = await project_manager.refresh_project_files(project_id)
        return {"created": created, "index": index}
    except Exception:
        _restore_sidecar(source_root, original_dirs)
        for path in reversed(created):
            if path.exists() and not _is_reparse(path):
                shutil.rmtree(path)
        try:
            await project_manager.refresh_project_files(project_id)
        except Exception:
            pass
        raise


async def execute_recovery(project_id: str, plan_id: str, approved: bool) -> dict[str, Any]:
    if not approved:
        raise RecoveryError(409, "approval_required", "Approve the reviewed archive recovery plan before writing outputs.")
    try:
        record = agent_registry.consume_plan(plan_id, approved=True)
    except KeyError as exc:
        raise RecoveryError(404, "plan_not_found", "Archive recovery plan not found.") from exc
    except (TimeoutError, RuntimeError) as exc:
        raise RecoveryError(409, "stale_plan", "The plan expired or was already used. Create a fresh preview.") from exc
    try:
        if record.get("kind") != PLAN_KIND or record.get("project_id") != project_id:
            raise RecoveryError(409, "invalid_plan", "This recovery plan belongs to a different workflow or project.")
        request = record["execution_args"]
        project = await _project(project_id)
        if str(Path(project["source_path"]).resolve()) != request["source_path"]:
            raise RecoveryError(409, "stale_source", "The project source path changed after preview.")
        inspected = await asyncio.to_thread(_inspect, project, tuple(request["languages"]))
        inspection = inspected["inspection"]
        for field in ("source_file", "source_sha256", "source_fingerprint", "archive_fingerprint"):
            if inspection[field] != request[field]:
                raise RecoveryError(409, "stale_snapshot", "The source or archived translations changed after preview.")
        snapshot = inspected["snapshot"]
        output_root = _output_root()
        source_name = Path(request["source_path"]).name
        destinations = {language: output_root / _output_name(language, source_name)
                        for language in request["languages"]}
        if any(path.exists() for path in destinations.values()):
            raise RecoveryError(409, "output_exists", "A recovery output now exists; nothing was overwritten.")
        project_config = ProjectJsonManager(request["source_path"]).get_config()
        original_dirs = list(project_config.get("translation_dirs", []))
        created: list[Path] = []
        with tempfile.TemporaryDirectory(prefix=".mars-archive-recovery-", dir=output_root) as temp_name:
            staging = Path(temp_name)
            staged: dict[str, Path] = {}
            output_facts = []
            for language in request["languages"]:
                folder = staging / _output_name(language, source_name)
                folder.mkdir(parents=True)
                content = _render(snapshot, language)
                relative = Path(request["source_file"])
                output_file = folder / relative
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(content)
                staged[language] = folder
                output_facts.append({"language": language, "output_folder_name": folder.name,
                                     "output_path": str(destinations[language] / relative),
                                     "entry_count": len(snapshot["archives"][language]["translations"]),
                                     "sha256": hashlib.sha256(content).hexdigest(),
                                     "validation_diagnostics": snapshot["archives"][language]["diagnostics"]})
            published = await _publish(staged, destinations, tuple(request["languages"]), project_id,
                                       Path(request["source_path"]), original_dirs)
            created, index = published["created"], published["index"]
        files = await project_manager.get_project_files(project_id)
        file_records = [{"file_id": item.get("file_id"), "file_path": item.get("file_path"),
                         "file_type": item.get("file_type")}
                        for item in files if item.get("file_type") == "translation"
                        and any(Path(str(item.get("file_path", ""))).is_relative_to(path) for path in created)]
        agent_registry.record_event("mars_archived_translation_recovered", project_id=project_id,
                                    plan_id=plan_id, languages=request["languages"],
                                    output_paths=[str(path) for path in created])
        return {"status": "recovered", "project_id": project_id, "plan_id": plan_id,
                "outputs": output_facts, "registered_files": file_records,
                "runtime_verified": False, "allowed_actions": ["inspect_validation", "proofread"]}
    except Exception:
        agent_registry.release_plan(plan_id)
        raise
