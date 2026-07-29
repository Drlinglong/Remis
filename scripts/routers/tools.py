from fastapi import APIRouter, HTTPException
from scripts.core import workshop_formatter, deploy_manager
from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.schemas.tools import WorkshopRequest
from scripts.shared import task_state
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict, Optional
from pathlib import Path
import logging
import threading
import time
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)
validation_sidecars = ValidationSidecarService()
_DEPLOY_PREVIEW_TTL_SECONDS = 10 * 60
_deploy_previews: Dict[str, Dict[str, Any]] = {}
_deploy_preview_lock = threading.RLock()

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
    preview_id: str
    approved: bool = False
    confirm_overwrite: bool = False


class DeployPreviewRequest(BaseModel):
    project_id: Optional[str] = None
    output_folder_name: str
    game_id: str


def _deploy_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _purge_expired_deploy_previews() -> None:
    cutoff = time.monotonic() - _DEPLOY_PREVIEW_TTL_SECONDS
    with _deploy_preview_lock:
        expired = [
            preview_id
            for preview_id, preview in _deploy_previews.items()
            if preview["created_monotonic"] < cutoff
        ]
        for preview_id in expired:
            _deploy_previews.pop(preview_id, None)


def _validation_error_count(project: Optional[Dict[str, Any]]) -> int:
    if not project or not project.get("source_path"):
        return 0
    status = validation_sidecars.load_status(project["source_path"])
    if not status:
        return 0
    return sum(
        1
        for issue in status.get("issues", [])
        if str(issue.get("severity") or "").lower() == "error"
    )


@router.post("/api/tools/deploy_preview")
async def preview_deploy(payload: DeployPreviewRequest):
    from scripts.shared.services import project_manager

    project = None
    if payload.project_id:
        project = await project_manager.get_project(payload.project_id)
        if not project:
            raise _deploy_error(404, "project_not_found", "Project not found")
        if project.get("status") != "active":
            raise _deploy_error(
                409,
                "project_not_active",
                "Restore this project before deploying it.",
            )
        if project.get("game_id") and project["game_id"] != payload.game_id:
            raise _deploy_error(
                409,
                "project_game_mismatch",
                "The deployment game does not match the selected project.",
            )

    try:
        source_path = deploy_manager.mod_deployer._resolve_output_source(
            payload.output_folder_name
        )
        _, target_path = deploy_manager.mod_deployer.resolve_deploy_target(
            payload.output_folder_name,
            payload.game_id,
            None,
        )
    except ValueError as exc:
        raise _deploy_error(
            400,
            "deploy_preview_unavailable",
            "Deployment preview could not be created from the selected output.",
        ) from exc

    validation_error_count = _validation_error_count(project)
    preview_id = str(uuid.uuid4())
    preview = {
        "preview_id": preview_id,
        "created_monotonic": time.monotonic(),
        "project_id": payload.project_id,
        "output_folder_name": payload.output_folder_name,
        "game_id": payload.game_id,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "target_exists": target_path.exists(),
        "validation_error_count": validation_error_count,
        "project_source_path": (
            str(project.get("source_path"))
            if project and project.get("source_path")
            else None
        ),
    }
    _purge_expired_deploy_previews()
    with _deploy_preview_lock:
        _deploy_previews[preview_id] = preview

    return {
        key: value
        for key, value in preview.items()
        if key not in {"created_monotonic", "project_source_path"}
    } | {
        "requires_approval": True,
        "requires_overwrite_confirmation": preview["target_exists"],
        "allowed_actions": (
            ["approve_deploy"]
            if validation_error_count == 0
            else ["return_to_validation"]
        ),
    }

