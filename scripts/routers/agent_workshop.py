import os
import sqlite3
import re
import json
import hashlib
import logging
import asyncio
import time
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from scripts.utils.post_process_validator import PostProcessValidator
from scripts.config.validators.hoi4_rules import RULES as HOI4_RULES
from scripts.config.validators.vic3_rules import RULES as VIC3_RULES
from scripts.shared.services import project_manager
from scripts.shared import task_state
from scripts.core.agents.fix_agent import ReflexionFixAgent
from scripts.core.base_handler import BaseApiHandler # For typing or creation

from scripts.core.loc_parser import parse_loc_file
from scripts.utils.validation_logger import ValidationLogger
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.core.services.workshop_issue_export_service import WorkshopIssueExportService, resolve_dynamic_valid_tags
from scripts.schemas.tasks import TaskCreator

router = APIRouter(prefix="/api/agent-workshop", tags=["agent-workshop"])
logger = logging.getLogger(__name__)
validation_sidecars = ValidationSidecarService()


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
    file_id: Optional[str] = None
    file_path: Optional[str] = None
    source_file: Optional[str] = None
    key: str
    line_number: Optional[int] = None
    source_str: str
    source_context_status: Optional[str] = "found"
    source_context_origin: Optional[str] = "source_file"
    source_context_warning: Optional[str] = None
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
    failure_reason: Optional[str] = None
    failure_details: Optional[str] = None
    last_suggested_fix: Optional[str] = None
    last_attempt_at: Optional[str] = None

class WorkshopRepairApproval(BaseModel):
    approved: bool = Field(
        default=False,
        description="True only after the user approves this exact repair scope.",
    )
    issue_count: int = Field(
        ge=1,
        description="Number of issues shown to the user when approval was granted.",
    )
    api_provider: str = Field(
        min_length=1,
        description="Provider identifier shown in the approval prompt.",
    )
    api_model: str = Field(
        min_length=1,
        description="Model identifier shown in the approval prompt.",
    )


class FixRequest(BaseModel):
    project_id: str
    file_name: str
    file_path: Optional[str] = None
    key: str
    source_str: str
    source_context_status: Optional[str] = "found"
    source_context_origin: Optional[str] = "source_file"
    source_context_warning: Optional[str] = None
    target_str: str
    error_type: str
    details: str
    api_provider: str = Field(min_length=1)
    api_model: str = Field(min_length=1)
    approval: Optional[WorkshopRepairApproval] = Field(
        default=None,
        description="Approval snapshot bound to this single model-backed write.",
    )

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
    max_retries: Optional[int] = None
    issues: List[Dict[str, Any]] # Collection of the original issue fields
    approval: Optional[WorkshopRepairApproval] = Field(
        default=None,
        description="Approval snapshot bound to this batch request.",
    )

class BatchAttemptSummary(BaseModel):
    attempt: int
    max_retries: int
    active_count: int
    used_reflection: bool = False
    reflections_generated: int = 0
    fixed_count: int = 0
    remaining_count: int = 0
    status: str = "completed"
    message: str = ""

class BatchResultItem(BaseModel):
    file_name: str
    key: str
    suggested_fix: str
    status: str
    parity_message: str
    report_path: Optional[str] = None

class FixBatchResponse(BaseModel):
    results: List[BatchResultItem]
    attempts: List[BatchAttemptSummary] = Field(default_factory=list)
    max_retries: int = 3

class FixRunRequest(BaseModel):
    project_id: str
    api_provider: str = Field(min_length=1)
    api_model: str = Field(min_length=1)
    batch_size_limit: Optional[int] = None
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40
    max_retries: Optional[int] = 3
    issues: List[Dict[str, Any]]
    approval: Optional[WorkshopRepairApproval] = Field(
        default=None,
        description="Approval snapshot bound to the full governed repair run.",
    )
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        description="Caller-stable key used to safely reuse an identical accepted run.",
    )
    created_by: TaskCreator = Field(
        default_factory=TaskCreator,
        description="Structured actor identity for user, Remis Agent, or automation callers.",
    )

class FixRunResponse(BaseModel):
    task_id: str
    status: str = "queued"
    reused: bool = False
    allowed_actions: List[str] = Field(default_factory=lambda: ["view_task"])


def _fix_run_fingerprint(request: FixRunRequest) -> str:
    governed_scope = {
        "project_id": request.project_id,
        "api_provider": request.api_provider,
        "api_model": request.api_model,
        "batch_size_limit": request.batch_size_limit,
        "concurrency_limit": request.concurrency_limit,
        "rpm_limit": request.rpm_limit,
        "max_retries": request.max_retries,
        "issues": request.issues,
    }
    canonical = json.dumps(governed_scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_repair_approval(
    approval: Optional[WorkshopRepairApproval],
    *,
    project_id: str,
    issue_count: int,
    api_provider: str,
    api_model: str,
) -> None:
    if (
        approval is None
        or not approval.approved
        or approval.issue_count != issue_count
        or approval.api_provider != api_provider
        or approval.api_model != api_model
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_required",
                "message": "Explicit approval is required for this exact Format Repair scope.",
                "retryable": False,
                "approval_scope": {
                    "project_id": project_id,
                    "issue_count": issue_count,
                    "api_provider": api_provider,
                    "api_model": api_model,
                    "writes_project_files": True,
                    "may_incur_model_cost": True,
                },
            },
        )


