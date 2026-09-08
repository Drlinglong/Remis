import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Optional, List

from scripts.core.services.initial_translation_discovery_service import discover_localizable_files
from scripts.core.services.initial_translation_completion_service import finalize_workflow_run
from scripts.core.services.initial_translation_snapshot_service import (
    SourceReadResult,
    calculate_total_batches,
    create_source_snapshot,
    get_chunk_size_for_provider,
    read_files_for_backup,
)
from scripts.core.services.initial_translation_run_service import (
    build_run_plan,
    create_translation_handler,
    resolve_provider_model,
)
from scripts.core.services.initial_translation_language_service import run_language_translation
from scripts.core.services.initial_translation_workspace_service import (
    clean_source_directory,
    load_glossaries_for_run,
    prepare_output_workspace,
)
from scripts.core.services.source_snapshot_service import SourceFileInput, SourceSnapshotService
from scripts.core.services.translation_context_service import prepare_workflow_context
from scripts.core.services.translation_context_gate import (
    prepare_and_require_workflow_context,
)
from scripts.app_settings import SOURCE_DIR, DEST_DIR
from scripts.utils import i18n


@dataclass(frozen=True)
class InitialTranslationOutcome:
    status: str
    issue_count: int = 0
    recovered_entry_count: int = 0
    dropped_file_count: int = 0
    reference_metrics: tuple[dict, ...] = ()
    context_metadata: dict = None

    @property
    def message(self) -> str:
        if self.status == "completed":
            return "Translation workflow completed successfully."
        return (
            "Translation completed with source-file warnings: "
            f"{self.recovered_entry_count} invalid entries replaced with empty values; "
            f"{self.dropped_file_count} files dropped."
        )


@dataclass(frozen=True)
class PreparedTranslationRun:
    output_dir_path: str
    source_result: SourceReadResult
    all_files_content: list[dict]
    context_selection: Any
    total_files: int
    total_batches: int
    effective_chunk_size: int
    version_id: int
    source_root: str
    source_snapshot_hash: str


def _prepare_source_files(
    mod_name: str,
    game_profile: dict,
    source_lang: dict,
    override_path: Optional[str],
    progress_callback: Optional[Any],
):
    all_file_paths = discover_files(
        mod_name, game_profile, source_lang, override_path=override_path
    )
    if not all_file_paths:
        message = i18n.t("no_localisable_files_found", lang_name=source_lang['name'])
        logging.warning(message)
        raise RuntimeError(message)

    total_files = len(all_file_paths)
    if progress_callback:
        progress_callback(0, total_files, "", "Analyzing Files")
    source_result = read_files_for_backup(all_file_paths, total_files, progress_callback)
    if isinstance(source_result, list):
        source_result = SourceReadResult(files=source_result)
    if not source_result.files:
        detail = source_result.issues[0].log_message() if source_result.issues else ""
        raise RuntimeError(f"No usable localization files remain. {detail}".strip())
    return source_result, total_files


def _prepare_context_selection(
    project_id, files, use_project_context, context_release_id,
    context_character_budget, context_service, snapshot_service,
    translation_context_mode, stale_choice=None, stale_acknowledgement=None,
):
    return prepare_and_require_workflow_context(
        prepare_workflow_context,
        (
            project_id, files, use_project_context,
            context_release_id, context_character_budget,
            context_service, snapshot_service,
        ),
        translation_context_mode,
        {"stale_choice": stale_choice, "stale_acknowledgement": stale_acknowledgement},
    )


def _source_snapshot_hash(files: list[dict], source_root: str) -> str:
    inputs = []
    for file_data in files:
        source_path = file_data.get("path")
        relative_path = file_data.get("file_path")
        if not relative_path and source_path:
            try:
                relative_path = os.path.relpath(source_path, source_root)
            except ValueError:
                relative_path = file_data.get("filename") or os.path.basename(source_path)
        relative_path = str(
            relative_path or file_data.get("filename") or os.path.basename(source_path or "source")
        ).replace("\\", "/")
        if source_path and os.path.isfile(source_path):
            inputs.append(SourceFileInput(relative_path=relative_path, path=source_path))
        else:
            content = "".join(str(line) for line in file_data.get("original_lines") or [])
            inputs.append(SourceFileInput(relative_path=relative_path, content=content))
    return SourceSnapshotService().build_snapshot(inputs).source_snapshot_hash


