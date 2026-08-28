import logging
from dataclasses import dataclass
from typing import Any, Optional, List

from scripts.core.services.initial_translation_discovery_service import discover_localizable_files
from scripts.core.services.initial_translation_completion_service import finalize_workflow_run
from scripts.core.services.initial_translation_snapshot_service import (
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
from scripts.app_settings import SOURCE_DIR, DEST_DIR
from scripts.utils import i18n


@dataclass(frozen=True)
class InitialTranslationOutcome:
    status: str
    issue_count: int = 0
    recovered_entry_count: int = 0
    dropped_file_count: int = 0
    reference_metrics: tuple[dict, ...] = ()

    @property
    def message(self) -> str:
        if self.status == "completed":
            return "Translation workflow completed successfully."
        return (
            "Translation completed with source-file warnings: "
            f"{self.recovered_entry_count} invalid entries replaced with empty values; "
            f"{self.dropped_file_count} files dropped."
        )


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
    if not source_result.files:
        detail = source_result.issues[0].log_message() if source_result.issues else ""
        raise RuntimeError(f"No usable localization files remain. {detail}".strip())
    return source_result, total_files


def run(mod_name: str,
        source_lang: dict,
        target_languages: list[dict],
        game_profile: dict,
        mod_context: str,
        selected_provider: str = "gemini",
        selected_glossary_ids: Optional[List[int]] = None,
        mod_id_for_archive: Optional[int] = None,
        model_name: Optional[str] = None,
        use_glossary: bool = True,
        project_id: Optional[str] = None,
        custom_lang_config: Optional[dict] = None,
        progress_callback: Optional[Any] = None,
        override_path: Optional[str] = None,
        use_resume: bool = True,
        clean_source: bool = False,
        batch_size_limit: Optional[int] = None,
        concurrency_limit: Optional[int] = None,
        rpm_limit: Optional[int] = 40,
        embedded_workshop: Optional[dict] = None,
        reference_reuse: Optional[dict] = None):
    """【最终版】初次翻译工作流（多语言 & 多游戏兼容）- 流式处理 & 断点续传版"""
    logging.info("Entered initial_translate.run")
    logging.info(f"--- Starting 'Initial Translation' workflow for: {mod_name} ---")
    # ───────────── 1. 路径与模式 ─────────────
    run_plan = build_run_plan(mod_name, target_languages)
    output_folder_name = run_plan.output_folder_name
    primary_target_lang = run_plan.primary_target_lang
    logging.info(i18n.t("start_workflow",
                 workflow_name=i18n.t("workflow_initial_translate_name"),
                 mod_name=mod_name))
    logging.info(i18n.t("log_selected_provider", provider=selected_provider))
    # ───────────── 2. 初始化客户端 ─────────────
    resolved_model_name = resolve_provider_model(selected_provider, model_name)
    handler = create_translation_handler(selected_provider, resolved_model_name)
    if not handler:
        raise RuntimeError("Failed to initialize the selected translation provider.")
    # ───────────── 2.5. 加载词典 ─────────────
    game_id = game_profile.get("id", "")
    load_glossaries_for_run(game_id, use_glossary, selected_glossary_ids)

    # ───────────── 3. 创建输出目录 & 初始化断点管理器 ─────────────
    output_dir_path = prepare_output_workspace(mod_name, output_folder_name, game_profile)
    
    # ───────────── 3.5. [NEW] 清理源文件 (如果启用) ─────────────
    if clean_source:
        clean_source_directory(mod_name, override_path=override_path)
    # ───────────── 4.5. 强制全量备份 (Brute Force Backup) ─────────────
    # 策略变更：数据安全第一。在开始任何翻译前，强制将所有源文件读入内存并创建快照。
    # 即使是大 Mod，文本数据通常也不超过 50MB，内存不是瓶颈。
    
    source_result, total_files = _prepare_source_files(
        mod_name, game_profile, source_lang, override_path, progress_callback
    )
    all_files_content = source_result.files

    # Calculate Total Batches (Pre-calculation)
    effective_chunk_size = get_chunk_size_for_provider(selected_provider, batch_size_limit)
    total_batches = calculate_total_batches(all_files_content, effective_chunk_size)
    mod_id, version_id = create_source_snapshot(
        mod_name,
        all_files_content,
        total_files,
        total_batches,
        progress_callback,
        project_id,
    )
    if not mod_id or not version_id:
        raise RuntimeError("Failed to create the source archive snapshot.")

    # ───────────── 5. 多语言并行翻译 (Streaming from Memory) ─────────────
    
    last_target_lang = None
    reference_metrics = []
    for target_lang in target_languages:
        last_target_lang = target_lang
        reference_metrics.append(run_language_translation(
            mod_name=mod_name,
            source_lang=source_lang,
            target_lang=target_lang,
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
        ))

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
    )


def discover_files(mod_name: str, game_profile: dict, source_lang: dict, override_path: Optional[str] = None) -> List[dict]:
    return discover_localizable_files(
        mod_name,
        game_profile,
        source_lang,
        override_path,
        source_dir=SOURCE_DIR,
    )