async def _require_repairable_project(project_id: str) -> Dict[str, Any]:
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "project_not_found",
                "message": "The selected Format Repair project no longer exists.",
                "project_id": project_id,
            },
        )
    status = str(project.get("status") or "active").lower()
    if status != "active":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "project_not_active",
                "message": "Restore this project before running Format Repair.",
                "project_id": project_id,
                "project_status": status,
            },
        )
    return project


def _normalize_issue_dict(issue: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(issue)
    normalized.setdefault("file_name", "")
    normalized.setdefault("file_path", None)
    normalized.setdefault("source_file", None)
    normalized.setdefault("key", "")
    normalized.setdefault("line_number", None)
    normalized.setdefault("source_str", "")
    normalized.setdefault("source_context_status", "found" if normalized.get("source_str") else "missing")
    normalized.setdefault("source_context_origin", "source_file" if normalized.get("source_str") else "none")
    normalized.setdefault("source_context_warning", None)
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
    normalized.setdefault("failure_reason", None)
    normalized.setdefault("failure_details", None)
    normalized.setdefault("last_suggested_fix", None)
    normalized.setdefault("last_attempt_at", None)
    return normalized


def _active_issue_dicts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        _normalize_issue_dict(item)
        for item in items
        if str(item.get("status", "detected")).lower() not in {"fixed", "ignored"}
    ]


def _slugify_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "")
    return safe.strip("._") or "issue"


def _build_concise_reflection(
    error_type: str,
    details: str,
    source_str: str,
    target_str: str,
    suggested_fix: str,
    source_context_status: str = "found",
    source_context_origin: str = "source_file",
    source_context_warning: Optional[str] = None,
) -> str:
    source_preview = (source_str or "").strip().replace("\n", " ")
    target_preview = (target_str or "").strip().replace("\n", " ")
    fix_preview = (suggested_fix or "").strip().replace("\n", " ")
    if len(source_preview) > 120:
        source_preview = source_preview[:117] + "..."
    if len(target_preview) > 120:
        target_preview = target_preview[:117] + "..."
    if len(fix_preview) > 120:
        fix_preview = fix_preview[:117] + "..."

    sentences = [
        f"问题类型：{error_type or '格式校验问题'}。",
        f"原文与译文的关键差异是：{details or '译文没有正确保留原文中的技术标记或结构。'}",
    ]
    if source_context_status == "missing":
        sentences.append(
            source_context_warning
            or "未找到原文上下文，我只能基于损坏译文即兴修补，结果主要保证格式可用，不保证语义最优。"
        )
    elif source_context_status == "fallback_found":
        sentences.append(
            source_context_warning
            or f"原文未能从当前源文件获取，已从后备来源（{source_context_origin}）补回原文上下文。"
        )
    sentences.append(f"建议修复为：{fix_preview or target_preview or source_preview}")
    return " ".join(sentences).strip()


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
    source_context_status: str = "found",
    source_context_origin: str = "source_file",
    source_context_warning: Optional[str] = None,
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
        "# Format Repair Report",
        "",
        f"- File: `{file_name}`",
        f"- Key: `{key}`",
        f"- Error Type: {error_type or 'Validation issue'}",
        f"- Details: {details or '--'}",
        f"- Source Context Status: `{source_context_status or 'unknown'}`",
        f"- Source Context Origin: `{source_context_origin or 'unknown'}`",
        f"- Source Context Warning: {source_context_warning or '--'}",
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


def _load_project_sidecar_issues(
    project: Dict[str, Any],
    project_files: List[Dict[str, Any]],
    selected_sidecar_path: Optional[str] = None,
) -> List[ValidationIssue]:
    source_path = project.get("source_path")
    if not source_path:
        return []

    raw_issues = validation_sidecars.attach_project_file_ids(
        validation_sidecars.current_translation_issues(source_path, selected_sidecar_path),
        project_files,
    )
    issues = [
        ValidationIssue(**_normalize_issue_dict(item))
        for item in raw_issues
    ]
    issues.sort(key=lambda item: (
        str(item.target_lang or ""),
        str(item.file_name or ""),
        int(item.line_number or 0),
        str(item.key or ""),
        str(item.error_code or item.error_type or ""),
    ))
    return issues


def _relative_to_any(path: Path, roots: List[Path], fallback_root: Path) -> str:
    resolved_path = path.resolve()
    for root in roots:
        try:
            return resolved_path.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    try:
        return os.path.relpath(resolved_path, fallback_root.resolve()).replace("\\", "/")
    except ValueError:
        return str(path)


def _find_translation_root(path: Path, translation_roots: List[Path]) -> Optional[Path]:
    resolved_path = path.resolve(strict=False)
    for root in translation_roots:
        try:
            resolved_path.relative_to(root.resolve(strict=False))
            return root
        except ValueError:
            continue
    return None


