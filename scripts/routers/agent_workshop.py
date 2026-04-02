import os
import sqlite3
import re
import json
import logging
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
from scripts.core.project_json_manager import ProjectJsonManager

router = APIRouter(prefix="/api/agent-workshop", tags=["agent-workshop"])
logger = logging.getLogger(__name__)


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
    report_path: Optional[str] = None

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
    report_path: Optional[str] = None

class FixBatchResponse(BaseModel):
    results: List[BatchResultItem]


def _normalize_issue_dict(issue: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(issue)
    normalized.setdefault("file_name", "")
    normalized.setdefault("file_path", None)
    normalized.setdefault("source_file", None)
    normalized.setdefault("key", "")
    normalized.setdefault("line_number", None)
    normalized.setdefault("source_str", "")
    normalized.setdefault("target_str", "")
    normalized.setdefault("error_type", normalized.get("message", ""))
    normalized.setdefault("error_code", normalized.get("error_type"))
    normalized.setdefault("details", "")
    normalized.setdefault("severity", None)
    normalized.setdefault("text_sample", None)
    normalized.setdefault("workflow", None)
    normalized.setdefault("game_id", None)
    normalized.setdefault("project_name", None)
    normalized.setdefault("target_lang", None)
    normalized.setdefault("generated_at", None)
    normalized.setdefault("status", "detected")
    return normalized


def _issue_identity(issue: Dict[str, Any]) -> tuple:
    return (
        str(issue.get("file_name", "")),
        str(issue.get("key", "")),
        str(issue.get("error_code") or issue.get("error_type") or ""),
        str(issue.get("target_lang", "")),
        int(issue.get("line_number") or 0),
    )


def _load_sidecar_issue_file(path: Path) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []

    if isinstance(payload, dict):
        issues = payload.get("issues", [])
    elif isinstance(payload, list):
        issues = payload
    else:
        issues = []

    if not isinstance(issues, list):
        return []

    return [_normalize_issue_dict(item) for item in issues if isinstance(item, dict)]


def _active_issue_dicts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        _normalize_issue_dict(item)
        for item in items
        if str(item.get("status", "detected")).lower() not in {"fixed", "ignored"}
    ]


def _slugify_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "")
    return safe.strip("._") or "issue"


def _build_concise_reflection(error_type: str, details: str, source_str: str, target_str: str, suggested_fix: str) -> str:
    source_preview = (source_str or "").strip().replace("\n", " ")
    target_preview = (target_str or "").strip().replace("\n", " ")
    fix_preview = (suggested_fix or "").strip().replace("\n", " ")
    if len(source_preview) > 120:
        source_preview = source_preview[:117] + "..."
    if len(target_preview) > 120:
        target_preview = target_preview[:117] + "..."
    if len(fix_preview) > 120:
        fix_preview = fix_preview[:117] + "..."

    sentence_1 = f"问题类型：{error_type or '格式校验问题'}。"
    sentence_2 = f"原文与译文的关键差异是：{details or '译文没有正确保留原文中的技术标记或结构。'}"
    sentence_3 = f"建议修复为：{fix_preview or target_preview or source_preview}"
    return " ".join([sentence_1, sentence_2, sentence_3]).strip()


def _write_fix_report(
    project_root: str,
    file_name: str,
    key: str,
    source_str: str,
    target_str: str,
    error_type: str,
    details: str,
    suggested_fix: str,
    reflection: str,
) -> Optional[str]:
    try:
        reports_dir = Path(project_root) / ".agent_workshop_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None

    from datetime import datetime

    file_stub = _slugify_filename(Path(file_name or "file").name)
    key_stub = _slugify_filename(key)
    report_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_stub}_{key_stub}.md"
    report_path = reports_dir / report_name

    content = "\n".join([
        "# Agent Workshop Fix Report",
        "",
        f"- File: `{file_name}`",
        f"- Key: `{key}`",
        f"- Error Type: {error_type or 'Validation issue'}",
        f"- Details: {details or '--'}",
        "",
        "## Summary",
        "",
        reflection or "--",
        "",
        "## Source",
        "",
        "```text",
        source_str or "",
        "```",
        "",
        "## Broken Translation",
        "",
        "```text",
        target_str or "",
        "```",
        "",
        "## Suggested Fix",
        "",
        "```text",
        suggested_fix or "",
        "```",
    ])

    report_path.write_text(content, encoding="utf-8")
    return str(report_path)


