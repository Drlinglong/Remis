"""User-facing operations for published Mod Archive lifecycle management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.core.repositories.context_archive_repository import ContextArchiveBusyError
from scripts.schemas.context_archive import (
    RemoveContextArchiveRequest,
    RemoveContextArchiveResponse,
)
from scripts.shared import task_state
from scripts.shared.services import context_archive_removal_service, project_manager


router = APIRouter(tags=["Mod Archive"])


@router.delete(
    "/api/context/projects/{project_id}/archive",
    response_model=RemoveContextArchiveResponse,
)
async def remove_context_archive(
    project_id: str, payload: RemoveContextArchiveRequest
):
    """Remove regenerable archive data without deleting the project or terminology."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project_name = str(project.get("name") or project_id)
    if not payload.approved:
        raise HTTPException(
            status_code=409,
            detail="Explicit confirmation is required to remove a project archive",
        )
    if payload.project_name.strip() != project_name:
        raise HTTPException(
            status_code=409,
            detail="Project name confirmation does not match the selected project",
        )
    if task_state.find_active_task_by_dedupe_key(f"neologism_mining:{project_id}"):
        raise HTTPException(
            status_code=409,
            detail="The project archive is currently being analyzed",
        )
    try:
        result = context_archive_removal_service.remove(project_id)
    except ContextArchiveBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result["removed"]:
        raise HTTPException(status_code=404, detail="No project archive data exists")
    return RemoveContextArchiveResponse(
        status="removed",
        project_id=project_id,
        project_name=project_name,
        removed_counts=result["counts"],
        preserved=["project", "source_files", "project_glossary", "neologism_candidates"],
        allowed_actions=["analyze_context_archive"],
    )
