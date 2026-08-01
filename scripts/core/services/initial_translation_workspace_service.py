import asyncio
import logging
import os
import shutil
from typing import Optional, List

from scripts.core import asset_handler, directory_handler
from scripts.core.glossary_manager import glossary_manager
from scripts.app_settings import SOURCE_DIR, DEST_DIR


def load_glossaries_for_run(game_id: str, use_glossary: bool, selected_glossary_ids: Optional[List[int]] = None):
    """Load glossary state before translation begins."""
    if not use_glossary:
        asyncio.run(glossary_manager.load_selected_glossaries([]))
        return
    if not game_id:
        return

    if selected_glossary_ids:
        asyncio.run(glossary_manager.load_selected_glossaries(selected_glossary_ids))
    else:
        asyncio.run(glossary_manager.load_game_glossary(game_id))


def prepare_output_workspace(mod_name: str, output_folder_name: str, game_profile: dict) -> str:
    """Create output directories and copy static assets for a run."""
    directory_handler.create_output_structure(mod_name, output_folder_name, game_profile)
    asset_handler.copy_assets(mod_name, output_folder_name, game_profile)
    return os.path.join(DEST_DIR, output_folder_name)


def clean_source_directory(mod_name: str, override_path: Optional[str] = None):
    """Delete non-localization source files after setup when clean_source is enabled."""
    logging.info("Cleaning source directory to save disk space (keeping only localization and metadata)...")
    mod_root_path = override_path if override_path else os.path.join(SOURCE_DIR, mod_name)
    whitelist_folders = {"localisation", "localization", "customizable_localization"}
    whitelist_files = {"descriptor.mod", "thumbnail.png", "thumbnail.jpg", "metadata.json", "remote_file_id.txt"}

    files_removed = 0
    folders_removed = 0
    bytes_freed = 0

    for item_name in os.listdir(mod_root_path):
        item_path = os.path.join(mod_root_path, item_name)
        item_lower = item_name.lower()

        if os.path.isdir(item_path):
            if item_lower in whitelist_folders:
                continue
            try:
                folder_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(item_path) for f in fns)
                shutil.rmtree(item_path)
                folders_removed += 1
                bytes_freed += folder_size
                logging.debug(f"Deleted directory: {item_name}")
            except OSError as e:
                logging.warning(f"Failed to delete directory {item_name}: {e}")
        else:
            if item_lower in whitelist_files:
                continue
            try:
                file_size = os.path.getsize(item_path)
                os.remove(item_path)
                files_removed += 1
                bytes_freed += file_size
                logging.debug(f"Deleted file: {item_name}")
            except OSError as e:
                logging.warning(f"Failed to delete file {item_name}: {e}")

    logging.info(
        "Clean Source: Removed %s folders and %s files, freed %.2f MB.",
        folders_removed,
        files_removed,
        bytes_freed / 1024 / 1024,
    )
