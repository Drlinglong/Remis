"""Read-only incremental preview for Agent API consumers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.app_settings import GAME_PROFILES, GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
from scripts.core.services.incremental_archive_service import IncrementalArchiveService
from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_preparation_service import _prepare_file_entries
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.game_language_policy import validate_target_language_codes
from scripts.core.services.incremental_source_paths import checked_source_path, source_root


def _source_language(project: dict[str, Any]) -> dict[str, Any]:
    code = project.get("source_language")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Project has no configured source language")
    normalized = code.strip()
    language = LANGUAGE_BY_CODE.get(normalized)
    if language is None:
        language = next(
            (item for item in LANGUAGE_BY_CODE.values()
             if item.get("name_en", "").casefold() == normalized.casefold()),
            None,
        )
    if language is None:
        raise ValueError(f"Unsupported project source language: {normalized}")
    return language


def _fingerprint(
    source_files: list[dict[str, Any]],
    baselines: dict[str, list[dict[str, Any]]],
    *, project_id: str, game_id: str, source_language: str,
    review_states: dict[str, dict[str, list[str]]],
    game_profile: dict[str, Any],
) -> str:
    source = []
    for file_data in source_files:
        source.append({
            "file_path": file_data["file_path"],
            "entries": [
                {"key": key, "source": text}
                for key, text, _line in file_data["parsed_entries"]
            ],
        })
    source.sort(key=lambda item: item["file_path"].casefold())
    payload = {
        "project_id": project_id, "game_id": game_id,
        "source_language": source_language, "source": source, "baselines": baselines,
        "review_states": review_states,
        "game_profile": {
            "id": game_profile.get("id"),
            "format_adapter_id": game_profile.get("format_adapter_id"),
            "supported_language_keys": game_profile.get("supported_language_keys", []),
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _describe_changes(file_summary, history_index, diff_service, code):
    for item in file_summary["dirty_entries"]:
        _status, previous = diff_service.classify_entry(
            file_summary["file_path"], item["key"], item["source_text"], history_index, code,
        )
        previous_source = previous.get("original") if previous else None
        item["previous_source_text"] = previous_source
        item["source_changed"] = bool(previous and previous_source != item["source_text"])
        item["reason"] = ("new_entry" if previous is None else
                          "source_modified" if item["source_changed"] else
                          "review_pending" if item.get("resolution") == "review" else
                          "missing_translation")


def _summarize_language(source_files, archived, code, review_states):
    diff_service = IncrementalDiffService()
    history_index = diff_service.build_history_index(archived)
    summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
    file_summaries = []
    for file_data in source_files:
        file_summary = {
            "filename": file_data["filename"], "file_path": file_data["file_path"],
            "total": 0, "new": 0, "changed": 0, "unchanged": 0,
            "dirty_entries": [],
        }
        from scripts.core.game_adapters.review_state import pending_keys
        pending = pending_keys(file_data, code)
        review_states.setdefault(code, {})[file_data["file_path"]] = sorted(pending)
        _texts, _indices, full_entries, _keys = _prepare_file_entries(
            file_data, history_index, diff_service, code, summary, file_summary,
            None, [],
        )
        file_summary["model_submitted"] = sum(
            1 for item in full_entries if item.get("resolution") == "model"
        )
        file_summary["review_required"] = sum(
            1 for item in full_entries if item.get("resolution") == "review"
        )
        _describe_changes(file_summary, history_index, diff_service, code)
        file_summaries.append(file_summary)

    current_pairs = {
        (diff_service._normalize_file_path(item["file_path"]),
         diff_service._normalize_key(key))
        for item in source_files
        for key, _text, _line in item["parsed_entries"]
    }
    current_key_counts = Counter(key for _path, key in current_pairs)
    baseline_key_counts = Counter(
        diff_service._normalize_key(str(entry.get("key", ""))) for entry in archived
    )
    deleted = []
    for entry in archived:
        normalized_key = diff_service._normalize_key(str(entry.get("key", "")))
        normalized_path = diff_service._normalize_file_path(str(entry.get("file_path", "")))
        relocated_match = baseline_key_counts[normalized_key] == 1 and current_key_counts[normalized_key] > 0
        if (normalized_path, normalized_key) not in current_pairs and not relocated_match:
            deleted.append({
                "file_path": entry.get("file_path", ""),
                "key": entry.get("key", ""),
                "translation": entry.get("translation"),
            })
    return {
        "target_lang_code": code,
        "total": summary["total"], "new": summary["new"],
        "changed": summary["changed"], "unchanged": summary["unchanged"],
        "deleted": len(deleted),
        "model_submitted": sum(item["model_submitted"] for item in file_summaries),
        "review_required": sum(item["review_required"] for item in file_summaries),
        "deleted_entries": deleted, "file_summaries": file_summaries,
    }


async def build_incremental_preview(
    project_id: str,
    custom_source_path: str | Path | None = None,
    target_lang_codes: list[str] | None = None,
    *,
    project_manager: Any,
) -> dict[str, Any]:
    """Classify pending incremental work without creating outputs or invoking providers."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise FileNotFoundError(f"Project {project_id} not found")

    selected_source = custom_source_path or project.get("source_path")
    if not selected_source:
        raise ValueError("Project has no configured source path")
    if not target_lang_codes:
        raise ValueError("At least one target language is required")
    source_path = source_root(selected_source)
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_path}")
    source_lang = _source_language(project)

    manifest_paths = [source_path / ".remis_project.json", source_path / "mars_lua_manifest.json"]
    for manifest_path in manifest_paths:
        checked_source_path(source_path, manifest_path, missing_ok=True)
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Remis project manifest: {exc}") from exc
        configured_language = (
            manifest.get("config", {}).get("source_language")
            or manifest.get("source_selection", {}).get("language")
        )
        if configured_language:
            manifest_language = _source_language({"source_language": configured_language})
            if manifest_language["code"] != source_lang["code"]:
                raise ValueError("Source manifest language does not match the project source language")

    game_id = str(project.get("game_id", ""))
    game_profile = GAME_PROFILES_BY_ID.get(game_id) or GAME_PROFILES.get(game_id)
    if not game_profile:
        raise ValueError(f"Game profile not found for project game: {game_id or '(empty)'}")
    if len(set(target_lang_codes)) != len(target_lang_codes):
        raise ValueError("Target languages must be unique")
    if source_lang["code"] in target_lang_codes:
        raise ValueError("The project source language cannot also be a target language")
    validate_target_language_codes(game_id, target_lang_codes)

    source_files = IncrementalSnapshotService().build_snapshot(
        str(source_path), source_lang, game_profile=game_profile
    )
    source_entry_count = sum(len(item["parsed_entries"]) for item in source_files)
    if source_entry_count == 0:
        raise ValueError("Source directory contains no eligible localization entries")

    archive_service = IncrementalArchiveService()
    languages: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    fingerprint_baselines: dict[str, list[dict[str, Any]]] = {}
    review_states: dict[str, dict[str, list[str]]] = {}

    for code in target_lang_codes:
        target_lang = LANGUAGE_BY_CODE.get(code)
        if target_lang is None:
            raise ValueError(f"Unsupported target language: {code}")
        archived = archive_service.get_language_entries(project_id, code)
        fingerprint_baselines[code] = sorted(
            (dict(entry) for entry in archived),
            key=lambda entry: (
                str(entry.get("file_path", "")).casefold(),
                str(entry.get("key", "")).casefold(),
            ),
        )
        language_summary = _summarize_language(
            source_files, archived, code, review_states
        )
        languages.append(language_summary)
        file_summaries.extend({**item, "target_lang": code} for item in language_summary["file_summaries"])

    aggregate = {
        key: sum(language[key] for language in languages)
        for key in ("total", "new", "changed", "unchanged", "deleted", "model_submitted", "review_required")
    }
    return {
        "project_id": project_id,
        "source_path": str(source_path),
        "source_language": source_lang["code"],
        "languages": languages,
        "summary": aggregate,
        "file_summaries": file_summaries,
        "per_language": languages,
        "fingerprint": _fingerprint(
            source_files, fingerprint_baselines, project_id=project_id,
            game_id=game_id, source_language=source_lang["code"],
            review_states=review_states,
            game_profile=game_profile,
        ),
    }
