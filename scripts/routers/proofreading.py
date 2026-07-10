import logging
from fastapi import APIRouter, HTTPException

from scripts.core.services.proofreading_service import ProofreadingConflictError, ProofreadingDataError
from scripts.shared.services import proofreading_service
from scripts.schemas.proofreading import SaveProofreadingRequest

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

@router.post("/api/proofread/save")
async def save_proofread_data(request: SaveProofreadingRequest):
    """
    保存校对数据 - Delegation to Service
    """
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
