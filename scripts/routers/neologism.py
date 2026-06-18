import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from scripts.core.neologism_manager import neologism_manager
from scripts.shared.services import project_manager
from scripts.schemas.neologism import ApproveNeologismRequest, UpdateNeologismRequest, MineNeologismsRequest
from scripts.app_settings import GAME_PROFILES_BY_ID

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/neologisms")
def list_neologisms(project_id: Optional[str] = None):
    """List neologism candidates, optionally filtered by project."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id query parameter is required")
    return neologism_manager.get_pending_candidates(project_id)

@router.post("/api/neologisms/{candidate_id}/approve")
async def approve_neologism(candidate_id: str, payload: ApproveNeologismRequest):
    """Approve a neologism candidate and add to glossary."""
    if await neologism_manager.approve_candidate(
        payload.project_id,
        candidate_id,
        payload.final_translation,
        payload.glossary_id,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
    ):
        logger.info(f"Approved neologism candidate {candidate_id} for project {payload.project_id}")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Candidate not found or failed to approve")

@router.post("/api/neologisms/{candidate_id}/reject")
def reject_neologism(candidate_id: str, payload: dict):
    """Reject a neologism candidate."""
    project_id = payload.get('project_id')
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if neologism_manager.reject_candidate(project_id, candidate_id):
        logger.info(f"Rejected neologism candidate {candidate_id} for project {project_id}")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Candidate not found")

@router.patch("/api/neologisms/{candidate_id}")
def update_neologism_suggestion(candidate_id: str, payload: UpdateNeologismRequest):
    """Update a candidate's suggestion."""
    if neologism_manager.update_candidate_suggestion(payload.project_id, candidate_id, payload.suggestion):
        logger.info(f"Updated neologism candidate {candidate_id} suggestion for project {payload.project_id}")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Candidate not found")

@router.post("/api/neologisms/mine")
async def trigger_mining(payload: MineNeologismsRequest, background_tasks: BackgroundTasks):
    """Trigger neologism mining for a project."""
    project = await project_manager.get_project(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all text files in project
    if payload.file_paths:
        files = payload.file_paths
    else:
        # Get all text files in project
        files = []
        for root, _, filenames in os.walk(project['source_path']):
            for filename in filenames:
                if filename.endswith(('.txt', '.yml', '.yaml', '.csv')):
                    files.append(os.path.join(root, filename))
    
    logger.info(f"Triggering neologism mining for project {payload.project_id} with {len(files)} files.")
    game_profile = GAME_PROFILES_BY_ID.get(project.get("game_id") or "")
    game_name = (game_profile or {}).get("name", "Paradox Game")
    
    background_tasks.add_task(
        neologism_manager.run_mining_workflow,
        payload.project_id,
        files,
        payload.api_provider,
        project.get("source_language") or "en",
        payload.target_lang,
        game_name,
    )
    return {"status": "started", "message": "Mining started in background"}

@router.get("/api/neologisms/status/{project_id}")
def get_mining_status(project_id: str):
    """Return the latest neologism mining status for a project."""
    return neologism_manager.get_mining_status(project_id)
