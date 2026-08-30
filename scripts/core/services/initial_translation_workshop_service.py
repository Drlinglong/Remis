import asyncio
import logging
import os
from typing import Any, List, Optional

from scripts.core.services.embedded_workshop_service import run_embedded_workshop
from scripts.core.services.initial_translation_snapshot_service import resolve_archive_mod_name
from scripts.core.services.workshop_issue_export_service import WorkshopIssueExportService
from scripts.app_settings import SOURCE_DIR


def export_workshop_issues_for_language(
    output_dir_path: str,
    override_path: Optional[str],
    mod_name: str,
    project_id: Optional[str],
    source_lang: dict,
    target_lang: dict,
    game_profile: dict,
    dynamic_valid_tags: Optional[List[str]] = None,
):
    archive_mod_name = resolve_archive_mod_name(mod_name, project_id)
    exporter = WorkshopIssueExportService()
    export_result = exporter.export_for_output(
        output_root=output_dir_path,
        source_root=override_path if override_path else os.path.join(SOURCE_DIR, mod_name),
        source_lang_info=source_lang,
        target_lang_info=target_lang,
        game_profile=game_profile,
        workflow="initial",
        project_name=archive_mod_name,
        project_id=project_id or "",
        dynamic_valid_tags=dynamic_valid_tags,
    )
    logging.info(
        "Exported %s workshop issues for %s to %s",
        export_result.get("issue_count", 0),
        target_lang.get("code"),
        export_result.get("issues_path"),
    )


def run_embedded_workshop_for_language(
    embedded_workshop: Optional[dict],
    output_dir_path: str,
    override_path: Optional[str],
    mod_name: str,
    project_id: Optional[str],
    source_lang: dict,
    target_lang: dict,
    game_profile: dict,
    selected_provider: str,
    model_name: Optional[str],
    concurrency_limit: Optional[int] = None,
    batch_size_limit: Optional[int] = None,
    rpm_limit: Optional[int] = None,
    dynamic_valid_tags: Optional[List[str]] = None,
    update_progress_callback=None,
    provider_runtime: Any = None,
):
    if embedded_workshop is None:
        embedded_workshop = {"enabled": True, "follow_primary_settings": True}

    if not embedded_workshop.get("enabled", True):
        logging.info("Embedded workshop skipped for %s: disabled or not configured.", target_lang.get("code"))
        if update_progress_callback:
            update_progress_callback(log_message=f"[{target_lang.get('code', '').upper()}] Smart Workshop skipped: disabled.")
        return

    archive_mod_name = resolve_archive_mod_name(mod_name, project_id)
    try:
        def embedded_progress(data):
            if not update_progress_callback:
                return
            workshop_progress = data.get("workshop_progress")
            update_progress_callback(
                stage=data.get("stage", "Smart Workshop"),
                log_message=data.get("message"),
                workshop_progress=workshop_progress,
            )

        workshop_summary = asyncio.run(run_embedded_workshop(
            output_root=output_dir_path,
            source_root=override_path if override_path else os.path.join(SOURCE_DIR, mod_name),
            project_id=project_id,
            project_name=archive_mod_name,
            source_lang_info=source_lang,
            target_lang_info=target_lang,
            game_profile=game_profile,
            workflow="initial",
            config=embedded_workshop,
            fallback_provider=selected_provider,
            fallback_model=model_name,
            fallback_concurrency=concurrency_limit,
            fallback_batch_size=batch_size_limit,
            fallback_rpm=rpm_limit,
            dynamic_valid_tags=dynamic_valid_tags,
            progress_callback=embedded_progress,
            provider_runtime=provider_runtime,
        ))
        if workshop_summary.get("detected_count", 0) == 0:
            logging.info("Embedded workshop skipped for %s: no fixable validation issues in sidecar.", target_lang.get("code"))
            if update_progress_callback:
                update_progress_callback(log_message=f"[{target_lang.get('code', '').upper()}] Smart Workshop skipped: no fixable validation issues.")
        elif update_progress_callback:
            repair_summary = {
                "detected_count": workshop_summary.get("detected_count", 0),
                "fixed_count": workshop_summary.get("fixed_count", 0),
                "remaining_count": workshop_summary.get("remaining_count", 0),
                "failed_count": workshop_summary.get("failed_count", 0),
            }
            workshop_progress = {
                "detected_count": workshop_summary.get("detected_count", 0),
                "processed_count": workshop_summary.get("detected_count", 0),
                "fixed_count": workshop_summary.get("fixed_count", 0),
                "failed_count": workshop_summary.get("failed_count", 0),
                "reflection_round": 1,
            }
            update_progress_callback(
                stage="Smart Workshop",
                log_message=(
                    f"[{target_lang.get('code', '').upper()}] Smart Workshop completed: "
                    f"{workshop_summary.get('fixed_count', 0)}/{workshop_summary.get('detected_count', 0)} fixed, "
                    f"{workshop_summary.get('remaining_count', 0)} remaining."
                ),
                format_repair=repair_summary,
                workshop_progress=workshop_progress,
            )
        logging.info(
            "Embedded workshop finished for %s: fixed=%s failed=%s remaining=%s provider=%s model=%s",
            target_lang.get("code"),
            workshop_summary.get("fixed_count", 0),
            workshop_summary.get("failed_count", 0),
            workshop_summary.get("remaining_count", 0),
            workshop_summary.get("provider"),
            workshop_summary.get("model"),
        )
    except Exception as exc:
        logging.error("Embedded workshop failed for %s: %s", target_lang.get("code"), exc)
