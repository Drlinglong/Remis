import asyncio
import logging
from typing import Any, List, Optional

from scripts.core import file_parser
from scripts.core.archive_manager import archive_manager
from scripts.shared.services import project_manager
from scripts.app_settings import CHUNK_SIZE, GEMINI_CLI_CHUNK_SIZE, OLLAMA_CHUNK_SIZE


def read_files_for_backup(
    all_file_paths: List[dict],
    total_files: int,
    progress_callback: Optional[Any] = None,
) -> List[dict]:
    """Read source files once and attach parsed content for backup and translation."""
    logging.info("Reading all source files for backup...")
    all_files_content = []

    for idx, file_info in enumerate(all_file_paths):
        file_path = file_info["path"]
        if progress_callback:
            progress_callback(idx, total_files, file_info["filename"], "Reading Source")
        try:
            original_lines, texts_to_translate, key_map = file_parser.extract_translatable_content(file_path)
        except Exception as e:
            logging.error(f"Failed to parse file {file_path} for backup: {e}")
            logging.error("Aborting workflow due to file read error.")
            raise

        file_info["original_lines"] = original_lines
        file_info["texts_to_translate"] = texts_to_translate
        file_info["key_map"] = key_map
        all_files_content.append(file_info)

    return all_files_content


def get_chunk_size_for_provider(selected_provider: str, batch_size_limit: Optional[int] = None) -> int:
    if batch_size_limit:
        return max(1, int(batch_size_limit))
    if selected_provider == "gemini_cli":
        return GEMINI_CLI_CHUNK_SIZE
    if selected_provider == "ollama":
        return OLLAMA_CHUNK_SIZE
    return CHUNK_SIZE


def calculate_total_batches(all_files_content: List[dict], chunk_size: int) -> int:
    total_batches = 0
    for file_data in all_files_content:
        texts_to_translate = file_data.get("texts_to_translate", [])
        if not texts_to_translate:
            continue
        total_batches += (len(texts_to_translate) + chunk_size - 1) // chunk_size
    return total_batches


def resolve_archive_mod_name(mod_name: str, project_id: Optional[str] = None) -> str:
    archive_mod_name = mod_name
    if not project_id:
        return archive_mod_name

    try:
        project = asyncio.run(project_manager.get_project(project_id))
        if project:
            archive_mod_name = project["name"]
    except Exception as e:
        logging.error(f"Failed to fetch project name for archive: {e}")

    return archive_mod_name


def create_source_snapshot(
    mod_name: str,
    all_files_content: List[dict],
    total_files: int,
    total_batches: int,
    progress_callback: Optional[Any] = None,
    project_id: Optional[str] = None,
):
    archive_mod_name = resolve_archive_mod_name(mod_name, project_id)
    mod_id = archive_manager.get_or_create_mod_entry(archive_mod_name, f"local_{mod_name}")
    if not mod_id:
        logging.error("Failed to get/create mod entry in database. Aborting.")
        return None, None

    logging.info("Creating source version snapshot...")
    if progress_callback:
        progress_callback(0, total_files, "", "Creating Backup", total_batches=total_batches)

    version_id = archive_manager.create_source_version(mod_id, all_files_content)
    if not version_id:
        logging.error("Failed to create source version snapshot. Aborting workflow to prevent data loss.")
        return mod_id, None

    logging.info(f"Source snapshot created successfully (Version ID: {version_id}). Proceeding to translation.")
    return mod_id, version_id
