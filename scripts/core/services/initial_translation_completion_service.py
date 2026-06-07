import asyncio
import logging
from typing import List, Optional

from scripts.core import asset_handler
from scripts.core.services.initial_translation_progress_service import build_checkpoint_manager
from scripts.shared.services import project_manager
from scripts.utils import i18n


def sync_project_outputs(project_id: str, output_dir_path: str):
    """Register generated output folder and refresh project files."""
    try:
        logging.info(f"Automatically syncing project {project_id}...")
        asyncio.run(project_manager.add_translation_path(project_id, output_dir_path))
        asyncio.run(project_manager.refresh_project_files(project_id))
    except Exception as e:
        logging.error(f"Failed to auto-sync project: {e}")


def process_metadata_for_language(
    mod_name,
    handler,
    source_lang,
    target_lang,
    output_folder_name,
    mod_context,
    game_profile,
):
    try:
        asset_handler.process_metadata(
            mod_name,
            handler,
            source_lang,
            target_lang,
            output_folder_name,
            mod_context,
            game_profile,
        )
    except Exception as e:
        logging.exception(i18n.t("metadata_processing_failed", error=e))


def process_metadata_for_run(
    is_batch_mode: bool,
    mod_name: str,
    handler,
    source_lang: dict,
    primary_target_lang: dict,
    last_target_lang: dict,
    output_folder_name: str,
    mod_context: str,
    game_profile: dict,
):
    metadata_target_lang = primary_target_lang if is_batch_mode else last_target_lang
    process_metadata_for_language(
        mod_name,
        handler,
        source_lang,
        metadata_target_lang,
        output_folder_name,
        mod_context,
        game_profile,
    )


def clear_translation_checkpoints(
    output_dir_path: str,
    selected_provider: str,
    model_name: Optional[str],
    source_lang: dict,
    target_languages: List[dict],
):
    """Clear per-language checkpoints after a successful workflow run."""
    for target_lang in target_languages:
        checkpoint_manager = build_checkpoint_manager(
            output_dir_path,
            selected_provider,
            model_name,
            source_lang,
            target_lang,
            use_resume=True,
        )
        checkpoint_manager.clear_checkpoint()


def finalize_workflow_run(
    is_batch_mode: bool,
    mod_name: str,
    handler,
    source_lang: dict,
    primary_target_lang: dict,
    last_target_lang: dict,
    output_folder_name: str,
    mod_context: str,
    game_profile: dict,
    output_dir_path: str,
    selected_provider: str,
    model_name: Optional[str],
    target_languages: List[dict],
    project_id: Optional[str],
):
    """Run metadata, cleanup checkpoints, and sync project outputs for the workflow."""
    process_metadata_for_run(
        is_batch_mode,
        mod_name,
        handler,
        source_lang,
        primary_target_lang,
        last_target_lang,
        output_folder_name,
        mod_context,
        game_profile,
    )
    clear_translation_checkpoints(output_dir_path, selected_provider, model_name, source_lang, target_languages)
    logging.info(i18n.t("translation_workflow_completed"))
    logging.info(i18n.t("output_folder_created", folder=output_folder_name))
    if project_id:
        sync_project_outputs(project_id, output_dir_path)
