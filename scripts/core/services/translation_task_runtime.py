"""Small runtime helpers shared by translation routes and background workers."""

from __future__ import annotations

import os
from hashlib import sha256
from typing import Any, Optional

from scripts.app_settings import DEST_DIR, GAME_PROFILES, GAME_PROFILES_BY_ID
from scripts.core.provider_errors import provider_failure_task_fields
from scripts.core.services.translation_recovery_service import (
    TranslationRecoveryService,
    build_recovery_descriptor,
    canonical_configuration,
    source_tree_hash,
)
from scripts.shared import task_state
from scripts.utils.system_utils import slugify_to_ascii


def _project_output_suffix(project_id: Optional[str]) -> str:
    if not project_id:
        return ""
    normalized = slugify_to_ascii(str(project_id)).strip("-_") or "project"
    digest = sha256(str(project_id).encode("utf-8")).hexdigest()[:12]
    return f"--{normalized[:32]}-{digest}"


def get_output_folder_name(mod_name: str, target_lang: dict, project_id: Optional[str] = None) -> str:
    prefix = target_lang.get("folder_prefix", f"{target_lang.get('code', 'unknown')}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}{_project_output_suffix(project_id)}"


def _language_output_folder_name(mod_name: str, target_lang: dict) -> str:
    prefix = target_lang.get("folder_prefix", f"{target_lang.get('code', 'unknown')}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}"


def get_output_folder_names(
    mod_name: str,
    target_languages: list[dict],
    project_id: Optional[str] = None,
    game_profile: Optional[dict] = None,
) -> list[str]:
    # Keep compatibility with callers that historically passed game_profile as
    # the third positional argument.
    if isinstance(project_id, dict):
        game_profile = project_id
        project_id = game_profile.get("_output_project_id")
    if len(target_languages) > 1:
        if game_profile and game_profile.get("format_adapter_id") == "surviving_mars_csv":
            return [
                f"{_language_output_folder_name(mod_name, language)}"
                f"{_project_output_suffix(project_id)}"
                for language in target_languages
            ]
        return [
            f"Multilanguage-{slugify_to_ascii(mod_name)}"
            f"{_project_output_suffix(project_id)}"
        ]
    return [
        get_output_folder_name(mod_name, target_language, project_id)
        for target_language in target_languages
    ]


def get_output_directories(
    mod_name: str,
    target_languages: list[dict],
    project_id: Optional[str] = None,
    game_profile: Optional[dict] = None,
) -> list[str]:
    return [
        os.path.join(DEST_DIR, folder_name)
        for folder_name in get_output_folder_names(
            mod_name,
            target_languages,
            project_id,
            game_profile,
        )
    ]


def get_checkpoint_output_dir(
    mod_name: str,
    target_languages: list[dict],
    project_id: Optional[str] = None,
) -> str:
    if len(target_languages) > 1:
        folder_name = (
            f"Multilanguage-{slugify_to_ascii(mod_name)}"
            f"{_project_output_suffix(project_id)}"
        )
        return os.path.join(DEST_DIR, folder_name)
    return get_output_directories(mod_name, target_languages, project_id)[0]


def resolve_task_output_directories(
    mod_name: str,
    target_languages: list[dict],
    project_id: Optional[str],
    recovery_identity: Optional[dict],
    game_profile: Optional[dict] = None,
) -> list[str]:
    recovery_output = str((recovery_identity or {}).get("output_dir") or "").strip()
    if (
        len(target_languages) > 1
        and game_profile
        and game_profile.get("format_adapter_id") == "surviving_mars_csv"
    ):
        return get_output_directories(
            mod_name,
            target_languages,
            project_id,
            game_profile,
        )
    if recovery_output:
        return [os.path.abspath(recovery_output)]
    return get_output_directories(mod_name, target_languages, project_id, game_profile)


def prepare_initial_recovery(
    *,
    request: Any,
    project: dict,
    task_id: str,
    target_languages: list[dict],
    provider_runtime: Any = None,
    game_profile: Optional[dict] = None,
) -> tuple[str, dict]:
    source_path = str(project.get("source_path") or "")
    if not os.path.isdir(source_path):
        raise ValueError(f"Project source path not found: {source_path}")
    mod_name = os.path.basename(os.path.normpath(source_path))
    source_snapshot_hash = source_tree_hash(source_path)
    configuration = canonical_configuration(request.model_dump(mode="json"))
    if provider_runtime is not None and hasattr(provider_runtime, "safe_metadata"):
        runtime_fingerprint = provider_runtime.safe_metadata().get("config_fingerprint")
        if runtime_fingerprint:
            configuration["provider_runtime_fingerprint"] = runtime_fingerprint
    owner_task_id = task_id
    owner_run_id = task_id
    parent_recovery = {}
    if request.resume_from_task_id:
        repository = task_state.get_repository()
        if repository is None:
            raise ValueError("Task persistence is unavailable for checkpoint resume")
        parent = TranslationRecoveryService(repository).require_resumable(
            request.resume_from_task_id,
            expected_checkpoint_revision=getattr(
                request, "expected_checkpoint_revision", None
            ),
            source_snapshot_hash=source_snapshot_hash,
        )
        parent_recovery = parent.get("recovery") or {}
        if parent_recovery.get("configuration_snapshot") != configuration:
            raise ValueError("Recovery configuration changed; start over is required")
        owner_task_id = parent_recovery.get("checkpoint_owner_task_id") or parent["task_id"]
        owner_run_id = parent_recovery.get("checkpoint_owner_run_id") or parent_recovery["run_id"]
    output_dir = parent_recovery.get("output_dir")
    if not output_dir:
        output_dir = get_checkpoint_output_dir(
            mod_name,
            target_languages,
            request.project_id,
        )
        if game_profile is None:
            game_id = str(project.get("game_id") or "")
            game_profile = GAME_PROFILES_BY_ID.get(game_id) or GAME_PROFILES.get(game_id)
        if game_profile:
            from scripts.core.game_adapters.registry import resource_adapter
            if resource_adapter(game_profile):
                from scripts.core.services.initial_translation_run_service import resource_output_folder
                output_dir = os.path.join(
                    os.path.dirname(output_dir),
                    resource_output_folder(
                        os.path.basename(output_dir),
                        game_profile,
                        owner_run_id,
                    ),
                )
    recovery = build_recovery_descriptor(
        task_id=task_id,
        project_id=request.project_id,
        source_root=source_path,
        output_dir=output_dir,
        target_lang_codes=[language["code"] for language in target_languages],
        configuration=configuration,
        snapshot_hash=source_snapshot_hash,
        resumed_from_task_id=request.resume_from_task_id,
        checkpoint_owner_task_id=owner_task_id,
        checkpoint_owner_run_id=owner_run_id,
    )
    return mod_name, recovery


def finalize_translation_task(
    task_id: str,
    status: str,
    log_message: Optional[str] = None,
    stage: Optional[str] = None,
    error_count: Optional[int] = None,
    error: Optional[BaseException] = None,
) -> None:
    progress = {}
    if status in {"completed", "partial_failed"}:
        progress["percent"] = 100
    if error_count is not None:
        progress["error_count"] = error_count
    if stage:
        progress["stage"] = stage
    task_state.update_task(
        task_id,
        status=status,
        append_log=log_message,
        progress=progress or None,
        fields=provider_failure_task_fields(error) if error else None,
        push=True,
    )
