import os
import sqlite3
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from scripts.utils.post_process_validator import PostProcessValidator
from scripts.config.validators.hoi4_rules import RULES as HOI4_RULES
from scripts.config.validators.vic3_rules import RULES as VIC3_RULES
from scripts.shared.services import project_manager
from scripts.core.agents.fix_agent import ReflexionFixAgent
from scripts.core.base_handler import BaseApiHandler # For typing or creation

router = APIRouter(prefix="/api/agent-workshop", tags=["agent-workshop"])

class ValidationIssue(BaseModel):
    file_name: str
    key: str
    source_str: str   # Renamed to avoid 'source' shadowing in some contexts
    target_str: str
    error_type: str
    details: str

class FixRequest(BaseModel):
    project_id: str
    file_name: str
    key: str
    source_str: str
    target_str: str
    error_type: str
    details: str

class FixResult(BaseModel):
    suggested_fix: str
    reflection: str
    status: str
    parity_message: str

@router.get("/scan", response_model=List[ValidationIssue])
async def scan_project(project_id: str):
    """
    Scans all translation files in a project for validation errors.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    source_root = Path(project['source_path'])
    game_id = project['game_id']
    source_lang_iso = project.get('source_language', 'en')
    
    # Select rules
    rules = HOI4_RULES if game_id == "hoi4" else VIC3_RULES
    validator = PostProcessValidator(rules)
    from scripts.core.loc_parser import parse_loc_file
    
    issues = []
    
    # 1. Get all project files
    files = await project_manager.get_project_files(project_id)
    
    source_files = {f['relative_path']: f for f in files if f['type'] == 'source'}
    translation_files = [f for f in files if f['type'] == 'translation']
    
    # Cache for source file entries to avoid re-parsing
    source_cache = {}

    for file_info in translation_files:
        file_path = source_root / file_info['relative_path']
        if not file_path.exists():
            continue
            
        # Try to find the corresponding source file
        rel_path = file_info['relative_path']
        match = re.search(r"(.+)_l_[a-z]+\.yml$", rel_path)
        source_entries = {}
        
        if match:
            from scripts.utils.i18n_utils import iso_to_paradox
            source_paradox = iso_to_paradox(source_lang_iso)
            source_rel_path = f"{match.group(1)}_l_{source_paradox}.yml"
            
            if source_rel_path in source_cache:
                source_entries = source_cache[source_rel_path]
            elif source_rel_path in source_files:
                src_full_path = source_root / source_rel_path
                if src_full_path.exists():
                    source_entries = dict(parse_loc_file(src_full_path))
                    source_cache[source_rel_path] = source_entries

        # Parse the translation file
        entries = dict(parse_loc_file(file_path))
        
        for key, value in entries.items():
            results = validator.validate(value, key=key)
            for res in results:
                if res.level.value == "error":
                    issues.append(ValidationIssue(
                        file_name=file_info['relative_path'],
                        key=key,
                        source_str=source_entries.get(key, ""),
                        target_str=value,
                        error_type=res.message,
                        details=res.details or ""
                    ))
                    
    return issues

@router.post("/fix", response_model=FixResult)
async def fix_issue(request: FixRequest):
    """
    Initiates the Reflexion Fix Workflow for a specific issue.
    """
    # Create a handler (reuse or create new)
    from scripts.core.api_handler import get_handler
    from scripts.app_settings import get_default_translation_config
    
    config = get_default_translation_config()
    # Note: get_handler handles the mapping, but we might need the API Key from somewhere.
    # Usually handlers pull from environment or settings.
    handler = get_handler(config['provider'], model_name=config['model'])
    
    project = await project_manager.get_project(request.project_id)
    game_id = project.get('game_id', 'vic3') if project else 'vic3'
    
    agent = ReflexionFixAgent(handler)
    result = await agent.fix_issue(
        request.source_str, 
        request.target_str, 
        request.error_type, 
        request.details,
        game_id=game_id
    )
    
    return FixResult(**result)
