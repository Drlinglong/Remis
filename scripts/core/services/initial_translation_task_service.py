import logging
from typing import Any, Iterator, List, Optional

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.parallel_types import FileTask
from scripts.core.vic3_country_adjective_context import build_file_hints
from scripts.core.services.initial_translation_file_service import handle_empty_file
from scripts.core.services.initial_translation_progress_service import LanguageRunState, emit_progress
from scripts.app_settings import SOURCE_DIR, DEST_DIR


def _key_info_at(key_map: Any, index: int) -> Any:
    if isinstance(key_map, dict):
        return key_map.get(index)
    if isinstance(key_map, list) and index < len(key_map):
        return key_map[index]
    return None


def _reference_key(key_info: dict) -> str:
    entry = key_info.get("entry")
    return getattr(entry, "base_key", None) or key_info.get("key_part", "")


def _split_reference_hits(texts, key_map, reference_resolver, source_file=""):
    if reference_resolver is None:
        return list(texts), list(range(len(texts))), {}

    model_texts = []
    model_positions = []
    reference_translations = {}
    for index, source_text in enumerate(texts):
        key_info = key_map[index]
        match = reference_resolver.lookup(
            _reference_key(key_info),
            source_text,
            source_file,
        )
        if match.hit:
            reference_translations[index] = match.translation
            continue
        model_positions.append(index)
        model_texts.append(source_text)
    return model_texts, model_positions, reference_translations


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
    reference_resolver: Optional[Any] = None,
    reference_protected_entries: Optional[List[dict]] = None,
    reference_run_metrics: Optional[dict] = None,
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

        all_semantic_hints = build_file_hints(
            game_id=game_profile.get("id", ""),
            target_lang=target_lang.get("code", ""),
            texts=texts,
            key_infos=(_key_info_at(key_map, index) for index in range(len(texts))),
        )

        source_file = file_data.get("file_path", file_data["filename"])
        model_texts, model_positions, reference_translations = _split_reference_hits(
            texts,
            key_map,
            reference_resolver,
            source_file,
        )
        if reference_run_metrics is not None:
            reference_run_metrics["model_submitted"] = (
                reference_run_metrics.get("model_submitted", 0) + len(model_texts)
            )
        if reference_protected_entries is not None:
            for position in reference_translations:
                reference_protected_entries.append({
                    "source_file": source_file,
                    "key": _reference_key(key_map[position]),
                })
        semantic_hints = [all_semantic_hints[position] for position in model_positions]

        yield FileTask(
            filename=file_data["filename"],
            root=file_data["root"],
            original_lines=original_lines,
            texts_to_translate=model_texts,
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
            semantic_hints=semantic_hints,
            all_source_texts=list(texts),
            all_key_map=(
                dict(enumerate(key_map))
                if isinstance(key_map, list)
                else dict(key_map)
            ),
            model_result_positions=model_positions,
            reference_translations=reference_translations,
        )
