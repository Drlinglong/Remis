import asyncio
import logging
import os
from typing import Any, List, Optional

from scripts.core import file_builder
from scripts.core.archive_manager import archive_manager
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.parallel_types import FileTask
from scripts.shared.services import project_manager
from scripts.app_settings import DEST_DIR, LANGUAGES, SOURCE_DIR
from scripts.utils import i18n


def sync_project_file_status(source_file_path: str):
    """Mark a file as complete in the project database."""
    try:
        import uuid

        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_file_path.lower().replace('\\', '/')))
        asyncio.run(project_manager.repository.update_file_status_by_id(file_id, 'done'))
    except Exception as e:
        logging.error(f"Failed to update DB status for {os.path.basename(source_file_path)}: {e}")


def build_dest_dir(file_task: FileTask, target_lang: dict, output_folder_name: str, game_profile: dict) -> str:
    """Build the destination directory while preserving module and language-folder structure."""
    known_lang_folders = set()
    for lang_def in LANGUAGES.values():
        if "name_en" in lang_def:
            known_lang_folders.add(lang_def["name_en"].lower())
        if "key" in lang_def:
            known_lang_folders.add(lang_def["key"][2:].lower())
        known_lang_folders.add("english")

    if file_task.file_path:
        relative_parts = [part for part in file_task.file_path.replace("\\", "/").split("/") if part]
        dir_parts = relative_parts[:-1] if relative_parts else []
        target_folder = target_lang["key"][2:]

        if file_task.is_custom_loc:
            rel_after_custom_root = dir_parts[1:] if dir_parts and dir_parts[0].lower() == "customizable_localization" else dir_parts
            return os.path.join(
                DEST_DIR,
                output_folder_name,
                "customizable_localization",
                target_folder,
                *rel_after_custom_root,
            )

        replaced_lang_folder = False
        for index, part in enumerate(dir_parts):
            if part.lower() in known_lang_folders:
                dir_parts[index] = target_folder
                replaced_lang_folder = True
                break

        if not replaced_lang_folder:
            source_loc_folder = game_profile["source_localization_folder"]
            for index, part in enumerate(dir_parts):
                if part.lower() == source_loc_folder.lower():
                    dir_parts.insert(index + 1, target_folder)
                    replaced_lang_folder = True
                    break

        if not replaced_lang_folder:
            dir_parts.insert(0, target_folder)

        return os.path.join(DEST_DIR, output_folder_name, *dir_parts)

    if file_task.is_custom_loc:
        cust_loc_root = os.path.join(SOURCE_DIR, file_task.mod_name, "customizable_localization")
        rel = os.path.relpath(file_task.root, cust_loc_root)
        return os.path.join(
            DEST_DIR,
            output_folder_name,
            "customizable_localization",
            target_lang["key"][2:],
            rel,
        )

    if file_task.loc_root:
        rel_from_loc_root = os.path.relpath(file_task.root, file_task.loc_root)
        parts = rel_from_loc_root.split(os.sep)

        if parts and parts[0].lower() in known_lang_folders:
            parts[0] = target_lang["key"][2:]
        else:
            if parts[0] == ".":
                parts = [target_lang["key"][2:]]
            else:
                parts.insert(0, target_lang["key"][2:])

        new_rel_path = os.path.join(*parts)
        mod_root = os.path.join(SOURCE_DIR, file_task.mod_name)
        module_rel_path = os.path.relpath(file_task.loc_root, mod_root)
        return os.path.join(DEST_DIR, output_folder_name, module_rel_path, new_rel_path)

    source_loc_folder = game_profile["source_localization_folder"]
    source_loc_path = os.path.join(SOURCE_DIR, file_task.mod_name, source_loc_folder)

    if file_task.root.startswith(source_loc_path):
        rel = os.path.relpath(file_task.root, source_loc_path)
    else:
        rel = os.path.basename(file_task.root)

    parts = rel.split(os.sep)
    if parts and parts[0].lower() in known_lang_folders:
        parts[0] = target_lang["key"][2:]
        rel = os.path.join(*parts)
    else:
        rel = os.path.join(target_lang["key"][2:], rel)

    return os.path.join(DEST_DIR, output_folder_name, source_loc_folder, rel)


def handle_empty_file(
    file_info,
    original_lines,
    texts,
    key_map,
    source_lang,
    target_lang,
    game_profile,
    output_folder_name,
    mod_name,
    proofreading_tracker,
):
    temp_task = FileTask(
        filename=file_info["filename"],
        root=file_info["root"],
        original_lines=original_lines,
        texts_to_translate=texts,
        key_map=key_map,
        is_custom_loc=file_info["is_custom_loc"],
        target_lang=target_lang,
        source_lang=source_lang,
        game_profile=game_profile,
        mod_context="",
        provider_name="",
        output_folder_name=output_folder_name,
        source_dir=SOURCE_DIR,
        dest_dir=DEST_DIR,
        client=None,
        mod_name=mod_name,
        loc_root=file_info.get("loc_root", ""),
        file_path=file_info.get("file_path", file_info["filename"]),
    )
    dest_dir = build_dest_dir(temp_task, target_lang, output_folder_name, game_profile)
    os.makedirs(dest_dir, exist_ok=True)

    source_file_path = os.path.join(file_info["root"], file_info["filename"])
    dest_file_path = file_builder.create_fallback_file(
        source_file_path,
        dest_dir,
        file_info["filename"],
        source_lang,
        target_lang,
        game_profile,
    )

    if dest_file_path:
        proofreading_tracker.add_file_info({
            'source_path': source_file_path,
            'dest_path': dest_file_path,
            'translated_lines': 0,
            'filename': file_info["filename"],
            'is_custom_loc': file_info["is_custom_loc"]
        })


def finalize_translated_file(
    file_task: FileTask,
    translated_texts: List[str],
    is_failed: bool,
    target_lang: dict,
    output_folder_name: str,
    game_profile: dict,
    proofreading_tracker: Any,
    checkpoint_manager: CheckpointManager,
    project_id: Optional[str],
    version_id: Optional[int],
    all_files_content: List[dict],
):
    """Write translated content, update trackers, and archive the result."""
    dest_dir = build_dest_dir(file_task, target_lang, output_folder_name, game_profile)
    os.makedirs(dest_dir, exist_ok=True)

    dest_file_path = file_builder.rebuild_and_write_file(
        file_task.original_lines,
        file_task.texts_to_translate,
        translated_texts,
        file_task.key_map,
        dest_dir,
        file_task.filename,
        file_task.source_lang,
        file_task.target_lang,
        file_task.game_profile,
    )

    source_file_path = os.path.join(file_task.root, file_task.filename)
    if dest_file_path:
        proofreading_tracker.add_file_info({
            'source_path': source_file_path,
            'dest_path': dest_file_path,
            'translated_lines': len(translated_texts),
            'filename': file_task.filename,
            'is_custom_loc': file_task.is_custom_loc,
            'translation_failed': is_failed,
        })
        logging.info(i18n.t("file_build_completed", filename=os.path.basename(dest_file_path)))

    if not is_failed:
        checkpoint_manager.mark_file_completed(file_task.filename)

    if project_id and not is_failed:
        sync_project_file_status(source_file_path)

    if version_id and not is_failed:
        try:
            archive_manager.archive_translated_results(
                version_id,
                {file_task.file_path or file_task.filename: translated_texts},
                all_files_content,
                target_lang.get("code")
            )
        except Exception as e:
            logging.error(f"Failed to archive results for {file_task.filename}: {e}")