def _load_project_sidecar_issues(project: Dict[str, Any]) -> List[ValidationIssue]:
    source_path = project.get("source_path")
    if not source_path:
        return []

    json_manager = ProjectJsonManager(source_path)
    config = json_manager.get_config()
    translation_dirs = config.get("translation_dirs", []) or []

    candidate_files: List[Path] = []
    for trans_dir in translation_dirs:
        trans_path = Path(trans_dir)
        workshop_path = trans_path / "workshop_issues.json"
        remis_path = trans_path / ValidationLogger.FILENAME
        if workshop_path.exists():
            candidate_files.append(workshop_path)
        elif remis_path.exists():
            candidate_files.append(remis_path)

    candidate_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    merged: Dict[tuple, Dict[str, Any]] = {}
    for sidecar_path in candidate_files:
        for issue in _load_sidecar_issue_file(sidecar_path):
            identity = _issue_identity(issue)
            if identity not in merged:
                merged[identity] = issue

    issues = [ValidationIssue(**item) for item in merged.values()]
    issues.sort(key=lambda item: (
        str(item.target_lang or ""),
        str(item.file_name or ""),
        int(item.line_number or 0),
        str(item.key or ""),
        str(item.error_code or item.error_type or ""),
    ))
    return issues


def _resolve_issue_target_path(project: Dict[str, Any], issue_file_path: Optional[str], issue_file_name: Optional[str]) -> Optional[Path]:
    if issue_file_path:
        candidate = Path(issue_file_path)
        if candidate.exists():
            return candidate

    source_path = project.get("source_path")
    if not source_path:
        return None

    json_manager = ProjectJsonManager(source_path)
    translation_dirs = json_manager.get_config().get("translation_dirs", []) or []

    if issue_file_name:
        for trans_dir in translation_dirs:
            candidate = Path(trans_dir) / issue_file_name
            if candidate.exists():
                return candidate

    fallback = Path(source_path) / (issue_file_name or "")
    if fallback.exists():
        return fallback
    return None


def _resolve_source_entries_for_translation(
    rel_path: str,
    source_lang_iso: str,
    source_files: Dict[str, Dict[str, Any]],
    source_cache: Dict[str, Dict[str, str]],
) -> tuple[Dict[str, str], Optional[str]]:
    from scripts.utils.i18n_utils import iso_to_paradox, paradox_to_iso

    match = re.search(r"(.+)_l_(?P<lang_suffix>[a-z_]+)\.yml$", rel_path)
    if not match:
        return {}, None

    lang_suffix = match.group("lang_suffix")
    target_lang = paradox_to_iso(lang_suffix)
    source_paradox = iso_to_paradox(source_lang_iso)
    source_rel_path = f"{match.group(1)}_l_{source_paradox}.yml"

    candidate_paths = [source_rel_path]

    source_basename = Path(source_rel_path).name
    for rel_source_path in source_files.keys():
        if rel_source_path not in candidate_paths and Path(rel_source_path).name == source_basename:
            candidate_paths.append(rel_source_path)

    for candidate_rel_path in candidate_paths:
        if candidate_rel_path in source_cache:
            return source_cache[candidate_rel_path], target_lang
        if candidate_rel_path in source_files:
            src_full_path = Path(source_files[candidate_rel_path]["file_path"])
            if src_full_path.exists():
                entries = dict(parse_loc_file(src_full_path))
                source_cache[candidate_rel_path] = entries
                logger.info(
                    "[AgentWorkshop] Matched source file %s for translation %s",
                    candidate_rel_path,
                    rel_path,
                )
                return entries, target_lang

    logger.warning(
        "[AgentWorkshop] Could not match source file for translation %s (expected base name %s)",
        rel_path,
        source_basename,
    )
    return {}, target_lang

