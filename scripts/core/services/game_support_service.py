"""Shared read-only game knowledge for Agent API, Copilot and operator clients."""
from __future__ import annotations

from scripts.core.game_adapters.project_support import inspect_support
from scripts.core.game_adapters.registry import game_capabilities, resource_adapter
from scripts.core.services.game_language_policy import supported_language_codes
from scripts.core.services import mars_translation_package
from scripts.core.services.mars_game_support import csv_contract, inspect_csv_support


def get_game_support(game_id: str) -> dict:
    from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGES
    if game_id not in GAME_PROFILES_BY_ID:
        raise ValueError(f"Unknown game: {game_id}")
    adapter = resource_adapter(game_id)
    formats = {
        "project_zomboid": ["Translate JSON string maps", "restricted literal Lua-table TXT"],
        "rimworld": ["Keyed", "DefInjected", "Strings", "known translatable Defs fields", "rulesStrings"],
        "surviving_mars": [
            "ModItemLocTable CSV",
            "Independent translation-only Mod package with ModItemLocTable",
            "Bounded FLPK v1 extraction and reviewed Lua internationalization",
        ],
    }
    limitations = {
        "project_zomboid": ["Unknown/nested JSON shapes and Lua expressions are diagnosed, not executed.",
                            "Hard-coded Lua strings and special media formats are not covered."],
        "rimworld": ["Unknown fields, inheritance, PatchOperation and conditional dependencies need review.",
                     "Assemblies and runtime-generated text are not executed or fully resolved."],
        "surviving_mars": [
            "Translation-only Mod packages reference the original Mod as a required dependency and include no source assets.",
            "FPK extraction supports the verified FLPK v1 profile; other profiles fail explicitly. Repacking, deployment and publishing are not implemented.",
            "Hard-coded Untranslated strings are outside recognized ModItemLocTable CSV coverage.",
        ],
    }
    special = adapter is not None or game_id == "surviving_mars"
    mars_languages = supported_language_codes(game_id) if game_id == "surviving_mars" else []
    return {
        "game_id": game_id, "capabilities": game_capabilities(game_id),
        **({"supported_language_codes": mars_languages,
            "game_language_tokens": {code: mars_translation_package.LANGUAGE_NAMES[code]
                                     for code in mars_languages}}
           if game_id == "surviving_mars" else {}),
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
        "runtime_verified": False if special else None,
        **({"translation_package": {
            "supported": True,
            "format": "metadata.loctables + items.lua ModItemLocTable",
            "output_kind": "independent_translation_mod",
            "export_mode": "manual_install",
            "options_endpoint": "/api/agent/projects/{project_id}/translation-package/options",
            "plan_endpoint": "/api/agent/projects/{project_id}/translation-package/plan",
            "export_endpoint": "/api/agent/projects/{project_id}/translation-package",
            "requires_original_mod": True,
            "includes_source_assets": False,
            "runtime_verified": False,
        }} if game_id == "surviving_mars" else {}),
        **({"csv_contract": csv_contract(), "hardcoded_lua": {
            "discovery_supported": True, "scope": "direct_untranslated_calls_only",
            "inspection_endpoint": "/api/agent/projects/{project_id}/game-support",
            "automatic_rewrite_supported": False, "included_in_csv_translation": False,
            "identity_policy": "Review candidates and persist a language-independent manifest before allocating numeric localization IDs.",
        }} if game_id == "surviving_mars" else {}),
        **({"source_pipeline": {
            "supported": True, "source_language": "en", "runtime_verified": False,
            "prepare_plan_endpoint": "/api/agent/mars-pipeline/prepare/plan",
            "prepare_endpoint": "/api/agent/mars-pipeline/prepare",
            "run_endpoint": "/api/agent/mars-pipeline/runs/{run_id}",
            "options_endpoint": "/api/agent/projects/{project_id}/mars-pipeline",
            "export_plan_endpoint": "/api/agent/projects/{project_id}/mars-pipeline/export/plan",
            "export_endpoint": "/api/agent/projects/{project_id}/mars-pipeline/export",
            "publication_endpoint": "/api/agent/projects/{project_id}/mars-pipeline/publication",
            "user_guide": "docs/zh/user-guides/surviving-mars.md",
            "multiple_languages_per_package": True,
            "translation_outputs_are_working_files": True,
            "installation": {
                "mode": "manual_install",
                "relaunch_windows_root": "%APPDATA%/Surviving Mars Relaunched/Mods",
                "package_folder": "<output_mod_id>",
                "metadata_at_package_root": True,
                "text_only": "Enable the original Mod and this translation package together.",
                "source_copy": "Disable the original Mod and older translation patches; enable this complete copy.",
            },
            "publishing": {"mode": "manual_game_mod_editor", "automatic_upload": False,
                           "binding_scope": "project_source_copy", "bind_original_author_id": False},
            "delivery_modes": ["text_only", "source_copy"],
            "advanced_delivery_modes": ["overlay"],
            "source_copy_includes_all_assets": True, "original_archive_read_only": True,
            "review_required": True, "overlay_requires_reviewed_runtime_profile": True,
        }} if game_id == "surviving_mars" else {}),
        "source_files_read_only": True,
        "workflow_modes": ["initial", "incremental"],
        "incremental_checkpoint_resume_supported": False,
        "terminology": {"existing_glossaries": True, "automatic_official_language_pack_candidates": False},
    }


def inspect_game_support(game_id: str, source_path: str, source_language: str = "en",
                         game_version: str | None = None) -> dict:
    contract = get_game_support(game_id)
    result = (inspect_csv_support(source_path) if game_id == "surviving_mars"
              else inspect_support(game_id, source_path, source_language, game_version))
    diagnostics = result["diagnostics"]
    return {**result, "support": contract, "read_only": True,
            "source_language": source_language, "requested_game_version": game_version,
            "recognized_resource_count": len(result["resources"]),
            "recognized_entry_count": sum(item["entry_count"] for item in result["resources"]),
            "coverage_scope": "recognized_resources_only" if resource_adapter(game_id) or game_id == "surviving_mars" else "use_existing_file_inspection",
            "has_blocking_diagnostics": any(item.get("severity") == "error" for item in diagnostics),
            "runtime_verified": contract["runtime_verified"],
            "allowed_actions": ["inspect_diagnostics"] if any(item.get("severity") == "error" for item in diagnostics)
            else ["create_translation_plan"]}


async def inspect_project_game_support(project_id: str, game_version: str | None = None) -> dict:
    from scripts.shared.services import project_manager
    project = await project_manager.get_project(project_id)
    if not project:
        raise LookupError("Project not found")
    effective_version = game_version or project.get("game_version")
    return {"project_id": project_id, **inspect_game_support(
        project["game_id"], project["source_path"],
        project.get("source_language", "en"), effective_version,
    )}
