"""Agent transport for the existing local Steam publishing workbench.

This adapter deliberately excludes deletion and actual Steam publication.
Persistence, validation and paid generation remain owned by product services.
"""

import hashlib

from fastapi import APIRouter, HTTPException, Path, Query

from scripts.routers import steam_workshop as workbench
from scripts.schemas.steam_workshop import (
    AssetType, CreateCoverVersionRequest, CreateDescriptionVersionRequest,
    CreateWorkspaceRequest, GenerateDescriptionRequest, SelectVersionRequest,
)

router = APIRouter(prefix="/api/agent/steam-workshop", tags=["agent-steam-workshop"])


def _call(operation, *args):
    try:
        return operation(*args)
    except HTTPException as exc:
        codes = {400: "invalid_request", 404: "not_found", 409: "approval_required"}
        # Provider exception strings can contain credentials or request headers.
        raise HTTPException(exc.status_code, detail={
            "code": codes.get(exc.status_code, "workshop_operation_failed"),
            "message": "Steam workbench operation failed. Check the request, approval and workspace state.",
            "retryable": False,
        }) from exc
    except Exception as exc:
        raise HTTPException(502, detail={
            "code": "workshop_operation_failed",
            "message": "Steam workbench operation failed. Inspect persisted workspace state before retrying.",
            "retryable": False,
        }) from exc


@router.get("/items/{workshop_item_id}/description")
def get_source_description(workshop_item_id: str = Path(pattern=r"^[0-9]{1,32}$")):
    description = _call(workbench.description_generation_service.fetch_source_description, workshop_item_id)
    return {
        "workshop_item_id": workshop_item_id,
        "source_url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_item_id}",
        "source_description": description,
        "source_description_sha256": hashlib.sha256(description.encode("utf-8")).hexdigest(),
    }


@router.get("/workspaces")
def list_workspaces(project_id: str | None = Query(default=None)):
    return _call(workbench.list_workspaces, project_id)


@router.post("/workspaces", status_code=201)
def create_workspace(request: CreateWorkspaceRequest):
    return _call(workbench.create_workspace, request)


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    return _call(workbench.get_workspace, workspace_id)


@router.get("/workspaces/{workspace_id}/versions")
def list_versions(workspace_id: str, asset_type: AssetType | None = Query(default=None)):
    return _call(workbench.list_versions, workspace_id, asset_type)


@router.post("/workspaces/{workspace_id}/generate-description", status_code=201)
def generate_description(workspace_id: str, request: GenerateDescriptionRequest):
    return _call(workbench.generate_description, workspace_id, request)


@router.post("/workspaces/{workspace_id}/versions/description", status_code=201)
def save_description(workspace_id: str, request: CreateDescriptionVersionRequest):
    return _call(workbench.create_description_version, workspace_id, request)


@router.post("/workspaces/{workspace_id}/versions/cover", status_code=201)
def save_cover(workspace_id: str, request: CreateCoverVersionRequest):
    return _call(workbench.create_cover_version, workspace_id, request)


@router.get("/versions/{version_id}")
def get_version(version_id: str):
    return _call(workbench.get_version, version_id)


@router.get("/versions/{version_id}/content")
def get_cover_content(version_id: str):
    return _call(workbench.get_version_content, version_id)


@router.post("/workspaces/{workspace_id}/selections/{asset_type}")
def select_version(workspace_id: str, asset_type: AssetType, request: SelectVersionRequest):
    return _call(workbench.select_version, workspace_id, asset_type, request)
