import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from scripts.core.neologism_manager import neologism_manager
from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.repositories.context_analysis_batch_repository import (
    ContextAnalysisBatchRepository,
)
from scripts.core.services.context_workflow_service import ContextWorkflowService
from scripts.core.services.context_analysis_preview_service import (
    ContextAnalysisPreviewService,
)
from scripts.shared.services import project_manager, glossary_manager
from scripts.shared import task_state
from scripts.shared.task_state import DuplicateTaskError
from scripts.schemas.neologism import (
    ApproveNeologismRequest,
    ProjectGlossaryBindingRequest,
    RestoreNeologismRequest,
    UpdateNeologismRequest,
    MineNeologismsRequest,
)
from scripts.schemas.common import LanguageCode
from scripts.app_settings import API_PROVIDERS, GAME_PROFILES_BY_ID, PROJECTS_DB_PATH

logger = logging.getLogger(__name__)

router = APIRouter()
context_repository = ContextRepository(PROJECTS_DB_PATH)
context_analysis_batch_repository = ContextAnalysisBatchRepository(PROJECTS_DB_PATH)
context_service = ContextService(context_repository)
context_analysis_preview_service = ContextAnalysisPreviewService(
    context_repository,
    context_analysis_batch_repository,
)
context_workflow_service = ContextWorkflowService(
    context_repository,
    candidate_store=neologism_manager,
    analysis_batch_repository=context_analysis_batch_repository,
)
SUPPORTED_MINING_SUFFIXES = {".txt", ".yml", ".yaml", ".csv", ".json"}


def _run_context_workflow_background(*args, **kwargs):
    """Keep an already-persisted workflow failure out of the ASGI response path."""

    try:
        return context_workflow_service.run(*args, **kwargs)
    except Exception as exc:
        logger.error(
            "Context archive analysis ended in a persisted failed state: %s",
            exc,
            exc_info=True,
        )
        return None


def _context_release_presentation(release):
    payload = release.model_dump()
    metadata = payload["metadata"]
    config = metadata.get("analysis_config") or {}
    metadata["prompt_example"] = ContextWorkflowService.prompt_example(
        str(config.get("description_language") or "en")
    )
    return payload


def _normalize_language_code(value: str) -> str:
    try:
        return LanguageCode.from_str(value).value
    except ValueError:
        return (value or "").strip().replace("_", "-").casefold()


def _reject_source_language_target(source_language: str, target_language: str) -> None:
    if _normalize_language_code(source_language) == _normalize_language_code(target_language):
        raise HTTPException(
            status_code=400,
            detail="Target language must be different from the project source language.",
        )


def _is_supported_mining_path(path: Path) -> bool:
    name = path.name.casefold()
    if name == ".remis_project.json" or name.startswith(".remis_checkpoint"):
        return False
    return path.suffix.lower() in SUPPORTED_MINING_SUFFIXES

def _normalize_term(term: str) -> str:
    return " ".join((term or "").casefold().split())


def _mining_task_identity(payload: MineNeologismsRequest, project: dict) -> tuple[str, str]:
    project_name = project.get("name") or payload.project_id
    if payload.analysis_scope == "narrative_context":
        return "context_archive_analysis", f"Build project archive for {project_name}"
    return "neologism_mining", f"Mine neologisms for {project_name}"

async def _build_glossary_duplicate_index(
    game_id: str,
    source_lang: str,
    project_id: str,
    project_name: Optional[str],
) -> dict:
    all_glossaries = await glossary_manager.get_all_glossaries()
    relevant = [glossary for glossary in all_glossaries if glossary.get("game_id") == game_id]
    project_glossary = await glossary_manager.get_project_glossary(game_id, project_id, project_name)
    if project_glossary and all(
        glossary.get("glossary_id") != project_glossary.get("glossary_id")
        for glossary in relevant
    ):
        relevant.append(project_glossary)
    glossary_ids = [glossary["glossary_id"] for glossary in relevant if glossary.get("glossary_id")]
    if not glossary_ids:
        return {}

    glossary_by_id = {glossary["glossary_id"]: glossary for glossary in relevant}
    entries = await glossary_manager.get_entries_for_glossary_ids(glossary_ids)
    duplicate_index = {}
    for entry in entries:
        translations = entry.get("translations") or {}
        source_term = translations.get(source_lang) or translations.get("en")
        if not source_term:
            continue
        key = _normalize_term(source_term)
        glossary = glossary_by_id.get(entry.get("glossary_id"), {})
        duplicate_index.setdefault(key, []).append({
            "entry_id": entry.get("entry_id"),
            "glossary_id": entry.get("glossary_id"),
            "glossary_name": glossary.get("name"),
            "scope": (
                "project"
                if project_glossary and entry.get("glossary_id") == project_glossary.get("glossary_id")
                else ("main" if glossary.get("is_main") else "game")
            ),
            "source_term": source_term,
            "translations": translations,
        })
    return duplicate_index


