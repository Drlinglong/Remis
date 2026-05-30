from fastapi import APIRouter, HTTPException
from scripts.core import workshop_formatter, deploy_manager
from scripts.schemas.tools import WorkshopRequest
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

router = APIRouter()

@router.post("/api/tools/generate_workshop_description")
def generate_workshop_description(payload: WorkshopRequest):
    original_desc = workshop_formatter.get_workshop_item_details(payload.item_id)
    if original_desc is None:
        raise HTTPException(status_code=502, detail="Failed to fetch from Steam Workshop.")
    formatted_bbcode = workshop_formatter.format_description_with_ai(
        original_description=original_desc, **payload.dict()
    )
    if "[AI Formatting Failed" in formatted_bbcode:
         raise HTTPException(status_code=500, detail=f"AI processing failed: {formatted_bbcode}")
    saved_path = workshop_formatter.archive_generated_description(
        project_id=payload.project_id, bbcode_content=formatted_bbcode, workshop_id=payload.item_id
    )
    return {"bbcode": formatted_bbcode, "saved_path": saved_path}

class DeployRequest(BaseModel):
    project_id: Optional[str] = None
    output_folder_name: str
    game_id: str
    target_deploy_path: Optional[str] = None
    workshop_path: Optional[str] = None
    clean_fake_loc: bool = False
    source_language: str = "english"

@router.post("/api/tools/deploy_mod")
def deploy_mod(payload: DeployRequest):
    result = deploy_manager.mod_deployer.deploy_mod(
        output_folder_name=payload.output_folder_name,
        game_id=payload.game_id,
        target_deploy_path=payload.target_deploy_path,
        workshop_path=payload.workshop_path,
        clean_fake_loc=payload.clean_fake_loc,
        source_language=payload.source_language
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

class DeployInfoRequest(BaseModel):
    project_id: Optional[str] = None
    game_id: str
    output_folder_name: str

@router.post("/api/tools/deploy_info")
async def get_deploy_info(payload: DeployInfoRequest):
    # 1. Default deploy folder
    default_mod_root = deploy_manager.mod_deployer.get_paradox_mod_dir(payload.game_id)
    default_deploy_path = ""
    if default_mod_root:
        default_deploy_path = str(default_mod_root / payload.output_folder_name)

    # 2. Detect workshop path and get source language
    detected_workshop_path = ""
    source_language = "english"
    remote_file_id = ""

    if payload.project_id:
        from scripts.shared.services import project_manager
        project = await project_manager.get_project(payload.project_id)
        if project:
            source_path = project.get("source_path")
            source_language = project.get("source_language", "english")
            if source_path:
                detected_workshop_path = deploy_manager.mod_deployer.locate_original_workshop_mod(source_path, payload.game_id) or ""
                remote_file_id = deploy_manager.mod_deployer.get_remote_file_id(Path(source_path), payload.game_id) or ""

    return {
        "default_deploy_path": default_deploy_path,
        "detected_workshop_path": detected_workshop_path,
        "remote_file_id": remote_file_id,
        "source_language": source_language
    }