def _write_fresh_scan_sidecars(
    project: Dict[str, Any],
    translation_roots: List[Path],
    issues: List[ValidationIssue],
) -> None:
    if not translation_roots:
        return

    exporter = WorkshopIssueExportService()
    project_id = str(project.get("project_id") or "")
    run_id = str(uuid.uuid4())
    resolved_roots = {
        root.resolve(strict=False): root
        for root in translation_roots
    }
    issues_by_root: Dict[Path, List[Dict[str, Any]]] = {
        resolved_root: []
        for resolved_root in resolved_roots
    }

    for issue in issues:
        if not issue.file_path:
            continue
        root = _find_translation_root(Path(issue.file_path), translation_roots)
        if root is None:
            continue
        resolved_root = root.resolve(strict=False)
        issue_dict = issue.model_dump()
        if project_id:
            issue_dict["project_id"] = project_id
        issue_dict["run_id"] = run_id
        issues_by_root.setdefault(resolved_root, []).append(issue_dict)

    for resolved_root, root in resolved_roots.items():
        try:
            exporter.write_issues(
                root,
                issues_by_root.get(resolved_root, []),
                project_id=project_id,
                run_id=run_id,
            )
        except Exception as exc:
            logger.warning(
                "[AgentWorkshop] Failed to refresh validation sidecar for %s: %s",
                root,
                exc,
            )


def _scoped_translation_roots(
    project_root: str,
    configured_roots: List[Path],
    selected_sidecar_path: Optional[str],
) -> List[Path]:
    if not selected_sidecar_path:
        return configured_roots

    status = validation_sidecars.load_status(project_root, selected_sidecar_path)
    if not status:
        return configured_roots

    scoped_roots: List[Path] = []
    seen = set()
    for source_path in status.get("source_paths", []):
        path = Path(source_path)
        if path.name not in {"workshop_issues.json", ValidationLogger.FILENAME}:
            continue
        root = path.parent.resolve(strict=False)
        if str(root).lower() in seen:
            continue
        seen.add(str(root).lower())
        scoped_roots.append(root)

    return scoped_roots or configured_roots


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
    source_root: Optional[Path] = None,
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

    if source_root and source_root.exists():
        for found in source_root.rglob(source_basename):
            if found.name.lower() == source_basename.lower() and found.exists():
                entries = dict(parse_loc_file(found))
                cache_key = _relative_to_any(found, [source_root], source_root)
                source_cache[cache_key] = entries
                logger.info(
                    "[AgentWorkshop] Matched source file by disk fallback %s for translation %s",
                    cache_key,
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
async def load_cached_errors(project_id: str, sidecar_path: Optional[str] = None):
    """
    Loads previously scanned errors from the .remis_errors.json sidecar.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_errors = ValidationLogger.load_errors(project['source_path'])
    project_files = await project_manager.get_project_files(project_id)
    sidecar_issues = _load_project_sidecar_issues(project, project_files, sidecar_path)
    if sidecar_issues:
        active_issues = [
            issue for issue in sidecar_issues
            if str(issue.status or "detected").lower() not in {"fixed", "ignored"}
        ]
        ValidationLogger.save_errors(project['source_path'], [issue.model_dump() for issue in active_issues])
        return [issue.model_dump() for issue in active_issues]

    if not sidecar_path and current_errors:
        return _active_issue_dicts(current_errors)

    return []

async def _scan_project_issues(
    project_id: str,
    force: bool = False,
    sidecar_path: Optional[str] = None,
):
    """
    Loads cached validation issues by default, or performs a fresh scan when forced.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_root = Path(project['source_path'])
    game_id = project['game_id']
    source_lang_iso = project.get('source_language', 'en')
    from scripts.app_settings import GAME_ID_ALIASES, GAME_PROFILES_BY_ID

    normalized_game_id = GAME_ID_ALIASES.get(str(game_id).lower(), game_id)
    game_profile = GAME_PROFILES_BY_ID.get(normalized_game_id) or GAME_PROFILES_BY_ID.get(game_id) or {"id": game_id}

    if not force:
        current_errors = ValidationLogger.load_errors(project['source_path'])
        project_files = await project_manager.get_project_files(project_id)
        sidecar_issues = _load_project_sidecar_issues(project, project_files, sidecar_path)
        if sidecar_issues:
            logger.info(
                "[AgentWorkshop] Returning %s current translation-sidecar issues for %s",
                len(sidecar_issues),
                project_id,
            )
            active_issues = [
                issue for issue in sidecar_issues
                if str(issue.status or "detected").lower() not in {"fixed", "ignored"}
            ]
            ValidationLogger.save_errors(project['source_path'], [issue.model_dump() for issue in active_issues])
            return [issue.model_dump() for issue in active_issues]

        if not sidecar_path and current_errors:
            logger.info(
                "[AgentWorkshop] Returning %s cached project-side issues for %s",
                len(current_errors),
                project_id,
            )
            return _active_issue_dicts(current_errors)

    logger.info(
        "[AgentWorkshop] Fresh scan started for project %s (%s) at %s",
        project.get("name", project_id),
        project_id,
        source_root,
    )
    
    # Select rules
    validator = PostProcessValidator()
    dynamic_valid_tags = resolve_dynamic_valid_tags(game_profile, source_root)
    
    issues = []
    
    # 1. Get all project files
    files = await project_manager.get_project_files(project_id)
    logger.info("[AgentWorkshop] Project file inventory size: %s", len(files))
    
    json_manager = ProjectJsonManager(project['source_path'])
    configured_translation_roots = [
        Path(path)
        for path in (json_manager.get_config().get("translation_dirs", []) or [])
    ]
    translation_roots = _scoped_translation_roots(
        project['source_path'],
        configured_translation_roots,
        sidecar_path,
    )
    logger.info(
        "[AgentWorkshop] Scan translation roots: %s",
        [str(root) for root in translation_roots],
    )

    def get_source_rel_path(p):
        return _relative_to_any(Path(p), [source_root], source_root)

    def get_translation_rel_path(p):
        return _relative_to_any(Path(p), translation_roots, source_root)

    source_files = {get_source_rel_path(f['file_path']): f for f in files if f.get('file_type') == 'source'}
    translation_files = [
        f for f in files
        if f.get('file_type') == 'translation'
        and (
            not translation_roots
            or _find_translation_root(Path(f.get('file_path', '')), translation_roots) is not None
        )
    ]
    logger.info(
        "[AgentWorkshop] Source files: %s, translation files: %s",
        len(source_files),
        len(translation_files),
    )
    
    # Cache for source file entries to avoid re-parsing
    source_cache = {}

    for file_info in translation_files:
        file_path = Path(file_info['file_path'])
        rel_path = file_info.get('relative_path') or get_translation_rel_path(file_path)
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
            source_root=source_root,
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
                    target_lang=target_lang,
                    dynamic_valid_tags=dynamic_valid_tags,
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
                        file_name=rel_path,
                        file_id=file_info.get('file_id'),
                        file_path=str(file_path),
                        key=key,
                        source_str=source_entries.get(key, ""),
                        source_context_status="found" if source_entries.get(key, "") else "missing",
                        source_context_origin="source_file" if source_entries.get(key, "") else "none",
                        source_context_warning=None if source_entries.get(key, "") else "Original source text was not found during direct project scan. The repair will rely on best-effort inference unless another fallback source is available.",
                        target_str=value,
                        error_type=res.message,
                        details=res.details or "",
                        target_lang=target_lang,
                        status="detected"
                    ))
    
    # Cache results
    ValidationLogger.save_errors(project['source_path'], [i.model_dump() for i in issues])
    _write_fresh_scan_sidecars(project, translation_roots, issues)
    logger.info("[AgentWorkshop] Fresh scan completed with %s issue(s)", len(issues))
                    
    return [i.model_dump() for i in issues]