def _normalize_path_within_root(raw_path: str, source_root: Path) -> str:
    try:
        root_text = os.path.realpath(str(source_root))
        candidate_text = os.path.expanduser(raw_path)
        if not os.path.isabs(candidate_text):
            candidate_text = os.path.join(root_text, candidate_text)
        normalized = os.path.realpath(candidate_text)
        root_prefix = root_text.rstrip("\\/") + os.sep
        if normalized != root_text and not normalized.startswith(root_prefix):
            raise HTTPException(
                status_code=400,
                detail="Selected files must stay inside the project source directory",
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Selected file path is invalid",
        ) from exc
    return normalized


def _resolve_tracked_path_within_root(raw_path: str, source_root: Path) -> Path:
    resolved = Path(_normalize_path_within_root(raw_path, source_root))
    if not resolved.is_file():
        raise HTTPException(status_code=400, detail="Selected file does not exist")
    if not _is_supported_mining_path(resolved):
        raise HTTPException(status_code=400, detail="Unsupported mining file type")
    return resolved


async def _resolve_project_mining_files(project: dict, requested_paths: Optional[list[str]]) -> list[str]:
    try:
        source_root = Path(project["source_path"]).resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Project source directory does not exist") from exc

    tracked_files = await project_manager.get_project_files(project["project_id"])
    allowed: dict[str, str] = {}
    for tracked in tracked_files:
        raw_path = tracked.get("file_path") or tracked.get("path")
        if not raw_path:
            continue
        try:
            resolved = _resolve_tracked_path_within_root(raw_path, source_root)
        except HTTPException:
            continue
        allowed[os.path.normcase(str(resolved))] = str(resolved)

    if requested_paths:
        selected: list[str] = []
        for raw_path in requested_paths:
            normalized = _normalize_path_within_root(raw_path, source_root)
            normalized_key = os.path.normcase(normalized)
            if normalized_key not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Selected file is not indexed for this project",
                )
            selected.append(allowed[normalized_key])
        files = list(dict.fromkeys(selected))
    else:
        files = sorted(allowed.values())

    if not files:
        raise HTTPException(status_code=400, detail="No supported indexed project files are available for mining")
    return files


@router.get("/api/neologisms/mining-files/{project_id}")
async def list_mining_files(project_id: str):
    """List the exact source files eligible for neologism mining."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    source_root = Path(project["source_path"]).resolve(strict=True)
    files = await _resolve_project_mining_files(project, None)
    return [
        {
            "file_path": file_path,
            "relative_path": str(Path(file_path).relative_to(source_root)),
        }
        for file_path in files
    ]

@router.get("/api/neologisms")
async def list_neologisms(project_id: Optional[str] = None, view: str = "pending"):
    """List neologism candidates, optionally filtered by project."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id query parameter is required")
    if not await project_manager.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if view not in {"pending", "processed", "all"}:
        raise HTTPException(status_code=400, detail="view must be pending, processed, or all")
    return neologism_manager.get_candidates(project_id, view=view)

@router.post("/api/neologisms/{candidate_id}/approve")
async def approve_neologism(candidate_id: str, payload: ApproveNeologismRequest):
    """Approve a neologism candidate and add to glossary."""
    project = await project_manager.get_project(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project_glossary = None
    if payload.resolution != "duplicate":
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
        project_glossary["glossary_id"] if project_glossary else None,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        resolution=payload.resolution,
    ):
        logger.info(f"Approved neologism candidate {candidate_id} for project {payload.project_id}")
        return {"status": "success", "glossary": project_glossary}
    raise HTTPException(status_code=404, detail="Candidate not found or failed to approve")

