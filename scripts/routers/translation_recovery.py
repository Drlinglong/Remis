"""Task Center recovery actions for persisted translation runs."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from scripts.core.feature_policy import checkpoint_resume_enabled
from scripts.core.services.translation_recovery_service import TranslationRecoveryService
from scripts.routers.translation import start_translation_project
from scripts.schemas.translation import (
    InitialTranslationRequest,
    ResumeTranslationTaskRequest,
    TranslationTaskResponse,
)
from scripts.shared import task_state


router = APIRouter()


@router.get("/api/projects/{project_id}/translation-recovery")
async def get_translation_recovery(project_id: str):
    repository = task_state.get_repository()
    if repository is None:
        return {"task_id": None, "status": "none", "checkpoint": {}, "allowed_actions": []}
    return TranslationRecoveryService(repository).inspect(project_id)


@router.delete("/api/projects/{project_id}/translation-checkpoint")
async def clear_translation_checkpoint(project_id: str):
    repository = task_state.get_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Task persistence is unavailable")
    try:
        return TranslationRecoveryService(repository).clear_project_checkpoint(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/tasks/{task_id}/resume",
    response_model=TranslationTaskResponse,
    response_model_exclude_none=True,
)
async def resume_translation_task(
    task_id: str,
    payload: ResumeTranslationTaskRequest,
    background_tasks: BackgroundTasks,
):
    if not checkpoint_resume_enabled():
        raise HTTPException(status_code=409, detail="Checkpoint resume is disabled")
    if payload.idempotency_key:
        existing = task_state.find_task_by_idempotency_key(payload.idempotency_key)
        if existing is not None:
            if existing.get("parent_task_id") != task_id:
                raise HTTPException(status_code=409, detail="Idempotency key belongs to another task")
            return {
                "task_id": existing["task_id"],
                "status": existing["status"],
                "message": "Existing recovery task returned for this idempotency key.",
            }
    repository = task_state.get_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Task persistence is unavailable")
    try:
        original = TranslationRecoveryService(repository).require_resumable(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    recovery = original["recovery"]
    configuration = dict(recovery["configuration_snapshot"])
    configuration.update(
        idempotency_key=payload.idempotency_key,
        resume_from_task_id=task_id,
        use_resume=True,
    )
    request = InitialTranslationRequest.model_validate(configuration)
    return await start_translation_project(request, background_tasks)


@router.post(
    "/api/tasks/{task_id}/start-over",
    response_model=TranslationTaskResponse,
    response_model_exclude_none=True,
)
async def start_translation_over(task_id: str, background_tasks: BackgroundTasks):
    repository = task_state.get_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Task persistence is unavailable")
    original = repository.get_task(task_id)
    if original is None or not original.get("recovery"):
        raise HTTPException(status_code=404, detail="Recovery task not found")
    try:
        service = TranslationRecoveryService(repository)
        original = service.require_start_over(task_id)
        configuration = dict(original["recovery"]["configuration_snapshot"])
        configuration.update(resume_from_task_id=None, use_resume=False)
        request = InitialTranslationRequest.model_validate(configuration)
        replacement = await start_translation_project(request, background_tasks)
        service.finalize_start_over(
            task_id,
            replacement_task_id=replacement["task_id"],
        )
        return replacement
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