@router.get("/scan", response_model=List[ValidationIssue])
async def scan_project(
    response: Response,
    project_id: str,
    force: bool = Query(False),
    sidecar_path: Optional[str] = None,
):
    """
    Runs the deterministic format scan and records it in the shared task ledger.

    The list response remains backward compatible. The exact task identity is
    returned in a response header so the UI can refresh the Task Center or open
    this scan directly without inventing a second scan record.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_id = str(uuid.uuid4())
    input_scope = sidecar_path or project.get("source_path")
    task_state.create_task(
        task_id,
        status="processing",
        log_message="Format scan started.",
        fields={
            "kind": "agent_workshop_scan",
            "project_id": project_id,
            "title": "Format scan",
            "source_route": "/agent-workshop",
            "created_by": {"type": "user"},
            "blocking": False,
            "workflow_context": {
                "mode": "format_scan",
                "project_id": project_id,
                "input_scope": input_scope,
                "force": force,
            },
            "progress": {
                "percent": 10,
                "stage": "Scanning",
                "stage_code": "scanning",
            },
        },
    )
    response.headers["X-Remis-Task-Id"] = task_id

    try:
        issues = await _scan_project_issues(
            project_id=project_id,
            force=force,
            sidecar_path=sidecar_path,
        )
        issue_count = len(issues)
        task_state.update_task(
            task_id,
            status="completed",
            progress={
                "percent": 100,
                "stage": "Completed",
                "stage_code": "completed",
            },
            fields={
                "result": {
                    "types": ["validation_report"],
                    "summary": (
                        f"{issue_count} format issue(s) found."
                        if issue_count
                        else "No format issues found."
                    ),
                    "metadata": {
                        "summary_code": "format_scan_completed",
                        "issue_count": issue_count,
                        "project_id": project_id,
                        "input_scope": input_scope,
                        "mutations_applied": False,
                    },
                },
            },
            append_log="Format scan completed.",
        )
        return issues
    except Exception as exc:
        task_state.update_task(
            task_id,
            status="failed",
            message="Format scan could not be completed.",
            progress={
                "stage": "Failed",
                "stage_code": "failed",
            },
            fields={
                "attention_reason": "Return to Format Scan, verify the project input scope, and try again.",
            },
            append_log="Format scan failed.",
        )
        task_state.append_task_event(
            task_id,
            str(exc),
            audience="diagnostic",
            level="error",
            event_type="scan_error",
        )
        raise


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


def _infer_target_lang_from_issue(issue_file_name: Optional[str], explicit_target_lang: Optional[str] = None) -> Optional[str]:
    if explicit_target_lang:
        return explicit_target_lang
    if not issue_file_name:
        return None

    from scripts.utils.i18n_utils import paradox_to_iso

    match = re.search(r"_l_([a-z_]+)\.yml$", issue_file_name, re.IGNORECASE)
    if not match:
        return None
    return paradox_to_iso(match.group(1))


def _read_translation_value(file_path: Path, key_to_find: str) -> Optional[str]:
    try:
        entries = dict(parse_loc_file(file_path))
    except Exception as exc:
        logger.error(f"Failed to parse updated translation file {file_path}: {exc}")
        return None

    if key_to_find in entries:
        return entries[key_to_find]

    base_key = key_to_find.split(":")[0]
    if base_key in entries:
        return entries[base_key]

    normalized_key = f"{base_key}:0"
    return entries.get(normalized_key)


def _post_validate_fixed_translation(
    game_id: str,
    key: str,
    source_str: str,
    target_str: str,
    target_lang: Optional[str] = None,
) -> List[str]:
    validator = PostProcessValidator()
    try:
        results = validator.validate_entry(
            game_id=game_id,
            key=key,
            value=target_str,
            source_value=source_str,
            target_lang=target_lang,
        )
    except Exception as exc:
        return [f"Post-validation crashed: {exc}"]

    return [result.message for result in results if result.level.value == "error"]


def _apply_fix_with_confirmation(
    project: Dict[str, Any],
    game_id: str,
    file_name: str,
    file_path: Optional[str],
    key: str,
    source_str: str,
    suggested_fix: str,
    target_lang: Optional[str] = None,
) -> tuple[bool, str, str]:
    target_path = _resolve_issue_target_path(project, file_path, file_name)
    if not target_path or not target_path.exists():
        return False, "target_not_found", "Target file not found for fix application."

    if not apply_translation_fix_to_file(target_path, key, suggested_fix):
        return False, "writeback_failure", "Failed to write suggested fix to target file."

    current_value = _read_translation_value(target_path, key)
    if current_value is None:
        return False, "readback_missing", "Fixed entry could not be read back from target file."

    if current_value != suggested_fix:
        return False, "readback_mismatch", "Read-back confirmation mismatch after writing fix."

    validation_errors = _post_validate_fixed_translation(
        game_id=game_id,
        key=key,
        source_str=source_str,
        target_str=current_value,
        target_lang=target_lang,
    )
    if validation_errors:
        return False, "post_validation_failure", "Post-write validation failed: " + " | ".join(validation_errors)

    return True, "validated_and_applied", "Applied and re-validated successfully."


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
    _validate_repair_approval(
        request.approval,
        project_id=request.project_id,
        issue_count=1,
        api_provider=provider_name,
        api_model=model_name or request.api_model,
    )
    
    project = await _require_repairable_project(request.project_id)
    handler = get_handler(provider_name, model_name=model_name)
    game_id = project.get('game_id', 'vic3')
    
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
        request.source_context_status or "found",
        request.source_context_origin or "source_file",
        request.source_context_warning,
    )
    result["reflection"] = concise_reflection
    result["report_path"] = None

    if result.get('status') == 'SUCCESS':
        target_lang = _infer_target_lang_from_issue(request.file_name)
        applied, failure_reason, apply_message = _apply_fix_with_confirmation(
            project=project,
            game_id=game_id,
            file_name=request.file_name,
            file_path=request.file_path,
            key=request.key,
            source_str=request.source_str,
            suggested_fix=result.get("suggested_fix", ""),
            target_lang=target_lang,
        )

        if applied:
            ValidationLogger.mark_attempt_result(
                project['source_path'],
                request.file_name,
                request.key,
                status="fixed",
                last_suggested_fix=result.get("suggested_fix", ""),
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
                request.source_context_status or "found",
                request.source_context_origin or "source_file",
                request.source_context_warning,
            )
            result["parity_message"] = apply_message
        else:
            ValidationLogger.mark_attempt_result(
                project['source_path'],
                request.file_name,
                request.key,
                status="failed",
                failure_reason=failure_reason,
                failure_details=apply_message,
                last_suggested_fix=result.get("suggested_fix", ""),
            )
            result["status"] = "FAILED"
            result["parity_message"] = apply_message
    
    return FixResult(**result)


async def _run_fix_batch(request: FixBatchRequest) -> FixBatchResponse:
    from scripts.core.api_handler import get_handler
    
    provider_name, model_name = _resolve_workshop_model_config(
        requested_provider=request.api_provider,
        requested_model=request.api_model,
    )
    
    project = await _require_repairable_project(request.project_id)
    handler = get_handler(provider_name, model_name=model_name)
    game_id = project.get('game_id', 'vic3')
    
    agent = ReflexionFixAgent(handler)
    first_issue = request.issues[0] if request.issues else {}
    target_lang = _infer_target_lang_from_issue(
        first_issue.get("file_name"),
        first_issue.get("target_lang"),
    )
    batch_result = await agent.fix_batch_loop(
        issues=request.issues,
        game_id=game_id,
        max_retries=max(1, min(request.max_retries or 3, 5)),
        target_lang_code=target_lang,
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
                concise_reflection = _build_concise_reflection(
                    original_issue.get("error_type") if original_issue else "",
                    original_issue.get("details") if original_issue else "",
                    original_issue.get("source_str") if original_issue else "",
                    original_issue.get("target_str") if original_issue else "",
                    res.get("suggested_fix", ""),
                    original_issue.get("source_context_status", "found") if original_issue else "found",
                    original_issue.get("source_context_origin", "source_file") if original_issue else "source_file",
                    original_issue.get("source_context_warning") if original_issue else None,
                )
                target_lang = _infer_target_lang_from_issue(
                    res["file_name"],
                    original_issue.get("target_lang") if original_issue else None,
                )
                applied, failure_reason, apply_message = _apply_fix_with_confirmation(
                    project=project,
                    game_id=game_id,
                    file_name=res["file_name"],
                    file_path=original_issue.get("file_path") if original_issue else None,
                    key=res["key"],
                    source_str=original_issue.get("source_str") if original_issue else "",
                    suggested_fix=res.get("suggested_fix", ""),
                    target_lang=target_lang,
                )
                if applied:
                    ValidationLogger.mark_attempt_result(
                        project['source_path'],
                        res["file_name"],
                        res["key"],
                        status="fixed",
                        last_suggested_fix=res.get("suggested_fix", ""),
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
                        original_issue.get("source_context_status", "found") if original_issue else "found",
                        original_issue.get("source_context_origin", "source_file") if original_issue else "source_file",
                        original_issue.get("source_context_warning") if original_issue else None,
                    )
                    res["parity_message"] = apply_message
                else:
                    ValidationLogger.mark_attempt_result(
                        project['source_path'],
                        res["file_name"],
                        res["key"],
                        status="failed",
                        failure_reason=failure_reason,
                        failure_details=apply_message,
                        last_suggested_fix=res.get("suggested_fix", ""),
                    )
                    res["status"] = "FAILED"
                    res["parity_message"] = apply_message
                    res["report_path"] = None
            else:
                res["report_path"] = None
            final_results.append(BatchResultItem(**res))
            
    attempts = [
        BatchAttemptSummary(**attempt)
        for attempt in batch_result.get("attempts", [])
        if isinstance(attempt, dict)
    ]
    return FixBatchResponse(
        results=final_results,
        attempts=attempts,
        max_retries=batch_result.get("max_retries", request.max_retries or 3),
    )


@router.post("/fix-batch", response_model=FixBatchResponse)
async def fix_batch(request: FixBatchRequest):
    """
    Initiates the Reflexion Fix Workflow for a batch of issues.
    """
    provider_name, model_name = _resolve_workshop_model_config(
        requested_provider=request.api_provider,
        requested_model=request.api_model,
    )
    _validate_repair_approval(
        request.approval,
        project_id=request.project_id,
        issue_count=len(request.issues),
        api_provider=provider_name,
        api_model=model_name or request.api_model or "",
    )
    return await _run_fix_batch(request)


def _build_fix_run_batches(issues: List[Dict[str, Any]], batch_size_limit: Optional[int]) -> List[List[Dict[str, Any]]]:
    batch_size = max(1, min(batch_size_limit or 10, 50))
    return [
        issues[index:index + batch_size]
        for index in range(0, len(issues), batch_size)
    ]


async def _run_agent_workshop_fix_task(task_id: str, request: FixRunRequest) -> None:
    started_at = time.time()
    batches = _build_fix_run_batches(request.issues, request.batch_size_limit)
    total = len(request.issues)
    total_batches = len(batches)
    concurrency = max(1, min(request.concurrency_limit or 1, 5))
    rpm = max(1, request.rpm_limit or 40)
    interval_seconds = 60 / rpm
    max_retries = max(1, min(request.max_retries or 3, 5))
    queue = asyncio.Queue()
    rate_lock = asyncio.Lock()
    stats_lock = asyncio.Lock()
    next_dispatch_at = 0.0
    completed = 0
    success_count = 0
    failed_count = 0
    all_results: List[Dict[str, Any]] = []
    all_attempts: List[Dict[str, Any]] = []
    child_task_ids: Dict[int, str] = {}

    for batch_number, batch in enumerate(batches, start=1):
        child_task_id = f"{task_id}:batch:{batch_number}"
        child_task_ids[batch_number] = child_task_id
        task_state.create_task(
            child_task_id,
            status="queued",
            log_message=f"Repair batch {batch_number}/{total_batches} queued.",
            fields={
                "kind": "agent_workshop_batch",
                "project_id": request.project_id,
                "parent_task_id": task_id,
                "title": f"Format Repair batch {batch_number}/{total_batches}",
                "source_route": f"/tasks/{task_id}",
                "created_by": request.created_by.model_dump(),
                "blocking": False,
                "workflow_context": {
                    "mode": "repair_batch",
                    "project_id": request.project_id,
                    "parent_task_id": task_id,
                    "batch_number": batch_number,
                    "issue_count": len(batch),
                },
                "checkpoint": {
                    "available": False,
                    "resume_supported": False,
                    "stage": "queued",
                    "metadata": {
                        "batch_number": batch_number,
                        "issue_count": len(batch),
                    },
                },
            },
        )
        queue.put_nowait((batch_number, batch))

    task_state.init_progress(task_id, {
        "total": total,
        "current": 0,
        "percent": 0,
        "stage": "Format Repair",
        "current_batch": 0,
        "total_batches": total_batches,
    })
    task_state.update_task(
        task_id,
        status="processing",
        append_log=f"Format Repair started repairing {total} issue(s) in {total_batches} batch(es).",
    )
    task_state.append_task_event(
        task_id,
        f"Format Repair execution settings: concurrency={concurrency}, rpm={rpm}, max_retries={max_retries}.",
        audience="diagnostic",
        level="debug",
        event_type="execution_settings",
    )

    async def wait_for_rate_limit() -> None:
        nonlocal next_dispatch_at
        async with rate_lock:
            now = time.monotonic()
            wait_seconds = max(0.0, next_dispatch_at - now)
            next_dispatch_at = max(now, next_dispatch_at) + interval_seconds
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    async def worker(worker_id: int) -> None:
        nonlocal completed, success_count, failed_count
        while True:
            try:
                batch_number, batch = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            child_task_id = child_task_ids[batch_number]
            await wait_for_rate_limit()
            task_state.update_task(
                child_task_id,
                status="processing",
                progress={
                    "current": 0,
                    "total": len(batch),
                    "percent": 0,
                    "stage": "Repairing",
                },
                append_log=f"Repair batch {batch_number}/{total_batches} started.",
            )
            task_state.update_progress(
                task_id,
                current=completed,
                total=total,
                current_batch=batch_number,
                total_batches=total_batches,
                stage="Format Repair",
                log_message=f"Worker {worker_id}: fixing batch {batch_number}/{total_batches} ({len(batch)} issue(s)).",
                event_audience="diagnostic",
                push=True,
            )

            try:
                response = await _run_fix_batch(FixBatchRequest(
                    project_id=request.project_id,
                    api_provider=request.api_provider,
                    api_model=request.api_model,
                    max_retries=max_retries,
                    issues=batch,
                ))
                batch_results = [item.model_dump() for item in response.results]
                batch_attempts = [item.model_dump() for item in response.attempts]
                batch_success = sum(1 for item in batch_results if item.get("status") == "SUCCESS")
                batch_failed = len(batch_results) - batch_success
                async with stats_lock:
                    all_results.extend(batch_results)
                    all_attempts.extend([
                        {"batch_number": batch_number, **attempt}
                        for attempt in batch_attempts
                    ])
                    completed += len(batch)
                    success_count += batch_success
                    failed_count += batch_failed
                    current_completed = completed
                    current_success = success_count
                    current_failed = failed_count
                child_status = "completed" if batch_failed == 0 else "partial_failed"
                child_summary = f"{batch_success} fixed, {batch_failed} still require review."
                task_state.update_task(
                    child_task_id,
                    status=child_status,
                    progress={
                        "current": len(batch),
                        "total": len(batch),
                        "percent": 100,
                        "stage": "Completed" if batch_failed == 0 else "Needs review",
                    },
                    summary={
                        "total": len(batch),
                        "successCount": batch_success,
                        "failedCount": batch_failed,
                    },
                    fields={
                        "result": {
                            "types": ["workshop_repairs"],
                            "summary": child_summary,
                            "metadata": {
                                "batch_number": batch_number,
                                "results": batch_results,
                            },
                        },
                        "attention_reason": child_summary if batch_failed else None,
                    },
                    append_log=(
                        f"Repair batch {batch_number}/{total_batches} completed."
                        if batch_failed == 0
                        else f"Repair batch {batch_number}/{total_batches} needs review: {batch_failed} item(s) failed."
                    ),
                )
                task_state.update_progress(
                    task_id,
                    current=current_completed,
                    total=total,
                    current_batch=batch_number,
                    total_batches=total_batches,
                    successful_batches=current_success,
                    failed_batches=current_failed,
                    stage="Format Repair",
                    log_message=f"Batch {batch_number}/{total_batches} completed: {batch_success}/{len(batch)} fixed.",
                    event_audience="diagnostic",
                    push=True,
                )
            except Exception as exc:
                logger.exception("Agent Workshop batch %s failed", batch_number)
                async with stats_lock:
                    completed += len(batch)
                    failed_count += len(batch)
                    current_completed = completed
                    current_failed = failed_count
                task_state.update_task(
                    child_task_id,
                    status="failed",
                    message="The batch could not be completed.",
                    progress={
                        "current": len(batch),
                        "total": len(batch),
                        "percent": 100,
                        "stage": "Failed",
                    },
                    fields={
                        "result": {
                            "types": ["workshop_repairs"],
                            "summary": "No repairs from this batch were applied.",
                            "metadata": {"batch_number": batch_number},
                        },
                        "attention_reason": "The batch failed before producing a complete result.",
                    },
                    append_log=f"Repair batch {batch_number}/{total_batches} failed.",
                )
                task_state.append_task_event(
                    child_task_id,
                    str(exc),
                    audience="diagnostic",
                    level="error",
                    event_type="batch_exception",
                )
                task_state.update_progress(
                    task_id,
                    current=current_completed,
                    total=total,
                    current_batch=batch_number,
                    total_batches=total_batches,
                    failed_batches=current_failed,
                    stage="Format Repair",
                    log_message=f"Batch {batch_number}/{total_batches} failed: {exc}",
                    event_audience="diagnostic",
                    push=True,
                )
            finally:
                queue.task_done()

    try:
        await asyncio.gather(*[
            worker(index)
            for index in range(1, min(concurrency, max(total_batches, 1)) + 1)
        ])
        summary = {
            "total": total,
            "completed": completed,
            "successCount": success_count,
            "failedCount": failed_count,
            "durationMs": int((time.time() - started_at) * 1000),
            "batchSize": max(1, min(request.batch_size_limit or 10, 50)),
            "totalBatches": total_batches,
            "results": all_results,
            "attempts": all_attempts,
            "maxRetries": max_retries,
        }
        report_paths = sorted({
            str(item.get("report_path"))
            for item in all_results
            if item.get("report_path")
        })
        final_status = "completed" if failed_count == 0 else "partial_failed"
        result_summary = (
            f"{success_count} issue(s) fixed."
            if failed_count == 0
            else f"{success_count} issue(s) fixed; {failed_count} still require review."
        )
        task_state.update_task(
            task_id,
            status=final_status,
            progress={
                "current": total,
                "total": total,
                "percent": 100,
                "stage": "Completed" if failed_count == 0 else "Needs review",
            },
            summary=summary,
            fields={
                "results": all_results,
                "attempts": all_attempts,
                "result": {
                    "types": ["workshop_repairs", *(["repair_reports"] if report_paths else [])],
                    "output_paths": report_paths,
                    "summary": result_summary,
                    "metadata": {
                        "total": total,
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "batch_task_ids": [
                            child_task_ids[index]
                            for index in sorted(child_task_ids)
                        ],
                    },
                },
                "attention_reason": result_summary if failed_count else None,
            },
            append_log=(
                "Format Repair run completed."
                if failed_count == 0
                else f"Format Repair run finished with {failed_count} item(s) requiring review."
            ),
        )
    except Exception as exc:
        logger.exception("Agent Workshop run failed")
        task_state.update_task(
            task_id,
            status="failed",
            message="Format Repair could not complete this repair run.",
            append_log="Format Repair run failed. Open diagnostics for technical details.",
        )
        task_state.append_task_event(
            task_id,
            str(exc),
            audience="diagnostic",
            level="error",
            event_type="run_exception",
        )


@router.post("/fix-run", response_model=FixRunResponse)
async def start_fix_run(request: FixRunRequest, background_tasks: BackgroundTasks):
    """
    Starts a backend-managed Agent Workshop run.

    The frontend should only trigger this task and subscribe to task status;
    batching, worker concurrency, RPM throttling, retries, and reflection stay here.
    """
    if not request.issues:
        raise HTTPException(status_code=400, detail="No issues supplied for Format Repair.")
    _validate_repair_approval(
        request.approval,
        project_id=request.project_id,
        issue_count=len(request.issues),
        api_provider=request.api_provider,
        api_model=request.api_model,
    )
    operation_fingerprint = _fix_run_fingerprint(request)
    existing = task_state.find_task_by_idempotency_key(request.idempotency_key)
    if existing is not None:
        if existing.get("operation_fingerprint") != operation_fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "This idempotency key is already bound to a different Format Repair scope.",
                    "retryable": False,
                    "existing_task_id": existing.get("task_id"),
                },
            )
        return FixRunResponse(
            task_id=str(existing.get("task_id")),
            status=str(existing.get("status") or "queued"),
            reused=True,
        )

    await _require_repairable_project(request.project_id)
    task_id = str(uuid.uuid4())
    try:
        task_state.create_task(
            task_id,
            status="pending",
            log_message="Format Repair run queued.",
            fields={
                "kind": "agent_workshop",
                "project_id": request.project_id,
                "title": "Format Repair",
                "source_route": "/agent-workshop",
                "created_by": request.created_by.model_dump(),
                "blocking": True,
                "blocking_reason": "Format Repair is repairing project files. Conflicting writes are blocked until it finishes.",
                "idempotency_key": request.idempotency_key,
                "operation_fingerprint": operation_fingerprint,
                "workflow_context": {
                    "mode": "repair",
                    "project_id": request.project_id,
                    "issue_count": len(request.issues),
                    "api_provider": request.api_provider,
                    "api_model": request.api_model,
                },
                "checkpoint": {
                    "available": False,
                    "resume_supported": False,
                    "stage": "queued",
                    "metadata": {
                        "issue_count": len(request.issues),
                        "api_provider": request.api_provider,
                        "api_model": request.api_model,
                    },
                },
            },
            dedupe_key=f"project_translation_write:{request.project_id}",
            reject_duplicate=True,
        )
    except task_state.DuplicateTaskError as exc:
        existing = exc.existing_task
        if existing.get("idempotency_key") == request.idempotency_key:
            if existing.get("operation_fingerprint") != operation_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "This idempotency key is already bound to a different Format Repair scope.",
                        "retryable": False,
                        "existing_task_id": existing.get("task_id"),
                    },
                ) from exc
            return FixRunResponse(
                task_id=str(existing.get("task_id")),
                status=str(existing.get("status") or "queued"),
                reused=True,
            )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_task",
                "message": "This project already has a Format Repair task in progress.",
                "existing_task_id": exc.existing_task.get("task_id"),
            },
        ) from exc
    background_tasks.add_task(_run_agent_workshop_fix_task, task_id, request)
    return FixRunResponse(task_id=task_id)