def _run_language_targets(
    *, target_languages, mod_name, source_lang, game_profile, mod_context,
    handler, output_folder_name, output_dir_path, selected_provider, model_name,
    all_files_content, total_batches, effective_chunk_size, progress_callback,
    project_id, version_id, override_path, use_resume, concurrency_limit, rpm_limit,
    batch_size_limit, embedded_workshop, reference_reuse, source_context_overlap,
    context_selection, provider_runtime, should_cancel, task_id, run_id, source_root,
    source_snapshot_hash, config_fingerprint,
) -> tuple[dict, ...]:
    metrics = []
    for target_lang in target_languages:
        metrics.append(run_language_translation(
            mod_name=mod_name,
            source_lang=source_lang,
            target_lang=target_lang,
            game_profile=game_profile,
            mod_context=mod_context,
            handler=handler,
            output_folder_name=output_folder_name,
            output_dir_path=output_dir_path,
            selected_provider=selected_provider,
            model_name=model_name,
            all_files_content=all_files_content,
            total_batches=total_batches,
            effective_chunk_size=effective_chunk_size,
            progress_callback=progress_callback,
            project_id=project_id,
            version_id=version_id,
            override_path=override_path,
            use_resume=use_resume,
            concurrency_limit=concurrency_limit,
            rpm_limit=rpm_limit,
            batch_size_limit=batch_size_limit,
            embedded_workshop=embedded_workshop,
            reference_reuse=reference_reuse,
            source_context_overlap=source_context_overlap,
            context_selection=context_selection,
            provider_runtime=provider_runtime,
            should_cancel=should_cancel,
            task_id=task_id,
            run_id=run_id,
            source_root=source_root,
            source_snapshot_hash=source_snapshot_hash,
            config_fingerprint=config_fingerprint,
        ))
    return tuple(metrics)


def _prepare_translation_run(
    *, mod_name, output_folder_name, game_profile, source_lang, selected_provider, selected_glossary_ids,
    use_glossary, clean_source, override_path, progress_callback, project_id,
    use_project_context, translation_context_mode, context_release_id,
    context_character_budget, context_service, snapshot_service, batch_size_limit,
    stale_choice=None, stale_acknowledgement=None,
) -> PreparedTranslationRun:
    load_glossaries_for_run(game_profile.get("id", ""), use_glossary, selected_glossary_ids)
    output_dir_path = prepare_output_workspace(mod_name, output_folder_name, game_profile)
    if clean_source:
        clean_source_directory(mod_name, override_path=override_path)
    source_result, total_files = _prepare_source_files(
        mod_name, game_profile, source_lang, override_path, progress_callback
    )
    all_files_content = source_result.files
    context_selection = _prepare_context_selection(
        project_id, all_files_content,
        use_project_context or translation_context_mode == "archive",
        context_release_id, context_character_budget, context_service, snapshot_service,
        translation_context_mode, stale_choice, stale_acknowledgement,
    )
    source_root = override_path or os.path.join(SOURCE_DIR, mod_name)
    source_snapshot_hash = (
        (context_selection.metadata or {}).get("source_snapshot_hash")
        or _source_snapshot_hash(all_files_content, source_root)
    )
    effective_chunk_size = get_chunk_size_for_provider(selected_provider, batch_size_limit)
    total_batches = calculate_total_batches(all_files_content, effective_chunk_size)
    _, version_id = create_source_snapshot(
        mod_name, all_files_content, total_files, total_batches,
        progress_callback, project_id,
    )
    if not version_id:
        raise RuntimeError("Failed to create the source archive snapshot.")
    return PreparedTranslationRun(
        output_dir_path=output_dir_path,
        source_result=source_result,
        all_files_content=all_files_content,
        context_selection=context_selection,
        total_files=total_files,
        total_batches=total_batches,
        effective_chunk_size=effective_chunk_size,
        version_id=version_id,
        source_root=source_root,
        source_snapshot_hash=source_snapshot_hash,
    )


def _resolve_run_identity(
    recovery_identity: Optional[dict],
    task_id: Optional[str],
    run_id: Optional[str],
    progress_callback: Optional[Any],
) -> tuple[dict, Optional[str], str]:
    identity = dict(recovery_identity or {})
    resolved_task_id = identity.get("checkpoint_owner_task_id") or task_id or getattr(
        progress_callback, "task_id", None
    )
    resolved_run_id = identity.get("checkpoint_owner_run_id") or run_id or getattr(
        progress_callback, "run_id", None
    ) or str(uuid.uuid4())
    return identity, resolved_task_id, resolved_run_id


def _build_run_plan(mod_name: str, target_languages: list[dict]):
    run_plan = build_run_plan(mod_name, target_languages)
    return run_plan, run_plan.output_folder_name, run_plan.primary_target_lang


def _unpack_prepared_run(prepared: PreparedTranslationRun, recovery_identity: dict):
    return (
        prepared.output_dir_path,
        prepared.source_result,
        prepared.all_files_content,
        prepared.context_selection,
        prepared.total_batches,
        prepared.version_id,
        prepared.source_root,
        prepared.source_snapshot_hash,
        prepared.effective_chunk_size,
    )


