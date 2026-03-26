import logging
import os
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from time import perf_counter

from scripts.app_settings import DEST_DIR
from scripts.core import api_handler
from scripts.shared.services import project_manager
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_build_service import IncrementalBuildService
from scripts.core.services.incremental_archive_service import IncrementalArchiveService
from scripts.core.services.incremental_package_service import IncrementalPackageService
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.incremental_translation_service import IncrementalTranslationService

logger = logging.getLogger(__name__)

async def run_incremental_update(
    project_id: str, 
    target_lang_infos: List[Dict[str, Any]], 
    source_lang_info: Dict[str, Any],
    game_profile: Dict[str, Any],
    selected_provider: str = "gemini",
    model_name: Optional[str] = None,
    concurrency_limit: Optional[int] = None,
    rpm_limit: Optional[int] = None,
    mod_context: str = "",
    dry_run: bool = False,
    custom_source_path: Optional[str] = None,
    use_resume: bool = True,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Runs the incremental translation workflow for multiple target languages.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": f"Project {project_id} not found"}

    source_path = custom_source_path or project['source_path']
    project_name = project['name']

    target_codes_str = ", ".join([lang['code'] for lang in target_lang_infos])
    logger.info(f"Starting incremental update for: {project_name} -> [{target_codes_str}]")
    logger.info(f"Scanning source path: {source_path}")
    workflow_started_at = perf_counter()

    snapshot_service = IncrementalSnapshotService()
    diff_service = IncrementalDiffService()
    build_service = IncrementalBuildService()
    incremental_archive_service = IncrementalArchiveService()
    package_service = IncrementalPackageService()
    preparation_service = IncrementalPreparationService()
    translation_service = IncrementalTranslationService()
    snapshot_started_at = perf_counter()
    current_files_data = snapshot_service.build_snapshot(source_path, source_lang_info, progress_callback)
    snapshot_elapsed_ms = round((perf_counter() - snapshot_started_at) * 1000, 1)
    logger.info(f"Snapshot build completed for {project_name}: {len(current_files_data)} source files detected.")

    if not current_files_data:
        logger.warning(f"No source files found in {source_path}")
        return {
            "status": "warning", 
            "message": f"No source files found. Please verify the source language setting.",
            "summary": {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
        }

    # Initialize overall summary
    overall_summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
    overall_warnings = []
    all_written_files = []
    output_dirs = []
    overall_file_summaries = []
    telemetry = {
        "snapshot_ms": snapshot_elapsed_ms,
        "languages": [],
    }

    # Process EACH target language independently
    for target_lang_info in target_lang_infos:
        target_lang_code = target_lang_info['code']
        logger.info(f"--- Processing Target Language: {target_lang_code} ---")
        output_folder_name = package_service.build_output_folder_name(project_name, target_lang_info)
        lang_output_dir = Path(DEST_DIR) / output_folder_name
        lang_telemetry = {"target_lang": target_lang_code}

        if not dry_run:
            package_started_at = perf_counter()
            package_info = package_service.prepare_output_package(
                project_name=project_name,
                source_path=source_path,
                target_lang_info=target_lang_info,
                game_profile=game_profile,
            )
            lang_output_dir = package_info["package_root"]
            output_folder_name = package_info["output_folder_name"]
            output_dirs.append(str(lang_output_dir))
            lang_telemetry["package_prepare_ms"] = round((perf_counter() - package_started_at) * 1000, 1)
            logger.info(f"Prepared incremental package root for {project_name} ({target_lang_code}): {lang_output_dir}")
        
        logger.info(f"Pre-fetching archive for {project_name} ({target_lang_code})...")
        if progress_callback:
            progress_callback({
                "stage": "Preparing",
                "stage_code": "loading_archive",
                "percent": 15,
                "message": f"Pre-fetching archive for {target_lang_code}..."
            })

        archive_started_at = perf_counter()
        all_entries = incremental_archive_service.get_language_entries(
            project_id=project_id,
            language_code=target_lang_code,
        )
        baseline_info = incremental_archive_service.get_language_baseline(
            project_id=project_id,
            language_code=target_lang_code,
        )
        lang_telemetry["archive_fetch_ms"] = round((perf_counter() - archive_started_at) * 1000, 1)
        logger.info(f"Pre-fetched {len(all_entries)} archive entries for {project_name}.")
        if baseline_info:
            lang_telemetry["archive_baseline"] = {
                "language": target_lang_code,
                "version_id": baseline_info.get("id"),
                "created_at": baseline_info.get("created_at"),
                "last_translation_at": baseline_info.get("last_translation_at"),
                "translated_count": baseline_info.get("translated_count"),
            }
        history_index = diff_service.build_history_index(all_entries)
        preparation_started_at = perf_counter()
        preparation_result = preparation_service.prepare_language_update(
            current_files_data=current_files_data,
            history_index=history_index,
            diff_service=diff_service,
            target_lang_info=target_lang_info,
            source_lang_info=source_lang_info,
            game_profile=game_profile,
            mod_context=mod_context,
            selected_provider=selected_provider,
            source_path=source_path,
            base_output_dir=lang_output_dir,
            total_targets=1,
            progress_callback=progress_callback,
        )
        summary = preparation_result["summary"]
        processing_records = preparation_result["processing_records"]
        file_tasks_for_ai = preparation_result["file_tasks_for_ai"]
        file_summaries = preparation_result["file_summaries"]
        lang_output_dir = preparation_result["lang_output_dir"]
        lang_telemetry["prepare_ms"] = round((perf_counter() - preparation_started_at) * 1000, 1)
        lang_telemetry["source_files"] = len(current_files_data)
        lang_telemetry["dirty_files"] = len(file_tasks_for_ai)
        lang_telemetry["dirty_entries"] = summary["new"] + summary["changed"]
        logger.info(
            f"Prepared language update for {project_name} ({target_lang_code}): "
            f"summary={summary}, processing_records={len(processing_records)}, file_tasks_for_ai={len(file_tasks_for_ai)}"
        )

        for task in file_tasks_for_ai:
            task.mod_name = project_name

        # Aggregate summaries
        overall_summary["total"] += summary["total"]
        overall_summary["new"] += summary["new"]
        overall_summary["changed"] += summary["changed"]
        overall_summary["unchanged"] += summary["unchanged"]
        overall_file_summaries.extend([
            {
                **file_summary,
                "target_lang": target_lang_code,
            }
            for file_summary in file_summaries
        ])
        telemetry["languages"].append(lang_telemetry)

        if dry_run:
            continue # Skip translation for this language

        if not use_resume:
            from scripts.core.checkpoint_manager import CheckpointManager
            checkpoint_mgr = CheckpointManager(str(lang_output_dir))
            checkpoint_mgr.clear_checkpoint()

        try:
            translation_started_at = perf_counter()
            translated_results, warnings = translation_service.translate_dirty_files(
                file_tasks_for_ai=file_tasks_for_ai,
                selected_provider=selected_provider,
                model_name=model_name,
                target_lang_code=target_lang_code,
                concurrency_limit=concurrency_limit,
                rpm_limit=rpm_limit,
                progress_callback=progress_callback,
            )
            lang_telemetry["translation_ms"] = round((perf_counter() - translation_started_at) * 1000, 1)
            overall_warnings.extend(warnings)
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}

        build_started_at = perf_counter()
        build_result = build_service.build_language_output(
            processing_records=processing_records,
            translated_results=translated_results,
            source_path=source_path,
            lang_output_dir=lang_output_dir,
            source_lang_info=source_lang_info,
            target_lang_info=target_lang_info,
            game_profile=game_profile,
        )
        lang_telemetry["build_ms"] = round((perf_counter() - build_started_at) * 1000, 1)
        written_files = build_result["written_files"]
        all_written_files.extend(written_files)

        metadata_handler = api_handler.get_handler(selected_provider, model_name=model_name)
        if metadata_handler and metadata_handler.client:
            metadata_started_at = perf_counter()
            package_service.process_metadata(
                project_name=project_name,
                source_path=source_path,
                handler=metadata_handler,
                source_lang_info=source_lang_info,
                target_lang_info=target_lang_info,
                output_folder_name=output_folder_name,
                mod_context=mod_context,
                game_profile=game_profile,
            )
            lang_telemetry["metadata_ms"] = round((perf_counter() - metadata_started_at) * 1000, 1)

        archive_write_started_at = perf_counter()
        new_version_id = incremental_archive_service.archive_language_result(
            project_id=project_id,
            project_name=project_name,
            target_lang_code=target_lang_code,
            archive_files_data=build_result["archive_files_data"],
            archive_results=build_result["archive_results"],
        )
        lang_telemetry["archive_write_ms"] = round((perf_counter() - archive_write_started_at) * 1000, 1)
        lang_telemetry["total_ms"] = round(
            sum(
                value
                for key, value in lang_telemetry.items()
                if key.endswith("_ms") and isinstance(value, (int, float))
            ),
            1,
        )

        # 6. Log History for THIS language
        await project_manager.log_history_event(
            project_id=project_id,
            action_type="translate",
            description="history.incremental_translate_desc",
            snapshot_id=new_version_id,
            metadata={
                "summary": summary,
                "output_dir": str(lang_output_dir),
                "files_count": len(written_files),
                "target_lang": target_lang_code,
                "new_count": summary["new"],
                "changed_count": summary["changed"],
                "unchanged_count": summary["unchanged"],
            }
        )
        await project_manager.add_translation_path(project_id, str(lang_output_dir))

    if dry_run:
        telemetry["total_ms"] = round((perf_counter() - workflow_started_at) * 1000, 1)
        logger.info(f"Dry-run completed for {project_name}: overall_summary={overall_summary}")
        if progress_callback:
            progress_callback({
                "stage": "Completed",
                "stage_code": "completed",
                "percent": 100,
                "message": "Pre-scan completed.",
                "status": "completed", # Redundant but helps
                "summary": overall_summary,
                "file_summaries": overall_file_summaries,
                "telemetry": telemetry,
            })
        return {
            "status": "success",
            "summary": overall_summary,
            "file_summaries": overall_file_summaries,
            "telemetry": telemetry,
        }

    telemetry["total_ms"] = round((perf_counter() - workflow_started_at) * 1000, 1)
    return {
        "status": "success", 
        "summary": overall_summary, 
        "warnings": overall_warnings, 
        "output_dir": output_dirs[0] if len(output_dirs) == 1 else DEST_DIR,
        "output_dirs": output_dirs,
        "file_summaries": overall_file_summaries,
        "telemetry": telemetry,
        "warning_count": len(overall_warnings),
        "history_desc": f"Built incremental updates for {len(target_lang_infos)} languages."
    }
