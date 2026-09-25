"""Shared GUI and Agent API boundaries for approved local package generation."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from scripts.core.services import translation_package_workflow as workflow

router = APIRouter(tags=["Translation packages"])


class PackagePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_folder_name: str = Field(min_length=1, max_length=255)
    target_language: str = Field(min_length=2, max_length=20)
    source_mod_id: str | None = Field(default=None, max_length=100)
    source_mod_title: str | None = Field(default=None, max_length=240)
    author: str | None = Field(default=None, max_length=120)


class PackageExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    approved: bool = False


async def _respond(operation):
    try:
        return await operation
    except workflow.PackageWorkflowError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    except FileExistsError as exc:
        raise HTTPException(409, detail={"code": "package_exists", "message": "The package already exists; create a fresh export plan."}) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, detail={"code": "invalid_package_inputs", "message": str(exc)}) from exc


@router.get("/api/projects/{project_id}/translation-package/options")
@router.get("/api/agent/projects/{project_id}/translation-package/options")
async def package_options(project_id: str):
    return await _respond(workflow.package_options(project_id))


@router.post("/api/projects/{project_id}/translation-package/plan")
@router.post("/api/agent/projects/{project_id}/translation-package/plan")
async def plan_package(project_id: str, request: PackagePlanRequest):
    return await _respond(workflow.plan_package(project_id, request.model_dump()))


@router.post("/api/projects/{project_id}/translation-package")
@router.post("/api/agent/projects/{project_id}/translation-package")
async def export_package(project_id: str, request: PackageExportRequest):
    return await _respond(workflow.export_package(project_id, request.plan_id, request.approved))
