"""GUI-only publication surface; Agent orchestration remains out of scope."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from scripts.core.services.workshop_publication_inputs import PARADOX_GAMES, output_options
from scripts.core.steam_game_catalog import GAME_STEAM_APP_IDS, publication_game_options
from scripts.core.services.workshop_publication_runtime import publication_runtime
from scripts.schemas.workshop_publication import PublicationApprovalRequest, PublicationError, PublicationPlanRequest, PublicationVerificationRequest
from scripts.shared.services import project_manager

router = APIRouter(prefix="/api/steam-workshop/workspaces", tags=["workshop-publication"])
service = publication_runtime()


async def _project(workspace_id):
    workspace = service.inputs.workshop.get_workspace(workspace_id)
    project_id = workspace.get("project_id")
    if not project_id:
        raise PublicationError("project_required", "Bind a project before publication")
    project = await project_manager.get_project(project_id)
    if not project:
        raise PublicationError("project_not_found", "Bound project not found", 404)
    return project


def _error(exc):
    if isinstance(exc, PublicationError):
        return HTTPException(exc.status_code, detail=exc.detail())
    if isinstance(exc, LookupError):
        return HTTPException(404, detail={"code": "workspace_not_found", "message": "Workspace not found"})
    return HTTPException(409, detail={"code": "publication_inspection_failed", "message": "Publication inspection failed; review project outputs and assets"})


@router.get("/{workspace_id}/publication/options")
async def options(workspace_id: str):
    try:
        project = await _project(workspace_id)
        outputs = await asyncio.to_thread(output_options, project)
        return {"outputs": outputs, "runtime": service.adapter.availability(),
                "game_options": publication_game_options(PARADOX_GAMES),
                "default_app_id": GAME_STEAM_APP_IDS.get(project.get("game_id")),
                "default_visibility": "private", "default_mode": "create"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{workspace_id}/publication/plans", status_code=201)
async def plan(workspace_id: str, request: PublicationPlanRequest):
    try:
        project = await _project(workspace_id)
        return await asyncio.to_thread(service.plan, workspace_id, project, request.model_dump())
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/{workspace_id}/publication/plans")
def list_plans(workspace_id: str):
    try:
        service.inputs.workshop.get_workspace(workspace_id)
        return [service.public(record) for record in service.repository.list_plans(workspace_id)]
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/{workspace_id}/publication/plans/{plan_id}")
def get_plan(workspace_id: str, plan_id: str):
    try:
        record = service.repository.get(plan_id)
        if record["workspace_id"] != workspace_id:
            raise PublicationError("plan_not_found", "Publication plan not found", 404)
        return service.public(record)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{workspace_id}/publication/plans/{plan_id}/submit", status_code=202)
async def submit(workspace_id: str, plan_id: str, request: PublicationApprovalRequest, background: BackgroundTasks):
    try:
        project = await _project(workspace_id)
        result, claimed = await asyncio.to_thread(service.approve, workspace_id, plan_id, project,
                                                  request.approved, request.fingerprint)
        if claimed:
            background.add_task(service.run, plan_id)
        return result
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{workspace_id}/publication/plans/{plan_id}/verify")
def verify(workspace_id: str, plan_id: str, request: PublicationVerificationRequest):
    try:
        return service.verify_remote(workspace_id, plan_id, request.model_dump())
    except Exception as exc:
        raise _error(exc) from exc
