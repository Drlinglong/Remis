import logging
import threading
from typing import Any, List, Optional

from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.proofreading_tracker import create_proofreading_tracker
from scripts.core.services.initial_translation_batch_service import (
    classify_batch_warnings,
    log_batch_warnings,
    log_recovered_retries,
    resolve_max_workers,
    temporary_rpm_limit,
)
from scripts.core.services.initial_translation_file_service import finalize_translated_file
from scripts.core.services.initial_translation_postprocess_service import finalize_language_run
from scripts.core.services.initial_translation_progress_service import (
    LanguageRunState,
    build_checkpoint_manager,
    build_progress_emitter,
    progress_log_bridge,
)
from scripts.core.services.initial_translation_task_service import build_file_task_iterator
from scripts.core.services.initial_translation_workshop_service import (
    export_workshop_issues_for_language,
    run_embedded_workshop_for_language,
)
from scripts.core.services.vanilla_reference_factory import create_reference_resolver
from scripts.utils import i18n


def _batch_entry_indices(batch_task) -> list[int]:
    indices = list(batch_task.file_task.translation_entry_indices)
    if len(indices) != len(batch_task.file_task.texts_to_translate):
        indices = list(range(len(batch_task.file_task.texts_to_translate)))
    return indices[batch_task.start_index:batch_task.end_index]


def _batch_checkpoint_identity(batch_task) -> str:
    return (batch_task.file_task.file_path or batch_task.file_task.filename).replace("\\", "/")


def _restore_checkpoint_batch(checkpoint_manager, batch_task) -> bool:
    if (
        not getattr(checkpoint_manager, "resume_enabled", True)
        or not hasattr(checkpoint_manager, "restore_batch")
    ):
        return False
    restored = checkpoint_manager.restore_batch(
        _batch_checkpoint_identity(batch_task),
        batch_index=batch_task.batch_index,
        start_index=batch_task.start_index,
        end_index=batch_task.end_index,
        source_texts=list(batch_task.texts),
        source_entry_indices=_batch_entry_indices(batch_task),
    )
    if restored is None:
        return False
    batch_task.translated_texts = restored["translated_texts"]
    batch_task.warnings = restored["warnings"]
    batch_task.resumed_from_checkpoint = True
    return True


def _persist_checkpoint_batch(checkpoint_manager, batch_task, progress_metadata) -> None:
    if (
        batch_task.failed
        or batch_task.fell_back_to_source
        or not getattr(checkpoint_manager, "resume_enabled", True)
        or not hasattr(checkpoint_manager, "mark_batch_completed")
    ):
        return
    checkpoint_manager.mark_batch_completed(
        _batch_checkpoint_identity(batch_task),
        batch_index=batch_task.batch_index,
        start_index=batch_task.start_index,
        end_index=batch_task.end_index,
        source_texts=list(batch_task.texts),
        source_entry_indices=_batch_entry_indices(batch_task),
        translated_texts=list(batch_task.translated_texts or []),
        warnings=list(batch_task.warnings or []),
        progress_metadata=progress_metadata,
    )


def _process_file_tasks(
    *,
    processor: ParallelProcessor,
    file_task_generator: Any,
    handler: Any,
    progress_lock: threading.Lock,
    run_state: LanguageRunState,
    update_progress: Any,
    rpm_limit: Optional[int],
    target_lang: dict,
    output_folder_name: str,
    game_profile: dict,
    proofreading_tracker: Any,
    checkpoint_manager: Any,
    project_id: Optional[str],
    version_id: Optional[int],
    all_files_content: List[dict],
    total_batches: int,
    should_cancel: Optional[Any] = None,
) -> None:
    def translation_wrapper(batch_task):
        if _restore_checkpoint_batch(checkpoint_manager, batch_task):
            return batch_task
        return handler.translate_batch(batch_task)

    def on_batch_completed(batch_task):
        resumed = bool(getattr(batch_task, "resumed_from_checkpoint", False))
        if not resumed:
            with progress_lock:
                run_state.completed_batches += 1
                if batch_task.failed or batch_task.fell_back_to_source:
                    run_state.failed_batches += 1
                else:
                    run_state.successful_batches += 1
                progress_metadata = {
                    **run_state.checkpoint_progress(),
                    "total_batches": total_batches,
                }
            _persist_checkpoint_batch(checkpoint_manager, batch_task, progress_metadata)
        update_progress(batch_task.file_task.filename)

    with temporary_rpm_limit(rpm_limit):
        with progress_log_bridge(update_progress):
            stream_options = {"batch_progress_callback": on_batch_completed}
            if should_cancel is not None:
                stream_options["should_cancel"] = should_cancel
            for file_task, translated_texts, warnings, is_failed in processor.process_files_stream(
                file_task_generator,
                translation_wrapper,
                **stream_options,
            ):
                classification = classify_batch_warnings(
                    file_task.filename,
                    warnings,
                    file_succeeded=not is_failed,
                )
                run_state.glossary_issues += len(classification.glossary_evidence)
                evidence_capacity = max(0, 100 - len(run_state.glossary_issue_details))
                run_state.glossary_issue_details.extend(classification.glossary_evidence[:evidence_capacity])
                run_state.recovered_retries += len(classification.recovered_retries)
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
                log_recovered_retries(file_task.filename, classification.recovered_retries)
                log_batch_warnings(file_task.filename, classification.final_warnings)
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
                    progress_metadata=run_state.checkpoint_progress(),
                )