@router.post("/api/tools/deploy_mod")
async def deploy_mod(payload: DeployRequest):
    from scripts.shared.services import project_manager

    if not payload.approved:
        raise _deploy_error(
            409,
            "approval_required",
            "Explicit approval is required before deployment.",
        )
    if payload.clean_fake_loc or payload.workshop_path:
        raise _deploy_error(
            409,
            "cleanup_requires_separate_confirmation",
            "Fake-localization cleanup requires its own preview and confirmation.",
        )
    _purge_expired_deploy_previews()
    with _deploy_preview_lock:
        preview = _deploy_previews.get(payload.preview_id)
    if not preview:
        raise _deploy_error(
            409,
            "deploy_preview_required",
            "Create a fresh deployment preview before deploying.",
        )
    requested_contract = {
        "project_id": payload.project_id,
        "output_folder_name": payload.output_folder_name,
        "game_id": payload.game_id,
    }
    if any(preview[key] != value for key, value in requested_contract.items()):
        raise _deploy_error(
            409,
            "deploy_preview_mismatch",
            "The deployment request no longer matches its preview.",
        )
    project = None
    if payload.project_id:
        project = await project_manager.get_project(payload.project_id)
        if not project or project.get("status") != "active":
            raise _deploy_error(
                409,
                "project_not_active",
                "Restore this project and create a fresh preview before deploying.",
            )
    try:
        source_path = deploy_manager.mod_deployer._resolve_output_source(
            payload.output_folder_name
        )
        _, target_path = deploy_manager.mod_deployer.resolve_deploy_target(
            payload.output_folder_name,
            payload.game_id,
            payload.target_deploy_path,
        )
    except ValueError as exc:
        raise _deploy_error(
            409,
            "deploy_preview_stale",
            "The deployment source or target changed. Create a fresh preview.",
        ) from exc
    if (
        str(source_path) != preview["source_path"]
        or str(target_path) != preview["target_path"]
        or target_path.exists() != preview["target_exists"]
    ):
        raise _deploy_error(
            409,
            "deploy_preview_stale",
            "The deployment source or target changed. Create a fresh preview.",
        )
    current_validation_error_count = _validation_error_count(
        {"source_path": preview["project_source_path"]}
        if preview.get("project_source_path")
        else None
    )
    if (
        preview["validation_error_count"]
        or current_validation_error_count
    ):
        raise _deploy_error(
            409,
            "validation_errors_block_deploy",
            "Resolve validation errors before deploying.",
        )
    if target_path.exists() and not payload.confirm_overwrite:
        raise _deploy_error(
            409,
            "overwrite_confirmation_required",
            "The target already exists. Confirm replacement before deploying.",
        )
    with _deploy_preview_lock:
        consumed_preview = _deploy_previews.pop(payload.preview_id, None)
    if consumed_preview is None:
        raise _deploy_error(
            409,
            "deploy_preview_consumed",
            "This deployment preview was already used. Create a fresh preview.",
        )

    task_id = str(uuid.uuid4())
    try:
        task_state.create_task(
            task_id,
            status="running",
            log_message="Approved deployment started.",
            fields={
                "kind": "deployment",
                "project_id": payload.project_id,
                "project_context": {
                    "name": (project or {}).get("name") or payload.output_folder_name,
                    "game_id": payload.game_id,
                },
                "title": f"Deploy {payload.output_folder_name}",
                "source_route": "/project-management",
                "created_by": {"type": "user"},
                "blocking": True,
                "blocking_reason": (
                    "Remis is deploying project output. Conflicting project writes "
                    "are blocked until deployment finishes."
                ),
                "result": {
                    "types": ["deployment_preview"],
                    "summary": "Deployment approved from a fresh preview.",
                    "metadata": {
                        "preview_id": payload.preview_id,
                        "source_path": str(source_path),
                        "target_path": str(target_path),
                        "target_existed": preview["target_exists"],
                    },
                },
            },
            dedupe_key=(
                f"project_translation_write:{payload.project_id}"
                if payload.project_id
                else f"deployment:{target_path}"
            ),
            reject_duplicate=True,
        )
    except task_state.DuplicateTaskError as exc:
        raise _deploy_error(
            409,
            "duplicate_task",
            f"Conflicting task {exc.existing_task.get('task_id')} is already active.",
        ) from exc

    try:
        result = await run_in_threadpool(
            deploy_manager.mod_deployer.deploy_mod,
            output_folder_name=payload.output_folder_name,
            game_id=payload.game_id,
            target_deploy_path=payload.target_deploy_path,
            workshop_path=None,
            clean_fake_loc=False,
            source_language=payload.source_language,
        )
    except Exception as exc:
        logger.exception("Deployment execution failed")
        task_state.update_task(
            task_id,
            status="failed",
            message="Deployment failed. Check Remis logs for details.",
            append_log="Deployment failed. Check Remis logs for details.",
            fields={
                "attention_reason": "Deployment failed. Check Remis logs for details."
            },
        )
        raise _deploy_error(
            500,
            "deployment_failed",
            "Deployment failed. Check Remis logs for details.",
        ) from exc
    if result["status"] == "error":
        task_state.update_task(
            task_id,
            status="failed",
            message="Deployment failed. Check Remis logs for details.",
            append_log="Deployment failed. Check Remis logs for details.",
            fields={"attention_reason": "Deployment failed. Check Remis logs for details."},
        )
        raise _deploy_error(
            500,
            "deployment_failed",
            "Deployment failed. Check Remis logs for details.",
        )
    output_paths = [
        str(path)
        for path in (
            result.get("output_paths")
            or [result.get("target_path") or target_path]
        )
    ]
    task_state.update_task(
        task_id,
        status="completed",
        append_log="Deployment completed.",
        progress={"current": 1, "total": 1, "percent": 100, "stage": "Completed"},
        fields={
            "result": {
                "types": ["deployment"],
                "output_paths": output_paths,
                "summary": result.get("message") or "Deployment completed.",
                "metadata": {
                    "preview_id": payload.preview_id,
                    "source_path": str(source_path),
                    "target_path": str(result.get("target_path") or target_path),
                    "target_replaced": preview["target_exists"],
                    "deploy_status": result.get("status"),
                },
            },
        },
    )
    if payload.project_id:
        try:
            await project_manager.log_history_event(
                payload.project_id,
                "deployment_completed",
                "Approved deployment completed.",
                metadata={
                    "task_id": task_id,
                    "preview_id": payload.preview_id,
                    "target_path": str(result.get("target_path") or target_path),
                    "target_replaced": preview["target_exists"],
                },
            )
        except Exception:
            logger.exception(
                "Deployment completed but project history could not be updated"
            )
    return {**result, "task_id": task_id, "preview_id": payload.preview_id}

class CleanFakeLocRequest(BaseModel):
    workshop_path: str
    source_language: str = "english"

@router.post("/api/tools/clean_fake_loc")
def clean_fake_loc(payload: CleanFakeLocRequest):
    result = deploy_manager.mod_deployer.clean_fake_localization(
        original_mod_path=payload.workshop_path,
        source_lang=payload.source_language
    )
    if result.get("status") == "error":
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