@router.get("/load-cached", response_model=List[ValidationIssue])
async def load_cached_errors(project_id: str):
    """
    Loads previously scanned errors from the .remis_errors.json sidecar.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_errors = ValidationLogger.load_errors(project['source_path'])
    if current_errors:
        return [ValidationIssue(**e) for e in _active_issue_dicts(current_errors)]

    sidecar_issues = _load_project_sidecar_issues(project)
    if sidecar_issues:
        ValidationLogger.save_errors(project['source_path'], [issue.model_dump() for issue in sidecar_issues])
        return sidecar_issues

    return []

@router.get("/scan", response_model=List[ValidationIssue])
async def scan_project(project_id: str, force: bool = Query(False)):
    """
    Loads cached validation issues by default, or performs a fresh scan when forced.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_root = Path(project['source_path'])
    game_id = project['game_id']
    source_lang_iso = project.get('source_language', 'en')

    if not force:
        current_errors = ValidationLogger.load_errors(project['source_path'])
        if current_errors:
            logger.info(
                "[AgentWorkshop] Returning %s cached project-side issues for %s",
                len(current_errors),
                project_id,
            )
            return [ValidationIssue(**e) for e in _active_issue_dicts(current_errors)]

        sidecar_issues = _load_project_sidecar_issues(project)
        if sidecar_issues:
            logger.info(
                "[AgentWorkshop] Returning %s translation-sidecar issues for %s",
                len(sidecar_issues),
                project_id,
            )
            ValidationLogger.save_errors(project['source_path'], [issue.model_dump() for issue in sidecar_issues])
            return sidecar_issues

    logger.info(
        "[AgentWorkshop] Fresh scan started for project %s (%s) at %s",
        project.get("name", project_id),
        project_id,
        source_root,
    )
    
    # Select rules
    validator = PostProcessValidator()
    
    issues = []
    
    # 1. Get all project files
    files = await project_manager.get_project_files(project_id)
    logger.info("[AgentWorkshop] Project file inventory size: %s", len(files))
    
    def get_rel_path(p):
        try:
            return os.path.relpath(p, project['source_path']).replace('\\', '/')
        except ValueError:
            return p

    source_files = {get_rel_path(f['file_path']): f for f in files if f.get('file_type') == 'source'}
    translation_files = [f for f in files if f.get('file_type') == 'translation']
    logger.info(
        "[AgentWorkshop] Source files: %s, translation files: %s",
        len(source_files),
        len(translation_files),
    )
    
    # Cache for source file entries to avoid re-parsing
    source_cache = {}

    for file_info in translation_files:
        rel_path = get_rel_path(file_info['file_path'])
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            logger.warning("[AgentWorkshop] Translation file missing on disk: %s", file_info['file_path'])
            continue
        logger.info("[AgentWorkshop] Scanning translation file: %s", file_path)
            
        # Try to find the corresponding source file and determine target language
        source_entries = {}
        target_lang = None
        source_entries, target_lang = _resolve_source_entries_for_translation(
            rel_path,
            source_lang_iso,
            source_files,
            source_cache,
        )

        # Parse the translation file
        entries = dict(parse_loc_file(file_path))
        logger.info("[AgentWorkshop] Parsed %s translation entries from %s", len(entries), rel_path)
        
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
                    logger.info(
                        "[AgentWorkshop] Issue detected: file=%s key=%s level=%s message=%s",
                        rel_path,
                        key,
                        res.level.value,
                        res.message,
                    )
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
    logger.info("[AgentWorkshop] Fresh scan completed with %s issue(s)", len(issues))
                    
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
    concise_reflection = _build_concise_reflection(
        request.error_type,
        request.details,
        request.source_str,
        request.target_str,
        result.get("suggested_fix", ""),
    )
    result["reflection"] = concise_reflection
    result["report_path"] = None

    if result.get('status') == 'SUCCESS' and project:
        target_path = _resolve_issue_target_path(project, request.file_path, request.file_name)
        if target_path and target_path.exists():
            apply_translation_fix_to_file(target_path, request.key, result['suggested_fix'])
            
        ValidationLogger.update_error_status(
            project['source_path'], 
            request.file_name, 
            request.key, 
            "fixed"
        )
        result["report_path"] = _write_fix_report(
            project['source_path'],
            request.file_name,
            request.key,
            request.source_str,
            request.target_str,
            request.error_type,
            request.details,
            result.get("suggested_fix", ""),
            concise_reflection,
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
                original_issue = next(
                    (
                        issue for issue in request.issues
                        if issue.get("file_name") == res["file_name"] and issue.get("key") == res["key"]
                    ),
                    None
                )
                target_path = _resolve_issue_target_path(
                    project,
                    original_issue.get("file_path") if original_issue else None,
                    res["file_name"]
                )
                if target_path and target_path.exists():
                    apply_translation_fix_to_file(target_path, res["key"], res["suggested_fix"])
                    
                ValidationLogger.update_error_status(
                    project['source_path'], 
                    res["file_name"], 
                    res["key"], 
                    "fixed"
                )
                concise_reflection = _build_concise_reflection(
                    original_issue.get("error_type") if original_issue else "",
                    original_issue.get("details") if original_issue else "",
                    original_issue.get("source_str") if original_issue else "",
                    original_issue.get("target_str") if original_issue else "",
                    res.get("suggested_fix", ""),
                )
                res["report_path"] = _write_fix_report(
                    project['source_path'],
                    res["file_name"],
                    res["key"],
                    original_issue.get("source_str") if original_issue else "",
                    original_issue.get("target_str") if original_issue else "",
                    original_issue.get("error_type") if original_issue else "",
                    original_issue.get("details") if original_issue else "",
                    res.get("suggested_fix", ""),
                    concise_reflection,
                )
            else:
                res["report_path"] = None
            final_results.append(BatchResultItem(**res))
            
    return FixBatchResponse(results=final_results)
