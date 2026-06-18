import os
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from scripts.core.neologism_manager import neologism_manager
from scripts.shared.services import project_manager, glossary_manager
from scripts.shared import task_state
from scripts.schemas.neologism import ApproveNeologismRequest, UpdateNeologismRequest, MineNeologismsRequest
from scripts.app_settings import GAME_PROFILES_BY_ID

logger = logging.getLogger(__name__)

router = APIRouter()

def _normalize_term(term: str) -> str:
    return " ".join((term or "").casefold().split())

async def _build_main_glossary_duplicate_index(game_id: str, source_lang: str) -> dict:
    glossaries = await glossary_manager.get_available_glossaries(game_id)
    main_glossary = next((g for g in glossaries if g.get("is_main")), None)
    if not main_glossary or not main_glossary.get("glossary_id"):
        return {}

    entries = await glossary_manager.get_entries_for_glossary_ids([main_glossary["glossary_id"]])
    duplicate_index = {}
    for entry in entries:
        translations = entry.get("translations") or {}
        source_term = translations.get(source_lang) or translations.get("en")
        if not source_term:
            continue
        key = _normalize_term(source_term)
        duplicate_index.setdefault(key, []).append({
            "entry_id": entry.get("entry_id"),
            "glossary_id": entry.get("glossary_id"),
            "glossary_name": main_glossary.get("name"),
            "source_term": source_term,
            "translations": translations,
        })
    return duplicate_index

@router.get("/api/neologisms")
def list_neologisms(project_id: Optional[str] = None):
    """List neologism candidates, optionally filtered by project."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id query parameter is required")
    return neologism_manager.get_pending_candidates(project_id)

@router.post("/api/neologisms/{candidate_id}/approve")
async def approve_neologism(candidate_id: str, payload: ApproveNeologismRequest):
    """Approve a neologism candidate and add to glossary."""
    project = await project_manager.get_project(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project_glossary = await glossary_manager.get_or_create_project_glossary(
        project["game_id"],
        payload.project_id,
        project.get("name"),
    )
    if not project_glossary or not project_glossary.get("glossary_id"):
        raise HTTPException(status_code=500, detail="Failed to prepare project glossary")

    if await neologism_manager.approve_candidate(
        payload.project_id,
        candidate_id,
        payload.final_translation,
        project_glossary["glossary_id"],
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
    ):
        logger.info(f"Approved neologism candidate {candidate_id} for project {payload.project_id}")
        return {"status": "success", "glossary": project_glossary}
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
    task_id = str(uuid.uuid4())
    task_state.create_task(task_id, status="pending", log_message="Neologism mining queued.")
    task_state.init_progress(task_id, {
        "total": len(files),
        "current": 0,
        "percent": 0,
        "stage": "Queued",
        "current_file": "",
    })
    task_state.update_task(
        task_id,
        status="starting",
        summary={
            "project_id": payload.project_id,
            "new_terms": 0,
            "duplicate_terms": 0,
        },
        fields={"kind": "neologism_mining"},
        push=True,
    )
    duplicate_index = await _build_main_glossary_duplicate_index(
        project["game_id"],
        project.get("source_language") or "en",
    )
    
    background_tasks.add_task(
        neologism_manager.run_mining_workflow,
        payload.project_id,
        files,
        payload.api_provider,
        project.get("source_language") or "en",
        payload.target_lang,
        game_name,
        task_id,
        duplicate_index,
    )
    return {"task_id": task_id, "status": "started", "message": "Mining started in background"}

@router.get("/api/neologisms/project-glossary/{project_id}")
async def get_project_neologism_glossary(project_id: str):
    """Return the dedicated project glossary if it already exists."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    glossary = await glossary_manager.get_project_glossary(
        project["game_id"],
        project_id,
    )
    return glossary or {
        "glossary_id": None,
        "game_id": project["game_id"],
        "name": glossary_manager.get_project_glossary_name(project_id),
        "description": f"Auto-mined project glossary for {project.get('name') or project_id}",
        "is_main": False,
        "pending_creation": True,
    }

@router.get("/api/neologisms/status/{project_id}")
def get_mining_status(project_id: str):
    """Return the latest neologism mining status for a project."""
    return neologism_manager.get_mining_status(project_id)
