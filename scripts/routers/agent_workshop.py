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

from scripts.core.loc_parser import parse_loc_file
from scripts.utils.validation_logger import ValidationLogger

router = APIRouter(prefix="/api/agent-workshop", tags=["agent-workshop"])


def _resolve_workshop_model_config(
    requested_provider: Optional[str] = None,
    requested_model: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    from scripts.app_settings import API_PROVIDERS, DEFAULT_API_PROVIDER, config_manager

    provider_name = requested_provider or DEFAULT_API_PROVIDER
    provider_config = API_PROVIDERS.get(provider_name, {})
    provider_overrides = config_manager.get_value("provider_config", {}).get(provider_name, {})

    model_name = requested_model
    if not model_name:
        model_name = provider_overrides.get("selected_model")
    if not model_name:
        model_name = provider_config.get("default_model")

    return provider_name, model_name

class ValidationIssue(BaseModel):
    file_name: str
    file_path: Optional[str] = None
    source_file: Optional[str] = None
    key: str
    line_number: Optional[int] = None
    source_str: str
    target_str: str
    error_type: str
    error_code: Optional[str] = None
    details: str
    severity: Optional[str] = None
    text_sample: Optional[str] = None
    workflow: Optional[str] = None
    game_id: Optional[str] = None
    project_name: Optional[str] = None
    target_lang: Optional[str] = None
    generated_at: Optional[str] = None
    status: Optional[str] = "detected" # New: status tracking

class FixRequest(BaseModel):
    project_id: str
    file_name: str
    key: str
    source_str: str
    target_str: str
    error_type: str
    details: str
    api_provider: Optional[str] = None
    api_model: Optional[str] = None

class FixResult(BaseModel):
    suggested_fix: str
    reflection: str
    status: str
    parity_message: str

class FixBatchRequest(BaseModel):
    project_id: str
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    issues: List[Dict[str, Any]] # Collection of the original issue fields

class BatchResultItem(BaseModel):
    file_name: str
    key: str
    suggested_fix: str
    status: str
    parity_message: str

class FixBatchResponse(BaseModel):
    results: List[BatchResultItem]

@router.get("/load-cached", response_model=List[ValidationIssue])
async def load_cached_errors(project_id: str):
    """
    Loads previously scanned errors from the .remis_errors.json sidecar.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    errors = ValidationLogger.load_errors(project['source_path'])
    return [ValidationIssue(**e) for e in errors]

@router.get("/scan", response_model=List[ValidationIssue])
async def scan_project(project_id: str):
    """
    Scans all translation files in a project for validation errors and caches them.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    source_root = Path(project['source_path'])
    game_id = project['game_id']
    source_lang_iso = project.get('source_language', 'en')
    
    # Select rules
    validator = PostProcessValidator()
    
    issues = []
    
    # 1. Get all project files
    files = await project_manager.get_project_files(project_id)
    
    def get_rel_path(p):
        try:
            return os.path.relpath(p, project['source_path']).replace('\\', '/')
        except ValueError:
            return p

    source_files = {get_rel_path(f['file_path']): f for f in files if f.get('file_type') == 'source'}
    translation_files = [f for f in files if f.get('file_type') == 'translation']
    
    # Cache for source file entries to avoid re-parsing
    source_cache = {}

    for file_info in translation_files:
        rel_path = get_rel_path(file_info['file_path'])
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            continue
            
        # Try to find the corresponding source file and determine target language
        match = re.search(r"(.+)_l_(?P<lang_suffix>[a-z_]+)\.yml$", rel_path)
        source_entries = {}
        target_lang = None
        
        if match:
            from scripts.utils.i18n_utils import iso_to_paradox, paradox_to_iso
            lang_suffix = match.group('lang_suffix')
            target_lang = paradox_to_iso(lang_suffix)
            
            source_paradox = iso_to_paradox(source_lang_iso)
            source_rel_path = f"{match.group(1)}_l_{source_paradox}.yml"
            
            if source_rel_path in source_cache:
                source_entries = source_cache[source_rel_path]
            elif source_rel_path in source_files:
                src_full_path = Path(source_files[source_rel_path]['file_path'])
                if src_full_path.exists():
                    source_entries = dict(parse_loc_file(src_full_path))
                    source_cache[source_rel_path] = source_entries

        # Parse the translation file
        entries = dict(parse_loc_file(file_path))
        
        for key, value in entries.items():
            try:
                results = validator.validate_entry(
                    game_id, 
                    key, 
                    value, 
                    source_value=source_entries.get(key, ""),
                    target_lang=target_lang
                )
            except ValueError as e:
                # Catch strict game ID validation error
                raise HTTPException(status_code=400, detail=str(e))
                
            for res in results:
                if res.level.value in ["error", "warning"]:
                    issues.append(ValidationIssue(
                        file_name=file_info['relative_path'] if 'relative_path' in file_info else get_rel_path(file_info['file_path']),
                        key=key,
                        source_str=source_entries.get(key, ""),
                        target_str=value,
                        error_type=res.message,
                        details=res.details or "",
                        status="detected"
                    ))
    
    # Cache results
    ValidationLogger.save_errors(project['source_path'], [i.dict() for i in issues])
                    
    return issues

def apply_translation_fix_to_file(file_path: Path, key_to_fix: str, new_value: str) -> bool:
    from scripts.core.loc_parser import parse_loc_file_with_lines
    try:
        entries = parse_loc_file_with_lines(file_path)
        target_line = -1
        for key, value, line_number in entries:
            # Full key matching ensures we get `key:0` or just `key`
            if key == key_to_fix or key.split(':')[0] == key_to_fix.split(':')[0]:
                target_line = line_number
                break
                
        if target_line != -1:
            idx = target_line - 1
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
                
            old_line = lines[idx]
            first_quote = old_line.find('"')
            # Look for the last quote from right, but not an escaped quote.
            # Using rfind on `"` is ok because our Loc parser logic relies on simple quote framing.
            last_quote = old_line.rfind('"', first_quote + 1)
            
            if first_quote != -1 and last_quote != -1:
                safe_val = new_value.replace('"', r'\"')
                lines[idx] = old_line[:first_quote+1] + safe_val + old_line[last_quote:]
                with open(file_path, 'w', encoding='utf-8-sig') as f:
                    f.writelines(lines)
                return True
        return False
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to apply fix to {file_path}: {e}")
        return False


@router.post("/fix", response_model=FixResult)
async def fix_issue(request: FixRequest):
    """
    Initiates the Reflexion Fix Workflow for a specific issue.
    """
    from scripts.core.api_handler import get_handler
    
    provider_name, model_name = _resolve_workshop_model_config(
        requested_provider=request.api_provider,
        requested_model=request.api_model,
    )
    
    handler = get_handler(provider_name, model_name=model_name)
    
    project = await project_manager.get_project(request.project_id)
    game_id = project.get('game_id', 'vic3') if project else 'vic3'
    
    agent = ReflexionFixAgent(handler)
    result = await agent.fix_issue_loop(
        request.source_str, 
        request.target_str, 
        request.error_type, 
        request.details,
        game_id=game_id
    )
    
    # If successful, apply fix to file and mark as fixed in local log
    if result.get('status') == 'SUCCESS' and project:
        target_path = Path(project['source_path']) / request.file_name
        if target_path.exists():
            apply_translation_fix_to_file(target_path, request.key, result['suggested_fix'])
            
        ValidationLogger.update_error_status(
            project['source_path'], 
            request.file_name, 
            request.key, 
            "fixed"
        )
    
    return FixResult(**result)


@router.post("/fix-batch", response_model=FixBatchResponse)
async def fix_batch(request: FixBatchRequest):
    """
    Initiates the Reflexion Fix Workflow for a batch of issues.
    """
    from scripts.core.api_handler import get_handler
    
    provider_name, model_name = _resolve_workshop_model_config(
        requested_provider=request.api_provider,
        requested_model=request.api_model,
    )
    
    handler = get_handler(provider_name, model_name=model_name)
    
    project = await project_manager.get_project(request.project_id)
    game_id = project.get('game_id', 'vic3') if project else 'vic3'
    
    agent = ReflexionFixAgent(handler)
    batch_result = await agent.fix_batch_loop(
        issues=request.issues,
        game_id=game_id
    )
    
    final_results = []
    
    if project:
        for res in batch_result.get("results", []):
            if res.get('status') == 'SUCCESS':
                target_path = Path(project['source_path']) / res["file_name"]
                if target_path.exists():
                    apply_translation_fix_to_file(target_path, res["key"], res["suggested_fix"])
                    
                ValidationLogger.update_error_status(
                    project['source_path'], 
                    res["file_name"], 
                    res["key"], 
                    "fixed"
                )
            final_results.append(BatchResultItem(**res))
            
    return FixBatchResponse(results=final_results)
