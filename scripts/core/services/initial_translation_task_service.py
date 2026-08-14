import logging
from typing import Any, Iterator, List, Optional

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.parallel_types import FileTask
from scripts.core.services.initial_translation_file_service import handle_empty_file
from scripts.core.services.initial_translation_progress_service import LanguageRunState, emit_progress
from scripts.app_settings import SOURCE_DIR, DEST_DIR


def build_file_task_iterator(
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
    version_id: Optional[int] = None,
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
                version_id=version_id,
                all_files_content=all_files_content,
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
            recovered_entries=file_data.get("recovered_entries", []),
        )
