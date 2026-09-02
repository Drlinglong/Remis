"""Durable audit projection for paid context-workflow stages."""

from __future__ import annotations

from typing import Any, Mapping

from scripts.core.prompts.context_workflow_v3_prompt import WORKFLOW_V3_VERSION
from scripts.core.services.context_model_usage import ContextModelUsageLedger


def record_context_workflow_telemetry(
    status_service: Any,
    project_id: str,
    task_id: str | None,
    *,
    source_snapshot_hash: str | None,
    analysis_run: Any | None,
    workflow_version: str,
    workflow_context: Mapping[str, Any] | None,
    usage_ledger: ContextModelUsageLedger,
    analysis_report: Mapping[str, Any] | None = None,
    error: Exception | None = None,
) -> None:
    """Write usage and read metrics before or after the release gate."""

    recorder = getattr(status_service, "record_telemetry", None)
    if not callable(recorder):
        return
    model_execution = usage_ledger.summary()
    report = dict(analysis_report or {})
    context = workflow_context or {}
    corpus_read = report.get("corpus_read_amplification")
    if corpus_read is None:
        corpus_read = context.get("corpus_read_amplification")
    effective_workflow_version = context.get("workflow_version") or (
        WORKFLOW_V3_VERSION if workflow_version == "tree_v2" else workflow_version
    )
    recorder(
        project_id,
        task_id,
        {
            "workflow_version": effective_workflow_version,
            "analysis_run_id": getattr(analysis_run, "run_id", None),
            "source_snapshot_hash": source_snapshot_hash,
            "publication_status": "not_published",
            "model_execution": model_execution,
            "cost": model_execution.get("cost"),
            "corpus_read_amplification": corpus_read,
            "error": (
                {"type": type(error).__name__, "message": str(error)[:1000]}
                if error is not None else None
            ),
        },
    )


def handle_context_workflow_failure(
    status_service: Any,
    analysis_checkpoints: Any,
    project_id: str,
    task_id: str | None,
    total_files: int,
    processed_files: int,
    error: Exception,
    snapshot: Any | None,
    analysis_run: Any | None,
    workflow_context: Mapping[str, Any] | None,
    workflow_version: str,
    usage_ledger: ContextModelUsageLedger,
) -> None:
    """Persist failure evidence before projecting the terminal task state."""

    record_context_workflow_telemetry(
        status_service,
        project_id,
        task_id,
        source_snapshot_hash=(
            snapshot.source_snapshot_hash if snapshot is not None else None
        ),
        analysis_run=analysis_run,
        workflow_version=workflow_version,
        workflow_context=workflow_context,
        usage_ledger=usage_ledger,
        error=error,
    )
    analysis_checkpoints.mark_failed(analysis_run)
    status_service.mark_failed(
        project_id, task_id, total_files, processed_files, error,
    )


__all__ = [
    "handle_context_workflow_failure",
    "record_context_workflow_telemetry",
]
