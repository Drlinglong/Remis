"""Bounded Agent routes for published Mod Context releases."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.repositories.context_archive_repository import ContextArchiveBusyError
from scripts.core.services.agent_context_service import AgentContextService
from scripts.schemas.context_archive import (
    RemoveContextArchiveRequest,
    RemoveContextArchiveResponse,
)
from scripts.schemas.agent_context import (
    AgentContextEffectiveResponse,
    AgentContextLatestReleaseResponse,
    AgentContextTraceabilityResponse,
)
from scripts.shared import task_state
from scripts.shared.services import context_archive_removal_service, project_manager


router = APIRouter(prefix="/api/agent", tags=["Agent Context API"])
context_repository = ContextRepository(PROJECTS_DB_PATH)
agent_context_service = AgentContextService(context_repository)
AGENT_CONTEXT_CAPABILITIES = {
    "read_context_release": {
        "supported": True,
        "read_only": True,
        "requires_approval": False,
        "preflight_required": True,
        "endpoints": [
            "/api/agent/context/releases/{project_id}/latest",
            "/api/agent/context/releases/{release_id}/effective",
            "/api/agent/context/releases/{release_id}/traceability",
        ],
    },
    "read_effective_context": {
        "supported": True,
        "read_only": True,
        "requires_approval": False,
        "preflight_required": True,
    },
    "read_context_traceability": {
        "supported": True,
        "read_only": True,
        "requires_approval": False,
        "preflight_required": True,
    },
    "remove_context_archive": {
        "supported": True,
        "read_only": False,
        "requires_approval": True,
        "preflight_required": True,
        "endpoints": ["/api/agent/context/projects/{project_id}/archive"],
    },
    "context_analysis": {
        "supported": False,
        "requires_approval": True,
        "reason": (
            "Agent context-analysis plan/start is not exposed yet; use the "
            "existing Remis context workflow with its normal task and approval gates."
        ),
    },
}


def _context_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": False},
    )


@router.get(
    "/context/releases/{project_id}/latest",
    response_model=AgentContextLatestReleaseResponse,
)
def get_latest_agent_context_release(project_id: str):
    release = agent_context_service.latest_release(project_id)
    if release is None:
        raise _context_error(
            404,
            "context_release_not_found",
            "No published context release exists for this project",
        )
    return release


@router.get(
    "/context/releases/{release_id}/effective",
    response_model=AgentContextEffectiveResponse,
)
def get_agent_effective_context(release_id: str):
    effective = agent_context_service.effective_context(release_id)
    if effective is None:
        raise _context_error(404, "context_release_not_found", "Context release not found")
    return effective


@router.get(
    "/context/releases/{release_id}/traceability",
    response_model=AgentContextTraceabilityResponse,
)
def get_agent_context_traceability(
    release_id: str,
    aggregate_key: str | None = Query(default=None, min_length=1, max_length=200),
    context_key: str | None = Query(default=None, min_length=1, max_length=200),
):
    if aggregate_key is None and context_key is None:
        raise _context_error(
            400,
            "context_selection_required",
            "Select an aggregate_key or context_key",
        )
    traceability = agent_context_service.traceability(
        release_id,
        aggregate_key=aggregate_key,
        context_key=context_key,
    )
    if traceability is None:
        raise _context_error(
            404,
            "context_selection_not_found",
            "The published context release or selected context key was not found",
        )
    return traceability


@router.delete(
    "/context/projects/{project_id}/archive",
    response_model=RemoveContextArchiveResponse,
)
async def remove_agent_context_archive(
    project_id: str, payload: RemoveContextArchiveRequest
):
    """Approval-gated Agent operation for deleting regenerable archive data."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise _context_error(404, "project_not_found", "Project not found")
    project_name = str(project.get("name") or project_id)
    if not payload.approved:
        raise _context_error(
            409,
            "approval_required",
            "Explicit approval is required before removing a project archive",
        )
    if payload.project_name.strip() != project_name:
        raise _context_error(
            409,
            "project_confirmation_mismatch",
            "Project name confirmation does not match the selected project",
        )
    if task_state.find_active_task_by_dedupe_key(f"neologism_mining:{project_id}"):
        raise _context_error(
            409,
            "context_analysis_active",
            "The project archive is currently being analyzed",
        )
    try:
        result = context_archive_removal_service.remove(project_id)
    except ContextArchiveBusyError as exc:
        raise _context_error(409, "context_analysis_active", str(exc)) from exc
    if not result["removed"]:
        raise _context_error(404, "context_archive_not_found", "No project archive data exists")
    return RemoveContextArchiveResponse(
        status="removed",
        project_id=project_id,
        project_name=project_name,
        removed_counts=result["counts"],
        preserved=["project", "source_files", "project_glossary", "neologism_candidates"],
        allowed_actions=["analyze_context_archive"],
    )
