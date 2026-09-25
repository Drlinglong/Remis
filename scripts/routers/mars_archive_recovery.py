"""Agent API for approved, no-model recovery of archived Mars translations."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from scripts.core.services import mars_translation_recovery as workflow

router = APIRouter(tags=["Mars translation recovery"])


class RecoveryPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    languages: list[str] = Field(min_length=1, max_length=9)


class RecoveryApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=8, max_length=100)
    approved: bool = False


def _respond_error(exc: Exception) -> HTTPException:
    if isinstance(exc, workflow.RecoveryError):
        return HTTPException(exc.status, detail={"code": exc.code, "message": str(exc), "retryable": False})
    if isinstance(exc, FileExistsError):
        return HTTPException(409, detail={"code": "output_exists", "message": "A recovery output already exists; no files were overwritten.", "retryable": False})
    if isinstance(exc, (ValueError, OSError)):
        return HTTPException(422, detail={"code": "recovery_failed", "message": str(exc), "retryable": False})
    raise exc


@router.post("/api/agent/projects/{project_id}/translation-recovery/plan")
async def plan_recovery(project_id: str, request: RecoveryPlanRequest):
    try:
        return await workflow.plan_recovery(project_id, request.languages)
    except Exception as exc:
        raise _respond_error(exc) from exc


@router.post("/api/agent/projects/{project_id}/translation-recovery")
async def execute_recovery(project_id: str, request: RecoveryApproval):
    try:
        return await workflow.execute_recovery(project_id, request.plan_id, request.approved)
    except Exception as exc:
        raise _respond_error(exc) from exc