def run(
    mod_name: str, source_lang: dict, target_languages: list[dict],
    game_profile: dict, mod_context: str, selected_provider: str = "gemini",
    selected_glossary_ids: Optional[List[int]] = None, mod_id_for_archive: Optional[int] = None,
    model_name: Optional[str] = None, use_glossary: bool = True,
    project_id: Optional[str] = None, custom_lang_config: Optional[dict] = None,
    progress_callback: Optional[Any] = None,
    override_path: Optional[str] = None, use_resume: bool = False,
    clean_source: bool = False, batch_size_limit: Optional[int] = None,
    source_context_overlap: int = 0, concurrency_limit: Optional[int] = None,
    rpm_limit: Optional[int] = 40, embedded_workshop: Optional[dict] = None,
    reference_reuse: Optional[dict] = None, use_project_context: bool = False,
    context_release_id: Optional[str] = None, context_character_budget: int = 4000,
    context_service: Any = None, snapshot_service: Any = None,
    translation_context_mode: Optional[str] = None, provider_runtime: Any = None,
    task_id: Optional[str] = None, run_id: Optional[str] = None,
    should_cancel: Optional[Any] = None, recovery_identity: Optional[dict] = None,
    stale_choice: Optional[str] = None,
    stale_acknowledgement: Optional[dict] = None,
):
    """【最终版】初次翻译工作流（多语言 & 多游戏兼容）- 流式处理 & 断点续传版"""
    logging.info(f"--- Starting 'Initial Translation' workflow for: {mod_name} ---")
    recovery_identity, task_id, run_id = _resolve_run_identity(
        recovery_identity, task_id, run_id, progress_callback
    )
    run_plan, output_folder_name, primary_target_lang = _build_run_plan(mod_name, target_languages)
    logging.info(i18n.t("start_workflow",
                 workflow_name=i18n.t("workflow_initial_translate_name"),
                 mod_name=mod_name))
    logging.info(i18n.t("log_selected_provider", provider=selected_provider))
    resolved_model_name = resolve_provider_model(selected_provider, model_name)
    handler = create_translation_handler(selected_provider, resolved_model_name, provider_runtime)
    if not handler:
        raise RuntimeError("Failed to initialize the selected translation provider.")
    prepared = _prepare_translation_run(
        mod_name=mod_name,
        output_folder_name=output_folder_name,
        game_profile=game_profile,
        source_lang=source_lang,
        selected_provider=selected_provider,
        selected_glossary_ids=selected_glossary_ids,
        use_glossary=use_glossary,
        clean_source=clean_source,
        override_path=override_path,
        progress_callback=progress_callback,
        project_id=project_id,
        use_project_context=use_project_context,
        translation_context_mode=translation_context_mode,
        context_release_id=context_release_id,
        context_character_budget=context_character_budget,
        context_service=context_service,
        snapshot_service=snapshot_service,
        batch_size_limit=batch_size_limit,
        stale_choice=stale_choice,
        stale_acknowledgement=stale_acknowledgement,
    )
    (
        output_dir_path, source_result, all_files_content, context_selection,
        total_batches, version_id, source_root, source_snapshot_hash, effective_chunk_size,
    ) = _unpack_prepared_run(prepared, recovery_identity)
    last_target_lang = target_languages[-1]
    reference_metrics = _run_language_targets(
        target_languages=target_languages,
        mod_name=mod_name,
        source_lang=source_lang,
        game_profile=game_profile,
        mod_context=mod_context,
        handler=handler,
        output_folder_name=output_folder_name,
        output_dir_path=output_dir_path,
        selected_provider=selected_provider,
        model_name=resolved_model_name,
        all_files_content=all_files_content,
        total_batches=total_batches,
        effective_chunk_size=effective_chunk_size,
        progress_callback=progress_callback,
        project_id=project_id,
        version_id=version_id,
        override_path=override_path,
        use_resume=use_resume,
        concurrency_limit=concurrency_limit,
        rpm_limit=rpm_limit,
        batch_size_limit=batch_size_limit,
        embedded_workshop=embedded_workshop,
        reference_reuse=reference_reuse,
        source_context_overlap=source_context_overlap,
        context_selection=context_selection,
        provider_runtime=provider_runtime,
        should_cancel=should_cancel,
        task_id=task_id,
        run_id=run_id,
        source_root=source_root,
        source_snapshot_hash=source_snapshot_hash,
        config_fingerprint=recovery_identity.get("config_fingerprint"),
    )
    finalize_workflow_run(
        run_plan.is_batch_mode,
        mod_name,
        handler,
        source_lang,
        primary_target_lang,
        last_target_lang,
        output_folder_name,
        mod_context,
        game_profile,
        output_dir_path,
        selected_provider,
        resolved_model_name,
        target_languages,
        project_id,
    )
    status = "partial_failed" if source_result.issues else "completed"
    return InitialTranslationOutcome(
        status=status,
        issue_count=len(source_result.issues),
        recovered_entry_count=source_result.recovered_entry_count,
        dropped_file_count=source_result.dropped_file_count,
        reference_metrics=tuple(reference_metrics),
        context_metadata=context_selection.metadata,
    )


def discover_files(mod_name: str, game_profile: dict, source_lang: dict, override_path: Optional[str] = None) -> List[dict]:
    return discover_localizable_files(
        mod_name,
        game_profile,
        source_lang,
        override_path,
        source_dir=SOURCE_DIR,
    )
