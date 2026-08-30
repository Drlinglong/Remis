import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from scripts.core.checkpoint_manager import CheckpointManager


@dataclass
class LanguageRunState:
    completed_batches: int = 0
    successful_batches: int = 0
    failed_batches: int = 0
    error_count: int = 0
    glossary_issues: int = 0
    glossary_issue_details: list[dict] = field(default_factory=list)
    recovered_retries: int = 0
    format_issues: int = 0


def build_checkpoint_manager(
    output_dir_path: str,
    selected_provider: str,
    model_name: Optional[str],
    source_lang: dict,
    target_lang: dict,
    use_resume: bool,
) -> CheckpointManager:
    current_config = {
        "model_name": model_name or selected_provider,
        "source_lang": source_lang.get("code"),
        "target_lang_code": target_lang.get("code"),
    }
    checkpoint_filename = f".remis_checkpoint_{target_lang.get('code', 'unknown')}.json"
    checkpoint_manager = CheckpointManager(
        output_dir_path,
        current_config=current_config,
        checkpoint_filename=checkpoint_filename,
    )
    if not use_resume:
        checkpoint_manager.clear_checkpoint()
        logging.info(f"use_resume is False - cleared checkpoint for {target_lang.get('code')}")
    return checkpoint_manager


def emit_progress(
    progress_callback: Optional[Any],
    run_state: LanguageRunState,
    total_batches: int,
    current_file_name: str = "",
    stage: str = "Translating",
    log_message: Optional[str] = None,
    format_issues_override: Optional[int] = None,
    format_repair: Optional[dict] = None,
    workshop_progress: Optional[dict] = None,
    event_level: Optional[str] = None,
):
    if format_issues_override is not None:
        run_state.format_issues = format_issues_override

    if progress_callback:
        progress_callback(
            current=run_state.completed_batches,
            total=total_batches,
            current_file=current_file_name,
            stage=stage,
            current_batch=run_state.completed_batches,
            total_batches=total_batches,
            successful_batches=run_state.successful_batches,
            failed_batches=run_state.failed_batches,
            error_count=run_state.error_count,
            glossary_issues=run_state.glossary_issues,
            glossary_issue_details=run_state.glossary_issue_details,
            recovered_retries=run_state.recovered_retries,
            format_issues=run_state.format_issues,
            format_repair=format_repair,
            workshop_progress=workshop_progress,
            log_message=log_message,
            event_level=event_level,
        )


def build_progress_emitter(
    progress_callback: Optional[Any],
    run_state: LanguageRunState,
    total_batches: int,
):
    """Bind run-scoped state to the callback contract."""
    def update_progress(
        current_file_name="",
        stage="Translating",
        log_message=None,
        format_issues_override=None,
        format_repair=None,
        workshop_progress=None,
        event_level=None,
    ):
        emit_progress(
            progress_callback,
            run_state,
            total_batches,
            current_file_name,
            stage,
            log_message,
            format_issues_override,
            format_repair,
            workshop_progress,
            event_level,
        )

    return update_progress


@contextmanager
def progress_log_bridge(progress_logger):
    class CallbackHandler(logging.Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                if "GET /api/status" in msg:
                    return
                progress_logger(log_message=msg, event_level=record.levelname.lower())
            except Exception:
                self.handleError(record)

    log_handler = CallbackHandler()
    log_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)
    logging.getLogger().addHandler(log_handler)
    try:
        yield
    finally:
        logging.getLogger().removeHandler(log_handler)
