"""Advanced base-game language patch delivery; never upload or mutate sources."""
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from scripts.core.mars_base_patch_service import MarsBasePatchService
from .agent_batch import get_batch_service, operation

from .advanced_agent_policy import require_advanced_route

router = APIRouter(dependencies=[Depends(require_advanced_route)], prefix="/api/agent/mars-base-patch", tags=["Mars base patch (advanced)"])


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mod_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]{2,63}$")
    title: str = Field(min_length=1, max_length=60, pattern=r"^[\x20-\x7e]+$")
    description: str = Field(min_length=1, max_length=8000)
    short_description: str = Field(min_length=1, max_length=1000)
    last_changes: str = Field(min_length=1, max_length=8000)
    author: str = Field(min_length=1, max_length=240)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    file_id: str
    candidates_path: str
    candidates_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    community_csv_path: str
    community_csv_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    conversion_job_ids: list[str] = Field(max_length=1000)
    native_job_ids: list[str] = Field(max_length=100)
    cover_asset_path: str
    cover_asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata: Metadata


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    approved: bool = False


def service(batch=Depends(get_batch_service)):
    from scripts.app_settings import DEST_DIR
    return MarsBasePatchService(batch, Path(DEST_DIR) / "mars_base_patches")


@router.post("/plan")
async def plan(request: Plan, current=Depends(service)):
    return await operation(current.plan, request)


@router.post("/export")
async def export(request: Approval, current=Depends(service)):
    return await operation(current.export, request.plan_id, request.approved)


@router.get("/plans/{identifier}")
async def get_plan(identifier: str, current=Depends(service)):
    return await operation(current.batch.repository.get, identifier, "mars_base_plan")
