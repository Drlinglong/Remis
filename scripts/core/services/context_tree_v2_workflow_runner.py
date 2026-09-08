"""Persistence-aware runner for the maintained tree-v2 workflow route."""

from __future__ import annotations

from typing import Any

from scripts.core.services.context_workflow_telemetry import (
    record_context_workflow_telemetry,
)


def execute_tree_v2_workflow(service: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Run tree-v2, persist its audit projection, then finalize task state."""

    result = service.tree_v2_workflow.run(
        project_id=values["project_id"],
        project_title=values["project_title"] or values["project_id"],
        task_id=values["task_id"],
        source_snapshot_hash=values["snapshot"].source_snapshot_hash,
        source_items=values["source_items"], local_units=values["local_units"],
        chunks=values["chunks"], scope=values["scope"],
        api_provider=values["api_provider"], model_name=values["model_name"],
        source_language=values["source_lang"], target_language=values["target_lang"],
        game_name=values["game_name"],
        description_language=values["effective_description_language"],
        duplicate_index=values["duplicate_index"] or {},
        analysis_run=values["analysis_run"], usage_ledger=values["usage_ledger"],
        concurrency=values["effective_concurrency"],
        runtime=values.get("runtime"),
    )
    record_context_workflow_telemetry(
        service.status_service,
        values["project_id"], values["task_id"],
        source_snapshot_hash=values["snapshot"].source_snapshot_hash,
        analysis_run=values["analysis_run"],
        workflow_context=values.get("workflow_context", {}),
        usage_ledger=values["usage_ledger"],
        analysis_report=result.get("analysis_report"),
        workflow_version=service.workflow_version,
    )
    if values["analysis_run"] is not None:
        service._finalize_analysis_run(values["analysis_run"], result)
    service._complete(
        values["project_id"], values["task_id"], result,
        len(values["parsed_files"]),
    )
    return result


__all__ = ["execute_tree_v2_workflow"]
