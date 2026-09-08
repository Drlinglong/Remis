import logging
import os
from typing import List, Optional

from scripts.core.services.workshop_issue_export_service import resolve_dynamic_valid_tags
from scripts.app_settings import DEST_DIR, SOURCE_DIR


def build_format_validation_summary(total_errors: int, total_warnings: int) -> str:
    """Build a summary whose wording cannot misclassify zero-count errors."""
    total_issues = total_errors + total_warnings
    if total_issues == 0:
        return "Final file format validation completed. Found 0 format issues."
    counts = []
    if total_errors:
        counts.append(f"{total_errors} error(s)")
    if total_warnings:
        counts.append(f"{total_warnings} warning(s)")
    return (
        "Final file format validation completed. "
        f"Found {total_issues} format issue(s): {', '.join(counts)}."
    )


def run_post_processing(
    mod_name,
    game_profile,
    target_lang,
    source_lang,
    output_folder_name,
    proofreading_tracker,
    update_progress_callback=None,
    source_root: Optional[str] = None,
    dynamic_valid_tags: Optional[List[str]] = None,
):
    """Run final validation and attach results to the proofreading tracker."""
    try:
        from scripts.core.post_processing_manager import PostProcessingManager

        output_folder_path = os.path.join(DEST_DIR, output_folder_name)
        post_processor = PostProcessingManager(
            game_profile,
            output_folder_path,
            source_root=source_root or os.path.join(SOURCE_DIR, mod_name),
        )
        validation_success = post_processor.run_validation(
            target_lang,
            source_lang,
            dynamic_valid_tags=dynamic_valid_tags,
        )

        stats = post_processor.get_validation_stats()
        total_errors = stats.get('total_errors', 0)
        total_warnings = stats.get('total_warnings', 0)
        total_issues = total_errors + total_warnings

        if update_progress_callback:
            update_progress_callback(
                log_message=build_format_validation_summary(total_errors, total_warnings),
                format_issues_override=total_issues,
            )

        if validation_success:
            post_processor.attach_results_to_proofreading_tracker(proofreading_tracker)

    except Exception as e:
        logging.error(f"Post-processing failed: {e}")


def finalize_language_run(
    mod_name: str,
    game_profile: dict,
    target_lang: dict,
    source_lang: dict,
    output_folder_name: str,
    proofreading_tracker,
    update_progress_callback,
    override_path: Optional[str] = None,
):
    """Run post-processing and persist proofreading progress for one target language."""
    source_root = override_path if override_path else os.path.join(SOURCE_DIR, mod_name)
    dynamic_valid_tags = resolve_dynamic_valid_tags(game_profile, source_root)
    run_post_processing(
        mod_name,
        game_profile,
        target_lang,
        source_lang,
        output_folder_name,
        proofreading_tracker,
        update_progress_callback,
        source_root=source_root,
        dynamic_valid_tags=dynamic_valid_tags,
    )
    proofreading_tracker.save_proofreading_progress()
    return dynamic_valid_tags
