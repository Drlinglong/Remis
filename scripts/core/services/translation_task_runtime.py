"""Small runtime helpers shared by translation routes and background workers."""

from __future__ import annotations

import os
from typing import Any, Optional

from scripts.app_settings import DEST_DIR
from scripts.core.provider_errors import provider_failure_task_fields
from scripts.core.services.translation_recovery_service import (
    TranslationRecoveryService,
    build_recovery_descriptor,
    canonical_configuration,
    source_tree_hash,
)
from scripts.shared import task_state
from scripts.utils.system_utils import slugify_to_ascii


def get_output_folder_name(mod_name: str, target_lang: dict) -> str:
    prefix = target_lang.get("folder_prefix", f"{target_lang.get('code', 'unknown')}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}"


def get_output_directories(mod_name: str, target_languages: list[dict]) -> list[str]:
    if len(target_languages) > 1:
        return [os.path.join(DEST_DIR, f"Multilanguage-{slugify_to_ascii(mod_name)}")]
    return [
        os.path.join(DEST_DIR, get_output_folder_name(mod_name, target_language))
        for target_language in target_languages
    ]


def get_checkpoint_output_dir(mod_name: str, target_languages: list[dict]) -> str:
    return get_output_directories(mod_name, target_languages)[0]


def prepare_initial_recovery(
    *,
    request: Any,
    project: dict,
    task_id: str,
    target_languages: list[dict],
    provider_runtime: Any = None,
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
    recovery = build_recovery_descriptor(
        task_id=task_id,
        project_id=request.project_id,
        source_root=source_path,
        output_dir=get_checkpoint_output_dir(mod_name, target_languages),
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
