from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.services.steam_workshop_task_service import (
    COVER_TASK_KIND,
    DESCRIPTION_TASK_KIND,
    generate_description_candidate,
    save_cover_candidate,
)
from scripts.core.services.workshop_description_generation_service import (
    WorkshopDescriptionGenerationService,
)
from scripts.schemas.steam_workshop import (
    AssetType,
    CreateCoverVersionRequest,
    CreateDescriptionVersionRequest,
    CreateWorkspaceRequest,
    GenerateDescriptionRequest,
    SelectVersionRequest,
    UpdateWorkspaceRequest,
)

router = APIRouter(prefix="/api/steam-workshop", tags=["steam-workshop"])
steam_workshop_service = SteamWorkshopService()
description_generation_service = WorkshopDescriptionGenerationService()

def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    detail = str(exc)
    status_code = 409 if "cannot be deleted" in detail else 400
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/workspaces")
def list_workspaces(project_id: str | None = Query(default=None)):
    return steam_workshop_service.list_workspaces(project_id)


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
def create_workspace(request: CreateWorkspaceRequest):
    try:
        return steam_workshop_service.create_workspace(request.model_dump())
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    try:
        return steam_workshop_service.get_workspace(workspace_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.patch("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    try:
        return steam_workshop_service.update_workspace(
            workspace_id,
            request.model_dump(exclude_unset=True),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: str):
    try:
        steam_workshop_service.delete_workspace(workspace_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/workspaces/{workspace_id}/versions")
def list_versions(
    workspace_id: str,
    asset_type: AssetType | None = Query(default=None),
):
    try:
        return steam_workshop_service.list_versions(workspace_id, asset_type)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/workspaces/{workspace_id}/versions/description",
    status_code=status.HTTP_201_CREATED,
)
def create_description_version(
    workspace_id: str,
    request: CreateDescriptionVersionRequest,
):
    try:
        return steam_workshop_service.create_description_version(
            workspace_id,
            request.model_dump(),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/workspaces/{workspace_id}/generate-description",
    status_code=status.HTTP_201_CREATED,
)
def generate_description(
    workspace_id: str,
    request: GenerateDescriptionRequest,
):
    if not request.approved:
        raise HTTPException(
            status_code=409,
            detail="Explicit approval is required before model generation",
        )
    try:
        workspace = steam_workshop_service.get_workspace(workspace_id)
        workshop_item_id = (
            request.workshop_item_id or workspace.get("workshop_item_id")
        )
        if not workshop_item_id:
            raise ValueError("A Workshop ID is required for model generation")
    except Exception as exc:
        raise _http_error(exc) from exc

    try:
        return generate_description_candidate(
            workspace=workspace,
            workshop_item_id=workshop_item_id,
            request=request.model_dump(),
            workshop_service=steam_workshop_service,
            generation_service=description_generation_service,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/workspaces/{workspace_id}/versions/cover",
    status_code=status.HTTP_201_CREATED,
)
def create_cover_version(
    workspace_id: str,
    request: CreateCoverVersionRequest,
):
    try:
        workspace = steam_workshop_service.get_workspace(workspace_id)
    except Exception as exc:
        raise _http_error(exc) from exc

    try:
        return save_cover_candidate(
            workspace=workspace,
            request=request.model_dump(),
            workshop_service=steam_workshop_service,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/versions/{version_id}")
def get_version(version_id: str):
    try:
        return steam_workshop_service.get_version(version_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/versions/{version_id}/content", response_class=FileResponse)
def get_version_content(version_id: str):
    try:
        path = steam_workshop_service.get_cover_path(version_id)
        return FileResponse(path, media_type="image/png", filename=f"{version_id}.png")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/workspaces/{workspace_id}/selections/{asset_type}")
def select_version(
    workspace_id: str,
    asset_type: AssetType,
    request: SelectVersionRequest,
):
    try:
        return steam_workshop_service.select_version(
            workspace_id,
            asset_type,
            request.version_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
