import logging
import threading
from typing import Any, Optional, List, Iterator

from scripts.core.proofreading_tracker import create_proofreading_tracker
from scripts.core.parallel_types import FileTask
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.services.initial_translation_discovery_service import discover_localizable_files
from scripts.core.services.initial_translation_file_service import (
    finalize_translated_file,
    handle_empty_file,
)
from scripts.core.services.initial_translation_completion_service import finalize_workflow_run
from scripts.core.services.initial_translation_progress_service import (
    LanguageRunState,
    build_checkpoint_manager,
    emit_progress,
    progress_log_bridge,
)
from scripts.core.services.initial_translation_postprocess_service import finalize_language_run
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
from scripts.core.services.initial_translation_workshop_service import (
    export_workshop_issues_for_language,
    run_embedded_workshop_for_language,
)
from scripts.core.services.initial_translation_batch_service import (
    log_batch_warnings,
    resolve_max_workers,
    temporary_rpm_limit,
)
from scripts.core.services.initial_translation_workspace_service import (
    clean_source_directory,
    load_glossaries_for_run,
    prepare_output_workspace,
)
from scripts.app_settings import SOURCE_DIR, DEST_DIR
from scripts.utils import i18n


def _build_file_task_iterator(
    all_files_content: List[dict],
    checkpoint_manager: CheckpointManager,
    source_lang: dict,
    target_lang: dict,
    game_profile: dict,
    mod_context: str,
    handler: Any,
    output_folder_name: str,
    mod_name: str,
    proofreading_tracker: Any,
    progress_callback: Optional[Any],
    run_state: LanguageRunState,
    total_batches: int,
) -> Iterator[FileTask]:
    for file_data in all_files_content:
        if checkpoint_manager.is_file_completed(file_data["filename"]):
            logging.info(f"Skipping completed file: {file_data['filename']}")
            continue

        texts = file_data["texts_to_translate"]
        original_lines = file_data["original_lines"]
        key_map = file_data["key_map"]

        if not texts:
            handle_empty_file(
                file_data,
                original_lines,
                texts,
                key_map,
                source_lang,
                target_lang,
                game_profile,
                output_folder_name,
                mod_name,
                proofreading_tracker,
            )
            checkpoint_manager.mark_file_completed(file_data["filename"])
            emit_progress(
                progress_callback,
                run_state,
                total_batches,
                file_data["filename"],
                log_message=f"Skipped empty file: {file_data['filename']}",
            )
            continue

        yield FileTask(
            filename=file_data["filename"],
            root=file_data["root"],
            original_lines=original_lines,
            texts_to_translate=texts,
            key_map=key_map,
            is_custom_loc=file_data["is_custom_loc"],
            target_lang=target_lang,
            source_lang=source_lang,
            game_profile=game_profile,
            mod_context=mod_context,
            provider_name=handler.provider_name,
            output_folder_name=output_folder_name,
            source_dir=SOURCE_DIR,
            dest_dir=DEST_DIR,
            client=handler.client,
            mod_name=mod_name,
            loc_root=file_data.get("loc_root", ""),
            file_path=file_data.get("file_path", file_data["filename"]),
        )

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
        embedded_workshop: Optional[dict] = None):
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
    gemini_cli_model = resolve_provider_model(selected_provider, model_name)
    handler = create_translation_handler(selected_provider, gemini_cli_model)
    if not handler:
        return

    # ───────────── 2.5. 加载词典 ─────────────
    game_id = game_profile.get("id", "")
    load_glossaries_for_run(game_id, use_glossary, selected_glossary_ids)

    # ───────────── 3. 创建输出目录 & 初始化断点管理器 ─────────────
    output_dir_path = prepare_output_workspace(mod_name, output_folder_name, game_profile)
    
    # ───────────── 3.5. [NEW] 清理源文件 (如果启用) ─────────────
    if clean_source:
        clean_source_directory(mod_name, override_path=override_path)

    # ───────────── 4. 发现所有源文件 (Discovery Phase) ─────────────
    all_file_paths = discover_files(mod_name, game_profile, source_lang, override_path=override_path)

    if not all_file_paths:
        logging.warning(i18n.t("no_localisable_files_found", lang_name=source_lang['name']))
        return

    # Update progress total
    total_files = len(all_file_paths)
    if progress_callback:
        progress_callback(0, total_files, "", "Analyzing Files")

    # ───────────── 4.5. 强制全量备份 (Brute Force Backup) ─────────────
    # 策略变更：数据安全第一。在开始任何翻译前，强制将所有源文件读入内存并创建快照。
    # 即使是大 Mod，文本数据通常也不超过 50MB，内存不是瓶颈。
    
    try:
        all_files_content = read_files_for_backup(all_file_paths, total_files, progress_callback)
    except Exception:
        return

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
        return

    # ───────────── 5. 多语言并行翻译 (Streaming from Memory) ─────────────
    
    for target_lang in target_languages:
        logging.info(i18n.t("translating_to_language", lang_name=target_lang["name"]))
        
        proofreading_tracker = create_proofreading_tracker(
            mod_name, output_folder_name, target_lang.get("code", "zh-CN")
        )

        checkpoint_manager = build_checkpoint_manager(
            output_dir_path,
            selected_provider,
            gemini_cli_model,
            source_lang,
            target_lang,
            use_resume,
        )
        run_state = LanguageRunState()
        progress_lock = threading.Lock()

        def update_progress(current_file_name="", stage="Translating", log_message=None, format_issues_override=None, format_repair=None, workshop_progress=None):
            emit_progress(
                progress_callback,
                run_state,
                total_batches,
                current_file_name,
                stage,
                log_message,
                format_issues_override,
                format_repair,
                workshop_progress,
            )

        file_task_generator = _build_file_task_iterator(
            all_files_content,
            checkpoint_manager,
            source_lang,
            target_lang,
            game_profile,
            mod_context,
            handler,
            output_folder_name,
            mod_name,
            proofreading_tracker,
            progress_callback,
            run_state,
            total_batches,
        )

        # 初始化并行处理器
        max_workers = resolve_max_workers(concurrency_limit, selected_provider)
        processor = ParallelProcessor(max_workers=max_workers, chunk_size_override=effective_chunk_size)

        # 定义翻译函数 (Consumer)
        def translation_wrapper(batch_task):
            result = handler.translate_batch(batch_task)
            with progress_lock:
                run_state.completed_batches += 1
                update_progress(batch_task.file_task.filename)
            return result

        with temporary_rpm_limit(rpm_limit):
            with progress_log_bridge(update_progress):
                for file_task, translated_texts, warnings, is_failed in processor.process_files_stream(file_task_generator, translation_wrapper):
                    if is_failed:
                        run_state.error_count += 1
                        logging.error(f"File {file_task.filename} failed to translate (partially or fully). Using fallback.")
                        update_progress(file_task.filename, "Failed", log_message=f"ERROR: File {file_task.filename} failed to translate. Rolled back to original text.")
                    else:
                        update_progress(file_task.filename, log_message=f"SUCCESS: {file_task.filename} translated.")

                    log_batch_warnings(file_task.filename, warnings)

                    finalize_translated_file(
                        file_task,
                        translated_texts,
                        is_failed,
                        target_lang,
                        output_folder_name,
                        game_profile,
                        proofreading_tracker,
                        checkpoint_manager,
                        project_id,
                        version_id,
                        all_files_content,
                    )

        if run_state.error_count:
            message = f"Translation failed for {run_state.error_count} file(s) while translating to {target_lang['name']}."
            logging.error(message)
            raise RuntimeError(message)

        dynamic_valid_tags = finalize_language_run(
            mod_name,
            game_profile,
            target_lang,
            source_lang,
            output_folder_name,
            proofreading_tracker,
            update_progress,
            override_path=override_path,
        )
        export_workshop_issues_for_language(
            output_dir_path,
            override_path,
            mod_name,
            project_id,
            source_lang,
            target_lang,
            game_profile,
            dynamic_valid_tags=dynamic_valid_tags,
        )
        run_embedded_workshop_for_language(
            embedded_workshop,
            output_dir_path,
            override_path,
            mod_name,
            project_id,
            source_lang,
            target_lang,
            game_profile,
            selected_provider,
            gemini_cli_model,
            concurrency_limit=concurrency_limit,
            batch_size_limit=batch_size_limit,
            rpm_limit=rpm_limit,
            dynamic_valid_tags=dynamic_valid_tags,
            update_progress_callback=update_progress,
        )

    finalize_workflow_run(
        run_plan.is_batch_mode,
        mod_name,
        handler,
        source_lang,
        primary_target_lang,
        target_lang,
        output_folder_name,
        mod_context,
        game_profile,
        output_dir_path,
        selected_provider,
        gemini_cli_model,
        target_languages,
        project_id,
    )


def discover_files(mod_name: str, game_profile: dict, source_lang: dict, override_path: Optional[str] = None) -> List[dict]:
    return discover_localizable_files(
        mod_name,
        game_profile,
        source_lang,
        override_path,
        source_dir=SOURCE_DIR,
    )
