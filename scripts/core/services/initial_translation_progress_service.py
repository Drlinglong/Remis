import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

from scripts.core.checkpoint_manager import CheckpointManager


@dataclass
class LanguageRunState:
    completed_batches: int = 0
    error_count: int = 0
    glossary_issues: int = 0
    format_issues: int = 0


def build_checkpoint_manager(
    output_dir_path: str,
    selected_provider: str,
    model_name: Optional[str],
    source_lang: dict,
    target_lang: dict,
    use_resume: bool,
    context_metadata: Optional[dict] = None,
) -> CheckpointManager:
    current_config = {
        "model_name": model_name or selected_provider,
        "source_lang": source_lang.get("code"),
        "target_lang_code": target_lang.get("code"),
    }
    if context_metadata:
        current_config["context_release_id"] = context_metadata.get("context_release_id")
        current_config["source_snapshot_hash"] = context_metadata.get("source_snapshot_hash")
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
            error_count=run_state.error_count,
            glossary_issues=run_state.glossary_issues,
            format_issues=run_state.format_issues,
            format_repair=format_repair,
            workshop_progress=workshop_progress,
            log_message=log_message,
        )


@contextmanager
def progress_log_bridge(progress_logger):
    class CallbackHandler(logging.Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                if "GET /api/status" in msg:
                    return
                progress_logger(log_message=msg)
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