@router.post("/api/neologisms/{candidate_id}/reject")
async def reject_neologism(candidate_id: str, payload: dict):
    """Reject a neologism candidate."""
    project_id = payload.get('project_id')
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not await project_manager.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    previous_status = neologism_manager.reject_candidate(project_id, candidate_id)
    if previous_status is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if previous_status not in {"pending", "ignored"}:
        raise HTTPException(
            status_code=409,
            detail=f"Candidate is already {previous_status}; restore it before rejecting",
        )
    if previous_status in {"pending", "ignored"}:
        logger.info(f"Rejected neologism candidate {candidate_id} for project {project_id}")
        return {"status": "success", "previous_status": previous_status}

@router.patch("/api/neologisms/{candidate_id}")
async def update_neologism_suggestion(candidate_id: str, payload: UpdateNeologismRequest):
    """Update a candidate's suggestion."""
    if not await project_manager.get_project(payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if neologism_manager.update_candidate_suggestion(payload.project_id, candidate_id, payload.suggestion):
        logger.info(f"Updated neologism candidate {candidate_id} suggestion for project {payload.project_id}")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Candidate not found")

@router.post("/api/neologisms/{candidate_id}/restore")
async def restore_neologism(candidate_id: str, payload: RestoreNeologismRequest):
    """Return a processed candidate to the pending docket without mutating glossary entries."""
    if not await project_manager.get_project(payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    previous_status = neologism_manager.restore_candidate(payload.project_id, candidate_id)
    if previous_status is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    logger.info(
        "Restored neologism candidate %s for project %s from %s",
        candidate_id,
        payload.project_id,
        previous_status,
    )
    return {
        "status": "success",
        "previous_status": previous_status,
        "glossary_entry_preserved": previous_status in {"approved", "new_meaning"},
    }

@router.post("/api/neologisms/mine")
async def trigger_mining(payload: MineNeologismsRequest, background_tasks: BackgroundTasks):
    """Trigger neologism mining for a project."""
    project = await project_manager.get_project(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _reject_source_language_target(
        project.get("source_language") or "en",
        payload.target_lang,
    )
    if payload.api_provider not in API_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown API provider: {payload.api_provider}")
    files = await _resolve_project_mining_files(project, payload.file_paths)
    
    logger.info(f"Triggering neologism mining for project {payload.project_id} with {len(files)} files.")
    game_profile = GAME_PROFILES_BY_ID.get(project.get("game_id") or "")
    game_name = (game_profile or {}).get("name", "Paradox Game")
    project_glossary = await glossary_manager.get_or_create_project_glossary(
        project["game_id"],
        payload.project_id,
        project.get("name"),
    )
    if not project_glossary or not project_glossary.get("glossary_id"):
        raise HTTPException(status_code=500, detail="Failed to prepare project glossary")

    duplicate_index = await _build_glossary_duplicate_index(
        project["game_id"],
        project.get("source_language") or "en",
        payload.project_id,
        project.get("name"),
    )

    task_id = str(uuid.uuid4())
    task_kind, task_title = _mining_task_identity(payload, project)
    if not context_workflow_service.reserve(
        payload.project_id,
        task_id,
        payload.analysis_scope,
    ):
        raise HTTPException(status_code=409, detail="A neologism mining run is already active for this project")
    try:
        task_state.create_task(
            task_id,
            status="queued",
            log_message="Neologism mining queued.",
            fields={
                "kind": task_kind,
                "project_id": payload.project_id,
                "title": task_title,
                "source_route": "/neologism-review",
                "created_by": {"type": "user"},
                "blocking": True,
                "workflow_context": {"analysis_scope": payload.analysis_scope},
            },
            dedupe_key=f"neologism_mining:{payload.project_id}",
            reject_duplicate=True,
        )
    except DuplicateTaskError as exc:
        context_workflow_service.release_reservation(payload.project_id, task_id)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_task",
                "message": "A neologism mining run is already active for this project",
                "existing_task_id": exc.existing_task.get("task_id"),
            },
        ) from exc
    except Exception:
        context_workflow_service.release_reservation(payload.project_id, task_id)
        raise
    task_state.init_progress(task_id, {
        "total": len(files),
        "current": 0,
        "percent": 0,
        "stage": "Queued",
        "current_file": "",
    })
    task_state.update_task(
        task_id,
        status="queued",
        summary={
            "project_id": payload.project_id,
            "project_glossary_id": project_glossary["glossary_id"],
            "project_glossary_name": project_glossary.get("name"),
            "new_terms": 0,
            "duplicate_terms": 0,
            "analysis_scope": payload.analysis_scope,
            "description_language": payload.effective_description_language,
        },
        fields={"kind": task_kind, "stage_code": "queued"},
        push=True,
    )
    background_tasks.add_task(
        _run_context_workflow_background,
        payload.project_id,
        files,
        project["source_path"],
        payload.api_provider,
        source_lang=project.get("source_language") or "en",
        target_lang=payload.target_lang,
        game_name=game_name,
        task_id=task_id,
        duplicate_index=duplicate_index,
        model_name=payload.model_name,
        review_language=payload.effective_description_language,
        description_language=payload.effective_description_language,
        analysis_scope=payload.analysis_scope,
        upstream_version=payload.upstream_version,
        concurrency_limit=payload.concurrency_limit,
    )
    return {
        "task_id": task_id,
        "status": "started",
        "total_files": len(files),
        "message": "Mining started in background",
    }

@router.get("/api/neologisms/project-glossary/{project_id}")
async def get_project_neologism_glossary(project_id: str):
    """Return the dedicated project glossary if it already exists."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    glossary = await glossary_manager.get_project_glossary(
        project["game_id"],
        project_id,
        project.get("name"),
    )
    return glossary or {
        "glossary_id": None,
        "game_id": project["game_id"],
        "name": glossary_manager.get_project_glossary_name(project_id, project.get("name")),
        "description": f"Auto-mined project glossary for {project.get('name') or project_id}",
        "is_main": False,
        "pending_creation": True,
    }

@router.post("/api/neologisms/project-glossary/{project_id}")
async def ensure_project_neologism_glossary(project_id: str):
    """Create the dedicated project glossary if needed and bind it to this project."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    glossary = await glossary_manager.get_or_create_project_glossary(
        project["game_id"],
        project_id,
        project.get("name"),
    )
    if not glossary or not glossary.get("glossary_id"):
        raise HTTPException(status_code=500, detail="Failed to prepare project glossary")
    return glossary

