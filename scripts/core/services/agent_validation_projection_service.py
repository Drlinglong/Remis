"""Build the Agent API's project and task-scoped validation projections."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional

from scripts.core.services.agent_validation_policy import (
    classify_issues,
    merge_task_validation_payload,
)
from scripts.schemas.agent import AgentValidationSummary


class AgentValidationProjectionService:
    """Keep project sidecars behind the current task result boundary."""

    def __init__(self, project_manager: Any, validation_sidecars: Any) -> None:
        self.project_manager = project_manager
        self.validation_sidecars = validation_sidecars

    @staticmethod
    def normalize_status(raw_status: Optional[str], *, recovered: bool = False) -> str:
        if recovered and raw_status not in {"completed", "failed", "cancelled"}:
            return "interrupted"
        return {
            "pending": "queued",
            "queued": "queued",
            "starting": "queued",
            "running": "running",
            "processing": "running",
            "completed": "completed",
            "failed": "failed",
            "partial_failed": "partial_failed",
            "cancelled": "cancelled",
            "interrupted": "interrupted",
        }.get(str(raw_status or "").lower(), "unknown")

    async def project_payload(
        self,
        project_id: Optional[str],
        *,
        include_items: bool = False,
    ) -> Dict[str, Any]:
        empty = AgentValidationSummary()
        if not project_id:
            return {"summary": empty, "items": []}
        project = await self.project_manager.get_project(project_id)
        if not project:
            return {"summary": empty, "items": []}
        status = self.validation_sidecars.load_status(project["source_path"])
        if not status:
            return {"summary": empty, "items": []}
        files = await self.project_manager.get_project_files(project_id)
        issues = self.validation_sidecars.attach_project_file_ids(
            status["issues"], files
        )
        public_items, summary = classify_issues(issues)
        if len(public_items) > 100:
            public_items = public_items[:100]
            summary.truncated = True
        return {
            "summary": summary,
            "items": public_items if include_items else [],
            "_raw_items": issues,
            "last_updated_at": status.get("last_updated_at"),
            "scope": status.get("sidecar_scope"),
        }

    async def task_payload(
        self,
        project_id: Optional[str],
        task: Dict[str, Any],
        status: str,
        *,
        include_items: bool = False,
        output_paths: Optional[list[str]] = None,
        project_payload: Callable[..., Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Suppress historical sidecars when a terminal task has no result."""
        current_output_paths = output_paths or self.task_output_paths(task)
        if (
            status in {"failed", "cancelled", "interrupted"}
            and not self.task_has_current_output_or_result(task, current_output_paths)
        ):
            return {
                "summary": AgentValidationSummary(),
                "items": [],
                "_raw_items": [],
                "_suppressed": True,
            }
        payload = merge_task_validation_payload(
            await project_payload(project_id, include_items=include_items),
            task,
            include_items=include_items,
        )
        payload["_suppressed"] = False
        return payload

    @staticmethod
    def task_output_paths(task: Dict[str, Any]) -> list[str]:
        """Return output paths recorded by this task, including its result."""
        output_paths = [
            str(path)
            for path in task.get("output_dirs") or []
            if path
        ]
        result = task.get("result") or {}
        for path in result.get("output_paths") or []:
            if path and str(path) not in output_paths:
                output_paths.append(str(path))
        if task.get("result_path") and task["result_path"] not in output_paths:
            output_paths.append(str(task["result_path"]))
        return output_paths

    @staticmethod
    def task_has_current_output_or_result(
        task: Dict[str, Any],
        output_paths: list[str],
    ) -> bool:
        return bool(output_paths or task.get("result"))
