import logging
from fastapi import APIRouter, HTTPException

from scripts.core.services.proofreading_service import ProofreadingConflictError, ProofreadingDataError
from scripts.shared.services import proofreading_service
from scripts.schemas.proofreading import AgentSaveProofreadingRequest, SaveProofreadingRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/proofread/{project_id}/{file_id}/revision")
async def get_proofread_revision(project_id: str, file_id: str):
    try:
        return await proofreading_service.get_document_revision(project_id, file_id)
    except ProofreadingDataError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

@router.get("/api/agent/proofread/{project_id}/{file_id}")
@router.get("/api/proofread/{project_id}/{file_id}")
async def get_proofread_data(project_id: str, file_id: str):
    """
    获取校对数据 - Delegation to Service
    """
    try:
        data = await proofreading_service.get_proofread_data(project_id, file_id)
    except ProofreadingDataError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    if not data:
        raise HTTPException(status_code=404, detail="Proofreading data not found")
    return data

async def _save_proofread_data(request: SaveProofreadingRequest):
    try:
        result = await proofreading_service.save_proofread_data(
            request.project_id,
            request.file_id,
            [{'key': e.key, 'translation': e.translation} for e in request.entries],
            [patch.model_dump() for patch in request.structure_patches],
            request.base_revision,
        )
    except ProofreadingConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "proofreading_revision_conflict", "message": str(exc)},
        ) from exc
    if not result:
        raise HTTPException(status_code=500, detail="Failed to save proofreading data")
    return result if isinstance(result, dict) else {"status": "success"}


async def _require_translation_file(project_id: str, file_id: str) -> None:
    files = await proofreading_service.project_manager.get_project_files(project_id)
    target = next((item for item in files if item.get("file_id") == file_id), None)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={"code": "proofreading_translation_not_found", "message": "Translation file not found in this project."},
        )
    if target.get("file_type") != "translation":
        raise HTTPException(
            status_code=409,
            detail={"code": "proofreading_target_not_translation", "message": "Agent proofreading can only save project translation files."},
        )


@router.post("/api/proofread/save")
async def save_proofread_data(request: SaveProofreadingRequest):
    """Save proofreading data using the existing GUI contract."""
    return await _save_proofread_data(request)


@router.post("/api/agent/proofread/save")
async def save_agent_proofread_data(request: AgentSaveProofreadingRequest):
    """Save Agent proofreading changes only with approval and a fresh revision."""
    await _require_translation_file(request.project_id, request.file_id)
    return await _save_proofread_data(request)
