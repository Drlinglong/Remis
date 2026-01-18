import logging
from fastapi import APIRouter, HTTPException

from scripts.shared.services import proofreading_service
from scripts.schemas.proofreading import SaveProofreadingRequest

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/proofread/{project_id}/{file_id}")
async def get_proofread_data(project_id: str, file_id: str):
    """
    获取校对数据 - Delegation to Service
    """
    data = await proofreading_service.get_proofread_data(project_id, file_id)
    if not data:
        raise HTTPException(status_code=404, detail="Proofreading data not found")
    return data

@router.post("/api/proofread/save")
async def save_proofread_data(request: SaveProofreadingRequest):
    """
    保存校对数据 - Delegation to Service
    """
    success = await proofreading_service.save_proofread_data(
        request.project_id, 
        request.file_id, 
        [{'key': e.key, 'translation': e.translation} for e in request.entries]
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save proofreading data")
    return {"status": "success"}
