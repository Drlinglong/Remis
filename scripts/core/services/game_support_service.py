"""Shared read-only game knowledge for Agent API, Copilot and operator clients."""
from __future__ import annotations

from scripts.core.game_adapters.project_support import inspect_support
from scripts.core.game_adapters.registry import game_capabilities, resource_adapter


def get_game_support(game_id: str) -> dict:
    from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGES
    if game_id not in GAME_PROFILES_BY_ID:
        raise ValueError(f"Unknown game: {game_id}")
    adapter = resource_adapter(game_id)
    formats = {
        "project_zomboid": ["Translate JSON string maps", "restricted literal Lua-table TXT"],
        "rimworld": ["Keyed", "DefInjected", "Strings", "known translatable Defs fields", "rulesStrings"],
        "surviving_mars": ["ModItemLocTable CSV"],
    }
    limitations = {
        "project_zomboid": ["Unknown/nested JSON shapes and Lua expressions are diagnosed, not executed.",
                            "Hard-coded Lua strings and special media formats are not covered."],
        "rimworld": ["Unknown fields, inheritance, PatchOperation and conditional dependencies need review.",
                     "Assemblies and runtime-generated text are not executed or fully resolved."],
        "surviving_mars": ["Reuses existing CSV translation only; independent translation Mod generation is not implemented."],
    }
    special = adapter is not None or game_id == "surviving_mars"
    return {
        "game_id": game_id, "capabilities": game_capabilities(game_id),
        "formats": formats.get(game_id, ["Paradox localization YAML"]),
        "output_kind": "independent_translation_mod" if adapter else ("csv_files" if special else "paradox_mod"),
        "export_mode": "manual_install" if adapter else ("local_files" if special else "paradox_deployment"),
        "language_folders": ({item["code"]: adapter.language_folder(item) for item in LANGUAGES.values()}
                             if adapter else {}),
        "shell_languages_supported": not special,
        "limitations": limitations.get(game_id, []),
        "version_policy": "Record provenance and effective directories; do not disable known rules for minor-version differences.",
        "incremental_policy": "Compare individual source entries; Mod metadata version changes alone do not require retranslating entries.",
        "changed_translation_policy": "preserve_and_require_review" if adapter else "existing_workflow",
        "runtime_verified": False if adapter else None,
        "source_files_read_only": True,
        "workflow_modes": ["initial", "incremental"],
        "incremental_checkpoint_resume_supported": False,
        "terminology": {"existing_glossaries": True, "automatic_official_language_pack_candidates": False},
    }


def inspect_game_support(game_id: str, source_path: str, source_language: str = "en",
                         game_version: str | None = None) -> dict:
    contract = get_game_support(game_id)
    result = inspect_support(game_id, source_path, source_language, game_version)
    diagnostics = result["diagnostics"]
    return {**result, "support": contract, "read_only": True,
            "source_language": source_language, "requested_game_version": game_version,
            "recognized_resource_count": len(result["resources"]),
            "recognized_entry_count": sum(item["entry_count"] for item in result["resources"]),
            "coverage_scope": "recognized_resources_only" if resource_adapter(game_id) else "use_existing_file_inspection",
            "has_blocking_diagnostics": any(item.get("severity") == "error" for item in diagnostics),
            "runtime_verified": contract["runtime_verified"],
            "allowed_actions": ["inspect_diagnostics"] if any(item.get("severity") == "error" for item in diagnostics)
            else ["create_translation_plan"]}


async def inspect_project_game_support(project_id: str, game_version: str | None = None) -> dict:
    from scripts.shared.services import project_manager
    project = await project_manager.get_project(project_id)
    if not project:
        raise LookupError("Project not found")
    return {"project_id": project_id, **inspect_game_support(project["game_id"], project["source_path"],
            project.get("source_language", "en"), game_version)}
