"""Shared desktop and Agent API for isolated FPK preparation and delivery."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from scripts.core.mars_pipeline import workflow, workflow_delivery, publication_identity
from scripts.routers.translation_packages import _respond

router = APIRouter(tags=["Mars pipeline"])


class PreparePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archive_path: str = Field(min_length=1, max_length=4096)
    name: str = Field(min_length=1, max_length=240)
    previous_run_id: str | None = None
    delivery_mode: Literal["text_only", "source_copy"] = "source_copy"
    approved_ids: list[str] = Field(default_factory=list, max_length=2000)


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    approved: bool = False


class TranslationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_folder_name: str = Field(min_length=1, max_length=255)
    language_code: str = Field(min_length=2, max_length=20)


class DeliveryMetadataOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, min_length=1, max_length=8000)
    short_description: str | None = Field(default=None, min_length=1, max_length=1000)
    last_changes: str | None = Field(default=None, min_length=1, max_length=8000)
    cover_asset_path: str | None = Field(default=None, min_length=1, max_length=4096)
    cover_asset_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def require_cover_snapshot(self):
        if (self.cover_asset_path is None) != (self.cover_asset_sha256 is None):
            raise ValueError("Cover image path and SHA-256 snapshot must be supplied together")
        return self


class DeliveryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["text_only", "overlay", "source_copy"]
    outputs: list[TranslationOutput] = Field(min_length=1, max_length=30)
    metadata_overrides: DeliveryMetadataOverrides | None = None


class PublicationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool = False
    expected_revision: int | None = Field(default=None, ge=0)
    steam_id: str = Field(min_length=1, max_length=20)


async def _publication_context(project_id: str) -> dict:
    try:
        _, receipt = await workflow_delivery._context(project_id)
        return receipt
    except workflow_delivery.PackageWorkflowError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


def _publication_response(operation):
    try:
        return operation()
    except publication_identity.PublicationIdentityError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/api/mars-pipeline/prepare/plan")
@router.post("/api/agent/mars-pipeline/prepare/plan")
async def plan_prepare(request: PreparePlan):
    return await _respond(workflow.plan_prepare(request.model_dump()))


@router.post("/api/mars-pipeline/prepare")
@router.post("/api/agent/mars-pipeline/prepare")
async def prepare(request: Approval):
    return await _respond(workflow.execute_prepare(request.plan_id, request.approved))


@router.get("/api/mars-pipeline/runs/{run_id}")
@router.get("/api/agent/mars-pipeline/runs/{run_id}")
async def get_run(run_id: str):
    return await _respond(workflow.get_run(run_id))


@router.get("/api/projects/{project_id}/mars-pipeline")
@router.get("/api/agent/projects/{project_id}/mars-pipeline")
async def options(project_id: str):
    return await _respond(workflow_delivery.options(project_id))


@router.get("/api/projects/{project_id}/mars-pipeline/publication")
@router.get("/api/agent/projects/{project_id}/mars-pipeline/publication")
async def get_publication(project_id: str):
    receipt = await _publication_context(project_id)
    return _publication_response(lambda: publication_identity.get_publication_binding(project_id, receipt))


@router.put("/api/projects/{project_id}/mars-pipeline/publication")
@router.put("/api/agent/projects/{project_id}/mars-pipeline/publication")
async def put_publication(project_id: str, request: PublicationBinding):
    receipt = await _publication_context(project_id)
    return _publication_response(lambda: publication_identity.bind_publication_id(
        project_id, receipt, request.steam_id, request.expected_revision, request.approved
    ))


@router.post("/api/projects/{project_id}/mars-pipeline/export/plan")
@router.post("/api/agent/projects/{project_id}/mars-pipeline/export/plan")
async def plan_delivery(project_id: str, request: DeliveryPlan):
    return await _respond(workflow_delivery.plan_delivery(project_id, request.model_dump(exclude_none=True)))


@router.post("/api/projects/{project_id}/mars-pipeline/export")
@router.post("/api/agent/projects/{project_id}/mars-pipeline/export")
async def export_delivery(project_id: str, request: Approval):
    return await _respond(workflow_delivery.execute_delivery(project_id, request.plan_id, request.approved))