@router.put("/api/neologisms/project-glossary/{project_id}")
async def bind_project_neologism_glossary(project_id: str, payload: ProjectGlossaryBindingRequest):
    """Bind this project to an existing glossary."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    target = await glossary_manager.get_glossary_by_id(payload.glossary_id)
    if not target:
        raise HTTPException(status_code=404, detail="Glossary not found")

    glossary = await glossary_manager.bind_project_glossary(
        project["game_id"],
        project_id,
        project.get("name"),
        payload.glossary_id,
    )
    if not glossary:
        raise HTTPException(status_code=500, detail="Failed to bind project glossary")
    return glossary

@router.delete("/api/neologisms/project-glossary/{project_id}")
async def unbind_project_neologism_glossary(project_id: str):
    """Unbind the current project glossary without deleting the glossary."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await glossary_manager.unbind_project_glossary(project["game_id"], project_id):
        raise HTTPException(status_code=500, detail="Failed to unbind project glossary")
    return {"status": "success"}

@router.get("/api/neologisms/status/{project_id}")
def get_mining_status(project_id: str):
    """Return the latest neologism mining status for a project."""
    return context_workflow_service.get_status(project_id)


@router.get("/api/context/releases/{project_id}/latest")
def get_latest_context_release(project_id: str, optional: bool = False):
    release = context_repository.list_releases(project_id)
    if not release:
        if optional:
            return {"release": None}
        raise HTTPException(status_code=404, detail="No context release exists for this project")
    return _context_release_presentation(release[0])


@router.get("/api/context/projects/{project_id}/analysis-preview")
def get_context_analysis_preview(project_id: str, optional: bool = False):
    preview = context_analysis_preview_service.latest(project_id)
    if preview is None:
        if optional:
            return {"preview": None}
        raise HTTPException(
            status_code=404,
            detail="No persisted context analysis preview exists for this project",
        )
    return preview.model_dump()


@router.get("/api/context/releases/{release_id}/effective")
def get_effective_context(release_id: str):
    effective = context_service.effective_context(release_id)
    if effective is None:
        raise HTTPException(status_code=404, detail="Context release not found")
    return effective.model_dump()


@router.get("/api/context/releases/{release_id}/traceability")
def get_context_traceability(release_id: str):
    if context_repository.get_release(release_id) is None:
        raise HTTPException(status_code=404, detail="Context release not found")
    return context_service.traceability(release_id)