def _build_parallel_processor(max_workers, chunk_size, source_context_overlap, context_selection):
    processor_kwargs = {"max_workers": max_workers, "chunk_size_override": chunk_size}
    if source_context_overlap:
        processor_kwargs["source_context_overlap"] = source_context_overlap
    if context_selection is not None:
        processor_kwargs["context_selector"] = context_selection
    return ParallelProcessor(**processor_kwargs)


def _prepare_reference_run(reference_reuse, game_profile, source_lang, target_lang):
    resolver = create_reference_resolver(
        reference_reuse,
        game_profile=game_profile,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    return resolver, [], {"model_submitted": 0}


def _finalize_language_translation(
    *, mod_name, game_profile, target_lang, source_lang, output_folder_name,
    proofreading_tracker, update_progress, override_path, output_dir_path,
    project_id, embedded_workshop, reference_protected_entries,
    reference_resolver, reference_run_metrics, selected_provider, model_name,
    concurrency_limit, batch_size_limit, rpm_limit, provider_runtime,
) -> dict:
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
    workshop_config = dict(embedded_workshop or {})
    workshop_config["protected_entries"] = reference_protected_entries
    run_embedded_workshop_for_language(
        workshop_config,
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
        provider_runtime=provider_runtime,
    )
    reference_metrics = (
        reference_resolver.metrics()
        if reference_resolver is not None
        else {"reference_enabled": False, "reference_matched": 0, "api_skipped": 0}
    )
    reference_metrics["target_lang"] = target_lang.get("code")
    reference_metrics.update(reference_run_metrics)
    logging.info("Vanilla reference reuse metrics: %s", reference_metrics)
    return reference_metrics


def run_language_translation(
    *,
    mod_name: str, source_lang: dict, target_lang: dict,
    game_profile: dict, mod_context: str, handler: Any,
    output_folder_name: str, output_dir_path: str,
    selected_provider: str, model_name: Optional[str],
    all_files_content: List[dict], total_batches: int,
    effective_chunk_size: int, progress_callback: Optional[Any],
    project_id: Optional[str], version_id: Optional[int],
    override_path: Optional[str], use_resume: bool,
    concurrency_limit: Optional[int], rpm_limit: Optional[int],
    batch_size_limit: Optional[int], embedded_workshop: Optional[dict],
    reference_reuse: Optional[dict] = None,
    source_context_overlap: int = 0,
    context_selection: Optional[Any] = None, provider_runtime: Any = None,
    should_cancel: Optional[Any] = None, task_id: Optional[str] = None,
    run_id: Optional[str] = None, source_root: Optional[str] = None,
    source_snapshot_hash: Optional[str] = None,
    config_fingerprint: Optional[str] = None,
) -> dict:
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
        use_resume, context_metadata=context_selection.metadata if context_selection else None,
        task_id=task_id,
        run_id=run_id,
        project_id=project_id,
        source_root=source_root,
        source_snapshot_hash=source_snapshot_hash,
        config_fingerprint=config_fingerprint,
        provider_runtime=provider_runtime,
    )
    run_state = LanguageRunState.from_checkpoint(checkpoint_manager)
    progress_lock = threading.Lock()
    (
        reference_resolver,
        reference_protected_entries,
        reference_run_metrics,
    ) = _prepare_reference_run(
        reference_reuse, game_profile, source_lang, target_lang
    )
    update_progress = build_progress_emitter(progress_callback, run_state, total_batches)
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
        total_batches, version_id,
        reference_resolver=reference_resolver,
        reference_protected_entries=reference_protected_entries,
        reference_run_metrics=reference_run_metrics,
    )
    max_workers = resolve_max_workers(concurrency_limit, selected_provider)
    processor = _build_parallel_processor(
        max_workers,
        effective_chunk_size,
        source_context_overlap,
        context_selection,
    )
    _process_file_tasks(
        processor=processor,
        file_task_generator=file_task_generator,
        handler=handler,
        progress_lock=progress_lock,
        run_state=run_state,
        update_progress=update_progress,
        rpm_limit=rpm_limit,
        target_lang=target_lang,
        output_folder_name=output_folder_name,
        game_profile=game_profile,
        proofreading_tracker=proofreading_tracker,
        checkpoint_manager=checkpoint_manager,
        project_id=project_id,
        version_id=version_id,
        all_files_content=all_files_content,
        total_batches=total_batches,
        should_cancel=should_cancel,
    )
    if run_state.error_count:
        message = f"Translation failed for {run_state.error_count} file(s) while translating to {target_lang['name']}."
        logging.error(message)
        raise RuntimeError(message)

    return _finalize_language_translation(
        mod_name=mod_name,
        game_profile=game_profile,
        target_lang=target_lang,
        source_lang=source_lang,
        output_folder_name=output_folder_name,
        proofreading_tracker=proofreading_tracker,
        update_progress=update_progress,
        override_path=override_path,
        output_dir_path=output_dir_path,
        project_id=project_id,
        embedded_workshop=embedded_workshop,
        reference_protected_entries=reference_protected_entries,
        reference_resolver=reference_resolver,
        reference_run_metrics=reference_run_metrics,
        selected_provider=selected_provider,
        model_name=model_name,
        concurrency_limit=concurrency_limit,
        batch_size_limit=batch_size_limit,
        rpm_limit=rpm_limit,
        provider_runtime=provider_runtime,
    )
