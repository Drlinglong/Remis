"""Bounded read-only game support data exposed to Copilot agents."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any

from scripts.core.services.game_support_service import (
    get_game_support,
    inspect_game_support as _inspect_game_support,
    inspect_project_game_support as _inspect_project_game_support,
)


_PUBLIC_SUPPORT_FIELDS = (
    "game_id",
    "capabilities",
    "formats",
    "output_kind",
    "export_mode",
    "language_folders",
    "supported_language_codes",
    "game_language_tokens",
    "shell_languages_supported",
    "limitations",
    "version_policy",
    "incremental_policy",
    "changed_translation_policy",
    "runtime_verified",
    "source_files_read_only",
    "workflow_modes",
    "incremental_checkpoint_resume_supported",
    "terminology",
    "csv_contract",
    "translation_package",
    "hardcoded_lua",
    "source_pipeline",
)


def _safe_support(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in _PUBLIC_SUPPORT_FIELDS if key in value}


def read_game_support(game_id: str) -> dict[str, Any]:
    """Return static capability facts without project paths or user data."""
    result = get_game_support(game_id)
    return {**_safe_support(result), "read_only": True}


def inspect_folder_game_support(
    game_id: str, source_path: str, source_language: str = "en"
) -> dict[str, Any]:
    """Summarize recognized resources for a folder already validated by the caller."""
    return _safe_project_summary(
        _inspect_game_support(game_id, source_path, source_language)
    )


def _safe_diagnostic(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    path = item.get("path")
    result = {key: item[key] for key in ("code", "severity") if key in item}
    if "message" in item:
        message = str(item["message"])
        result["message"] = re.sub(
            r"(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/])[^\s,;]+",
            "<path>", message,
        )
    if path:
        result["path"] = PurePath(str(path).replace("\\", "/")).name
    return result


async def inspect_project_game_support(
    project_id: str, game_version: str | None = None
) -> dict[str, Any]:
    """Return project resource coverage while withholding absolute source paths."""
    result = await _inspect_project_game_support(project_id, game_version)
    return _safe_project_summary(result)


def _safe_project_summary(result: dict[str, Any]) -> dict[str, Any]:
    resources = [
        {
            "path": PurePath(str(item.get("path") or "").replace("\\", "/")).name,
            "entry_count": int(item.get("entry_count") or 0),
        }
        for item in result.get("resources", [])
        if isinstance(item, dict)
    ]
    return {
        "project_id": result.get("project_id"),
        "game_id": result.get("game_id"),
        "requested_game_version": result.get("requested_game_version"),
        "support": _safe_support(result.get("support") or {}),
        "resources": resources,
        "diagnostics": [
            safe for item in result.get("diagnostics", [])
            if (safe := _safe_diagnostic(item))
        ],
        "recognized_resource_count": int(result.get("recognized_resource_count") or 0),
        "recognized_entry_count": int(result.get("recognized_entry_count") or 0),
        "coverage_scope": result.get("coverage_scope"),
        "hardcoded_lua": {
            key: value for key, value in (result.get("hardcoded_lua") or {}).items()
            if key in {"scan_complete", "scope", "files_scanned", "candidate_count",
                       "literal_count", "dynamic_count", "included_in_translation",
                       "automatic_rewrite_supported", "requires_review", "limitations"}
        },
        "has_blocking_diagnostics": bool(result.get("has_blocking_diagnostics")),
        "runtime_verified": result.get("runtime_verified"),
        "allowed_actions": list(result.get("allowed_actions") or []),
        "read_only": True,
    }
