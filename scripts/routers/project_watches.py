from fastapi import APIRouter, HTTPException

from scripts.schemas.project_watches import (
    CreateProjectWatchRequest,
    ScanProjectWatchesRequest,
    UpdateProjectWatchRequest,
)
from scripts.shared.services import project_watch_service
from scripts.utils.system_utils import sanitize_for_json

router = APIRouter()


@router.get("/api/project-watches")
async def list_project_watches():
    return sanitize_for_json(await project_watch_service.list_watches())


@router.post("/api/project-watches")
async def create_project_watch(request: CreateProjectWatchRequest):
    try:
        return sanitize_for_json(await project_watch_service.create_watch(request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/api/project-watches/{watch_id}")
async def update_project_watch(watch_id: str, request: UpdateProjectWatchRequest):
    try:
        return sanitize_for_json(await project_watch_service.update_watch(watch_id, request.model_dump(exclude_unset=True)))
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail.lower() else 400, detail=detail)


@router.delete("/api/project-watches/{watch_id}")
async def delete_project_watch(watch_id: str):
    await project_watch_service.delete_watch(watch_id)
    return {"status": "success"}


@router.post("/api/project-watches/{watch_id}/scan")
async def scan_project_watch(watch_id: str):
    try:
        return sanitize_for_json(await project_watch_service.scan_watch(watch_id))
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail.lower() else 400, detail=detail)


@router.post("/api/project-watches/scan")
async def scan_project_watches(request: ScanProjectWatchesRequest):
    try:
        return sanitize_for_json(await project_watch_service.scan_watches(request.watch_ids))
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail.lower() else 400, detail=detail)


@router.post("/api/project-watches/scan-due")
async def scan_due_project_watches():
    return sanitize_for_json(await project_watch_service.scan_due_watches())
