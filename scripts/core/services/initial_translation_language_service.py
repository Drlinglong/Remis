import logging
import threading
from typing import Any, List, Optional

from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.proofreading_tracker import create_proofreading_tracker
from scripts.core.services.initial_translation_batch_service import (
    log_batch_warnings,
    resolve_max_workers,
    temporary_rpm_limit,
)
from scripts.core.services.initial_translation_file_service import finalize_translated_file
from scripts.core.services.initial_translation_postprocess_service import finalize_language_run
from scripts.core.services.initial_translation_progress_service import (
    LanguageRunState,
    build_checkpoint_manager,
    emit_progress,
    progress_log_bridge,
)
from scripts.core.services.initial_translation_task_service import build_file_task_iterator
from scripts.core.services.initial_translation_workshop_service import (
    export_workshop_issues_for_language,
    run_embedded_workshop_for_language,
)
from scripts.utils import i18n


def run_language_translation(
    *,
    mod_name: str,
    source_lang: dict,
    target_lang: dict,
    game_profile: dict,
    mod_context: str,
    handler: Any,
    output_folder_name: str,
    output_dir_path: str,
    selected_provider: str,
    model_name: Optional[str],
    all_files_content: List[dict],
    total_batches: int,
    effective_chunk_size: int,
    progress_callback: Optional[Any],
    project_id: Optional[str],
    version_id: Optional[int],
    override_path: Optional[str],
    use_resume: bool,
    concurrency_limit: Optional[int],
    rpm_limit: Optional[int],
    batch_size_limit: Optional[int],
    embedded_workshop: Optional[dict],
    source_context_overlap: int = 0,
) -> None:
    logging.info(i18n.t("translating_to_language", lang_name=target_lang["name"]))

    proofreading_tracker = create_proofreading_tracker(
        mod_name, output_folder_name, target_lang.get("code", "zh-CN")
    )

    checkpoint_manager = build_checkpoint_manager(
        output_dir_path,
        selected_provider,
        model_name,
        source_lang,
        target_lang,
        use_resume,
    )
    run_state = LanguageRunState()
    progress_lock = threading.Lock()

    def update_progress(
        current_file_name="",
        stage="Translating",
        log_message=None,
        format_issues_override=None,
        format_repair=None,
        workshop_progress=None,
    ):
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

    file_task_generator = build_file_task_iterator(
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

    max_workers = resolve_max_workers(concurrency_limit, selected_provider)
    processor = ParallelProcessor(max_workers=max_workers, chunk_size_override=effective_chunk_size, source_context_overlap=source_context_overlap)
    def translation_wrapper(batch_task):
        result = handler.translate_batch(batch_task)
        with progress_lock:
            run_state.completed_batches += 1
            update_progress(batch_task.file_task.filename)
        return result

    with temporary_rpm_limit(rpm_limit):
        with progress_log_bridge(update_progress):
            for file_task, translated_texts, warnings, is_failed in processor.process_files_stream(
                file_task_generator,
                translation_wrapper,
            ):
                if is_failed:
                    run_state.error_count += 1
                    logging.error(f"File {file_task.filename} failed to translate (partially or fully). Using fallback.")
                    update_progress(
                        file_task.filename,
                        "Failed",
                        log_message=f"ERROR: File {file_task.filename} failed to translate. Rolled back to original text.",
                    )
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
        model_name,
        concurrency_limit=concurrency_limit,
        batch_size_limit=batch_size_limit,
        rpm_limit=rpm_limit,
        dynamic_valid_tags=dynamic_valid_tags,
        update_progress_callback=update_progress,
    )
