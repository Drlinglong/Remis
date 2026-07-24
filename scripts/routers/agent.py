from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException

from scripts.app_settings import (
    API_PROVIDERS,
    DEST_DIR,
    GAME_PROFILES,
    LANGUAGES,
    PROJECT_INFO,
    get_api_key,
)
from scripts.core import deploy_manager
from scripts.core.agent_service import AGENT_API_VERSION, agent_registry
from scripts.core.copilot.workflow import create_translation_plan
from scripts.core.copilot.workflow import inspect_mod_folder
from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.routers.agent_workshop import FixRunRequest, start_fix_run
from scripts.routers.translation import start_translation_project
from scripts.schemas.agent import (
    AgentExportRequest,
    AgentJobPlanRequest,
    AgentJobResponse,
    AgentJobStartRequest,
    AgentPlanResponse,
    AgentProjectCreateRequest,
    AgentProjectInspectRequest,
    AgentProjectPlanRequest,
    AgentProjectPlanResponse,
    AgentProjectSummary,
    AgentRepairRequest,
    AgentValidationSummary,
)
from scripts.schemas.translation import InitialTranslationRequest
from scripts.shared import task_state
from scripts.shared.services import project_manager
from scripts.utils.system_utils import sanitize_for_json


router = APIRouter(prefix="/api/agent", tags=["Agent API"])
validation_sidecars = ValidationSidecarService()
logger = logging.getLogger(__name__)

LOCAL_PROVIDER_IDS = {
    "ollama",
    "lm_studio",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "hunyuan",
}
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
LATEST_RELEASE_URL = "https://api.github.com/repos/Drlinglong/Remis/releases/latest"


def _error(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
    )


def _public_provider(provider_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    env_name = config.get("api_key_env")
    credential_status = "not_required"
    if env_name:
        credential_status = (
            "configured" if get_api_key(provider_id, env_name) else "missing"
        )
    return {
        "id": provider_id,
        "name": config.get("name") or provider_id,
        "default_model": config.get("default_model"),
        "local": provider_id in LOCAL_PROVIDER_IDS,
        "requires_api_key": bool(config.get("api_key_env")),
        "credential_status": credential_status,
    }


def _version_key(value: str) -> tuple[int, ...]:
    numeric = str(value or "").strip().lower().lstrip("v").split("-", 1)[0]
    try:
        return tuple(int(part) for part in numeric.split("."))
    except ValueError:
        return ()


def _provider_setup(provider_id: Optional[str] = None) -> Dict[str, Any]:
    configured_cloud = []
    for item_id, config in API_PROVIDERS.items():
        env_name = config.get("api_key_env")
        if env_name and get_api_key(item_id, env_name):
            configured_cloud.append(item_id)

    selected = API_PROVIDERS.get(provider_id) if provider_id else None
    selected_requires_key = bool(selected and selected.get("api_key_env"))
    selected_ready = None
    if selected is not None:
        selected_ready = (
            not selected_requires_key
            or provider_id in configured_cloud
        )

    return {
        "api_key_configured": bool(configured_cloud),
        "configured_cloud_providers": configured_cloud,
        "selected_provider": provider_id,
        "selected_provider_ready": selected_ready,
        "keyless_local_providers_available": sorted(LOCAL_PROVIDER_IDS),
        "setup_required": selected_ready is False or (
            selected is None and not configured_cloud
        ),
        "settings_location": "Remis Settings > API Settings",
        "explanation_available": True,
        "explanation": (
            "An API key is a secret credential issued by a model provider. "
            "It lets Remis authenticate model requests and may be tied to billing. "
            "Store it in Remis Settings; never paste it into an Agent chat. "
            "A deliberately selected local provider can be keyless."
        ),
    }


def _release_check() -> Dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    current = str(PROJECT_INFO["version"])
    try:
        response = requests.get(
            LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"Remis-Agent-API/{current}",
            },
            timeout=5,
        )
        response.raise_for_status()
        release = response.json()
        latest = str(release.get("tag_name") or "").strip()
        if not latest:
            raise ValueError("GitHub release response did not include tag_name")
        return {
            "checked": True,
            "checked_at": checked_at,
            "current_version": current,
            "latest_version": latest,
            "update_available": _version_key(latest) > _version_key(current),
            "release_url": release.get("html_url"),
            "published_at": release.get("published_at"),
            "prerelease": bool(release.get("prerelease")),
            "source": LATEST_RELEASE_URL,
        }
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Agent release check failed: %s", exc)
        return {
            "checked": False,
            "checked_at": checked_at,
            "current_version": current,
            "latest_version": None,
            "update_available": None,
            "release_url": "https://github.com/Drlinglong/Remis/releases/latest",
            "error": "The release check is currently unavailable.",
            "source": LATEST_RELEASE_URL,
        }


def _public_game(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "source_localization_folder": profile.get("source_localization_folder"),
    }


def _validate_agent_import_path(folder_path: str) -> Dict[str, Any]:
    try:
        inspection = inspect_mod_folder(folder_path)
    except ValueError as exc:
        reason = str(exc)
        if reason in {
            "Mod folder is outside the allowed local import roots",
            "Mod folder is inside a protected system root",
            "Select a specific mod folder",
        }:
            raise _error(
                403,
                "import_path_not_allowed",
                (
                    "Agent imports are restricted to the user profile, standard "
                    "Steam Workshop roots, or REMIS_AGENT_IMPORT_ROOTS"
                ),
            ) from exc
        if reason == "Mod folder does not exist":
            raise _error(
                404,
                "import_path_not_found",
                "Import path not found",
            ) from exc
        raise _error(
            400,
            "invalid_mod_folder",
            "The selected folder is not a supported Paradox mod",
        ) from exc
    if (
        inspection.get("localization_file_count", 0) == 0
        and not inspection.get("metadata_files")
    ):
        raise _error(
            400,
            "invalid_mod_folder",
            "No localization files or supported mod metadata were found",
        )
    return inspection


def _classify_issues(
    issues: Iterable[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], AgentValidationSummary]:
    public_items = []
    errors = 0
    warnings = 0
    human_review = 0
    for raw in issues:
        severity = str(raw.get("severity") or "").strip().lower()
        error_code = str(raw.get("error_code") or raw.get("error_type") or "unknown")
        if severity in {"critical", "error", "fatal"}:
            category = "error"
            errors += 1
        elif severity in {"warning", "warn", "info"}:
            category = "warning"
            warnings += 1
        else:
            category = "human_review"
            human_review += 1
        public_items.append(
            {
                "category": category,
                "code": error_code,
                "file_id": raw.get("file_id"),
                "file_name": raw.get("file_name"),
                "key": raw.get("key"),
                "line_number": raw.get("line_number"),
                "details": raw.get("details") or raw.get("message"),
                "status": raw.get("status", "detected"),
            }
        )
    summary = AgentValidationSummary(
        errors=errors,
        warnings=warnings,
        human_review_items=human_review,
        total=len(public_items),
        available=True,
    )
    return public_items, summary


async def _validation_payload(
    project_id: Optional[str], *, include_items: bool = False
) -> Dict[str, Any]:
    empty = AgentValidationSummary()
    if not project_id:
        return {"summary": empty, "items": []}
    project = await project_manager.get_project(project_id)
    if not project:
        return {"summary": empty, "items": []}
    status = validation_sidecars.load_status(project["source_path"])
    if not status:
        return {"summary": empty, "items": []}
    files = await project_manager.get_project_files(project_id)
    issues = validation_sidecars.attach_project_file_ids(status["issues"], files)
    public_items, summary = _classify_issues(issues)
    if len(public_items) > 100:
        public_items = public_items[:100]
        summary.truncated = True
    return {
        "summary": summary,
        "items": public_items if include_items else [],
        "_raw_items": issues,
        "last_updated_at": status.get("last_updated_at"),
        "scope": status.get("sidecar_scope"),
    }


def _normalize_status(raw_status: Optional[str], *, recovered: bool = False) -> str:
    if recovered and raw_status not in TERMINAL_TASK_STATUSES:
        return "interrupted"
    return {
        "pending": "queued",
        "queued": "queued",
        "starting": "queued",
        "running": "running",
        "processing": "running",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }.get(str(raw_status or "").lower(), "unknown")


def _job_allowed_actions(
    status: str,
    validation: AgentValidationSummary,
    output_paths: list[str],
    *,
    kind: str,
) -> list[str]:
    actions = ["poll"] if status in {"queued", "running"} else []
    if status in {"failed", "interrupted"}:
        actions.append("retry")
    if status == "completed":
        if validation.available:
            actions.append("inspect_validation")
        if validation.errors or validation.human_review_items:
            actions.append("repair")
        if kind == "dry_run":
            actions.append("create_translation_plan")
        elif output_paths and validation.errors == 0:
            actions.append("approve_export")
    return actions


async def _build_job_response(job_id: str) -> AgentJobResponse:
    metadata = agent_registry.get_job(job_id)
    live_task = task_state.get_task(job_id)
    recovered = False
    if live_task is None:
        if not metadata:
            raise _error(404, "job_not_found", "Agent job not found")
        live_task = metadata.get("last_snapshot") or {}
        recovered = True

    project_id = (
        live_task.get("project_id")
        or (metadata or {}).get("project_id")
    )
    kind = live_task.get("agent_job_kind") or (metadata or {}).get(
        "kind", "translation"
    )
    validation_payload = await _validation_payload(project_id)
    validation = validation_payload["summary"]
    progress = live_task.get("progress") or {}
    output_paths = [
        str(path)
        for path in live_task.get("output_dirs", [])
        if path
    ]
    if live_task.get("result_path") and live_task["result_path"] not in output_paths:
        output_paths.append(str(live_task["result_path"]))
    status = _normalize_status(live_task.get("status"), recovered=recovered)
    response = AgentJobResponse(
        job_id=job_id,
        project_id=project_id,
        status=status,
        kind=kind,
        progress={
            "completed_files": int(progress.get("current") or 0),
            "total_files": int(progress.get("total") or 0),
            "percent": int(progress.get("percent") or 0),
            "current_file": str(progress.get("current_file") or ""),
            "stage": str(progress.get("stage") or ""),
            "successful_batches": int(progress.get("successful_batches") or 0),
            "failed_batches": int(progress.get("failed_batches") or 0),
        },
        validation=validation,
        allowed_actions=_job_allowed_actions(
            status, validation, output_paths, kind=kind
        ),
        output_paths=output_paths,
        message=live_task.get("message"),
        recovery={
            "source": "persisted_snapshot" if recovered else "live_task_state",
            "checkpoint_resume_supported": bool(
                (metadata or {}).get("execution_args", {}).get("use_resume", False)
            ),
        },
        links={
            "self": f"/api/agent/jobs/{job_id}",
            "validation": f"/api/agent/jobs/{job_id}/validation",
            "export_preview": f"/api/agent/jobs/{job_id}/export-preview",
        },
    )
    agent_registry.update_snapshot(
        job_id,
        {
            "status": live_task.get("status"),
            "progress": live_task.get("progress") or {},
            "project_id": project_id,
            "agent_job_kind": kind,
            "output_dirs": output_paths,
            "result_path": live_task.get("result_path"),
            "message": live_task.get("message"),
        },
    )
    return response


async def _project_summary(project: Dict[str, Any]) -> AgentProjectSummary:
    project_id = str(project.get("project_id") or project.get("id") or "")
    files = await project_manager.get_project_files(project_id)
    status_counts: Dict[str, int] = {}
    for item in files:
        status = str(item.get("status") or "todo")
        status_counts[status] = status_counts.get(status, 0) + 1
    validation = (await _validation_payload(project_id))["summary"]
    actions = ["inspect", "create_translation_plan"]
    if validation.total:
        actions.append("inspect_validation")
    return AgentProjectSummary(
        project_id=project_id,
        name=str(project.get("name") or ""),
        game_id=str(project.get("game_id") or ""),
        source_language=str(project.get("source_language") or "en"),
        status=str(project.get("status") or "active"),
        file_count=len(files),
        file_status_counts=status_counts,
        validation=validation,
        allowed_actions=actions,
    )


@router.get("/capabilities")
async def get_capabilities():
    """Discover safe Agent operations without exposing provider secrets."""
    return {
        "api_version": AGENT_API_VERSION,
        "remis_version": PROJECT_INFO["version"],
        "service": "remis-agent-api",
        "transport": {
            "base_url": "/api/agent",
            "localhost_only": True,
            "polling": True,
            "websocket_status": True,
        },
        "games": [_public_game(item) for item in GAME_PROFILES.values()],
        "languages": [
            {"code": item["code"], "name": item["name_en"]}
            for item in LANGUAGES.values()
        ],
        "providers": [
            _public_provider(provider_id, config)
            for provider_id, config in API_PROVIDERS.items()
        ],
        "actions": {
            "read_projects": {"supported": True, "requires_approval": False},
            "plan_translation": {"supported": True, "requires_approval": False},
            "run_dry_run": {"supported": True, "requires_approval": False},
            "start_translation": {"supported": True, "requires_approval": True},
            "resume_from_checkpoint": {
                "supported": True,
                "requires_approval": True,
            },
            "pause": {
                "supported": False,
                "reason": "The current runner has no safe cooperative pause boundary.",
            },
            "cancel": {
                "supported": False,
                "reason": "The current runner has no safe cooperative cancellation boundary.",
            },
            "repair": {"supported": True, "requires_approval": True},
            "export": {"supported": True, "requires_approval": True},
        },
        "safety": {
            "api_keys_returned": False,
            "direct_database_writes_allowed": False,
            "direct_localization_file_edits_allowed": False,
            "custom_export_paths_restricted": True,
        },
        "links": {
            "health": "/api/health",
            "preflight": "/api/agent/preflight",
            "openapi": "/openapi.json",
            "docs": "/docs",
            "projects": "/api/agent/projects",
        },
    }


@router.get("/preflight")
def get_agent_preflight(provider_id: Optional[str] = None):
    """Run the mandatory release and provider-setup checks before Agent work."""
    provider_setup = _provider_setup(provider_id)
    release_check = _release_check()
    actions = []
    if release_check["update_available"]:
        actions.append("review_latest_release")
    if provider_setup["setup_required"]:
        actions.append("configure_provider")
    if not release_check["checked"]:
        actions.append("report_release_check_unavailable")
    return {
        "status": "attention_required" if actions else "ready",
        "release_check": release_check,
        "provider_setup": provider_setup,
        "required_before_every_workflow": True,
        "allowed_actions": actions or ["continue"],
    }


@router.get("/projects", response_model=list[AgentProjectSummary])
async def list_agent_projects(status: Optional[str] = None):
    projects = sanitize_for_json(await project_manager.get_projects(status))
    return [await _project_summary(project) for project in projects]


@router.post("/projects/inspect")
async def inspect_agent_project(request: AgentProjectInspectRequest):
    inspection = _validate_agent_import_path(request.folder_path)
    return {
        "status": "ready",
        "inspection": inspection,
        "allowed_actions": ["create_project_plan"],
    }


@router.post("/projects/plan", response_model=AgentProjectPlanResponse)
async def plan_agent_project(request: AgentProjectPlanRequest):
    inspection = _validate_agent_import_path(request.folder_path)
    execution_args = {
        "name": request.name.strip(),
        "folder_path": inspection["folder_path"],
        "game_id": request.game_id,
        "source_language": (
            request.source_language.value
            if hasattr(request.source_language, "value")
            else str(request.source_language)
        ),
        "import_mode": request.import_mode,
    }
    if not execution_args["name"]:
        raise _error(400, "invalid_request", "Project name is required")
    summary = (
        f"Create Remis project '{execution_args['name']}' using "
        f"{request.import_mode} import mode."
    )
    record = agent_registry.create_plan(
        project_id=None,
        execution_args=execution_args,
        dry_run=False,
        summary=summary,
        kind="project_import",
        inspection=inspection,
    )
    return AgentProjectPlanResponse(
        plan_id=record["plan_id"],
        status="awaiting_approval",
        inspection=inspection,
        risk={
            "writes_database": True,
            "copies_files": request.import_mode == "copy",
            "modifies_source_folder": False,
            "starts_translation": False,
        },
        summary=summary,
        allowed_actions=["approve_create_project"],
        expires_at=record["expires_at"],
    )


@router.post("/projects", response_model=AgentProjectSummary)
async def create_agent_project(request: AgentProjectCreateRequest):
    try:
        plan = agent_registry.consume_plan(request.plan_id, approved=request.approved)
    except KeyError as exc:
        raise _error(404, "plan_not_found", str(exc)) from exc
    except TimeoutError as exc:
        raise _error(410, "plan_expired", str(exc)) from exc
    except RuntimeError as exc:
        raise _error(409, "plan_already_used", str(exc)) from exc
    except PermissionError as exc:
        raise _error(409, "approval_required", str(exc)) from exc
    if plan.get("kind") != "project_import":
        agent_registry.release_plan(request.plan_id)
        raise _error(400, "wrong_plan_type", "Plan is not a project import plan")
    args = plan["execution_args"]
    try:
        project = await project_manager.create_project(**args)
    except Exception:
        agent_registry.release_plan(request.plan_id)
        raise
    project_id = str(project.get("project_id") or project.get("id") or "")
    agent_registry.record_event(
        "project_created",
        project_id=project_id,
        plan_id=request.plan_id,
        import_mode=args["import_mode"],
    )
    return await _project_summary(project)


@router.get(
    "/projects/{project_id}/status",
    response_model=AgentProjectSummary,
)
async def get_agent_project_status(project_id: str):
    project = await project_manager.get_project(project_id)
    if not project:
        raise _error(404, "project_not_found", "Project not found")
    return await _project_summary(sanitize_for_json(project))


@router.post("/jobs/plan", response_model=AgentPlanResponse)
async def plan_agent_job(request: AgentJobPlanRequest):
    provider = API_PROVIDERS.get(request.api_provider)
    if provider is None:
        raise _error(400, "invalid_provider", "Unknown API provider")
    env_name = provider.get("api_key_env")
    if env_name and not get_api_key(request.api_provider, env_name):
        raise _error(
            409,
            "provider_setup_required",
            (
                f"{provider.get('name') or request.api_provider} requires an API key. "
                "Configure it in Remis Settings > API Settings. If the user does not "
                "know what an API key is, explain it before continuing."
            ),
        )
    try:
        plan = await create_translation_plan(
            project_id=request.project_id,
            target_lang_codes=[
                item.value if hasattr(item, "value") else str(item)
                for item in request.target_lang_codes
            ],
            api_provider=request.api_provider,
            model=request.model,
            batch_size_limit=request.batch_size_limit,
            concurrency_limit=request.concurrency_limit,
            rpm_limit=request.rpm_limit,
            use_resume=request.use_resume,
            use_main_glossary=request.use_main_glossary,
            embedded_workshop_enabled=request.embedded_workshop_enabled,
        )
    except ValueError as exc:
        message = str(exc)
        code = "project_not_found" if "Project not found" in message else "invalid_request"
        raise _error(404 if code == "project_not_found" else 400, code, message) from exc

    summary = (
        "Read-only readiness check. No model call or localization output will be written."
        if request.dry_run
        else "Start the existing Remis translation workflow after explicit approval."
    )
    record = agent_registry.create_plan(
        project_id=request.project_id,
        execution_args=plan["execution_args"],
        dry_run=request.dry_run,
        summary=summary,
    )
    local_provider = request.api_provider in LOCAL_PROVIDER_IDS
    return AgentPlanResponse(
        plan_id=record["plan_id"],
        status="ready" if request.dry_run else "awaiting_approval",
        project_id=request.project_id,
        dry_run=request.dry_run,
        requires_approval=not request.dry_run,
        risk={
            "writes_output": not request.dry_run,
            "may_use_paid_api": not request.dry_run and not local_provider,
            "overwrites_existing_output": False,
            "exports_to_game_directory": False,
        },
        summary=summary,
        allowed_actions=["start_dry_run"] if request.dry_run else ["approve_start"],
        expires_at=record["expires_at"],
    )


@router.post("/jobs", response_model=AgentJobResponse)
async def start_agent_job(
    request: AgentJobStartRequest,
    background_tasks: BackgroundTasks,
):
    try:
        plan = agent_registry.consume_plan(request.plan_id, approved=request.approved)
    except KeyError as exc:
        raise _error(404, "plan_not_found", str(exc)) from exc
    except TimeoutError as exc:
        raise _error(410, "plan_expired", str(exc)) from exc
    except RuntimeError as exc:
        raise _error(409, "plan_already_used", str(exc)) from exc
    except PermissionError as exc:
        raise _error(409, "approval_required", str(exc)) from exc

    args = plan["execution_args"]
    if plan["dry_run"]:
        project = await project_manager.get_project(plan["project_id"])
        files = await project_manager.get_project_files(plan["project_id"])
        job_id = f"job_{uuid.uuid4().hex}"
        task_state.create_task(
            job_id,
            status="completed",
            log_message="Agent dry-run readiness check completed.",
            fields={
                "kind": "dry_run",
                "project_id": plan["project_id"],
                "created_by": {"type": "remis_agent", "label": "Remis Agent"},
                "idempotency_key": request.plan_id,
            },
        )
        task_state.init_progress(
            job_id,
            {
                "total": len(files),
                "current": len(files),
                "percent": 100,
                "stage": "Readiness check completed",
            },
        )
        task_state.update_task(
            job_id,
            summary={
                "project_name": (project or {}).get("name"),
                "file_count": len(files),
                "would_use_provider": args.get("api_provider"),
                "would_use_model": args.get("model"),
            },
            fields={
                "project_id": plan["project_id"],
                "agent_job_kind": "dry_run",
                "output_dirs": [],
            },
        )
        agent_registry.record_job(
            job_id=job_id,
            project_id=plan["project_id"],
            plan_id=request.plan_id,
            kind="dry_run",
            execution_args=args,
        )
        return await _build_job_response(job_id)

    try:
        response = await start_translation_project(
            InitialTranslationRequest(**{**args, "idempotency_key": request.plan_id}),
            background_tasks,
        )
    except Exception:
        agent_registry.release_plan(request.plan_id)
        raise
    job_id = response["task_id"]
    task_state.update_task(
        job_id,
        fields={
            "project_id": plan["project_id"],
            "agent_job_kind": "translation",
            "created_by": {"type": "remis_agent", "label": "Remis Agent"},
            "idempotency_key": request.plan_id,
        },
    )
    agent_registry.record_job(
        job_id=job_id,
        project_id=plan["project_id"],
        plan_id=request.plan_id,
        kind="translation",
        execution_args=args,
    )
    try:
        await project_manager.log_history_event(
            plan["project_id"],
            "agent_translation_started",
            "Codex-approved Agent API translation job started.",
            metadata={"job_id": job_id, "plan_id": request.plan_id},
        )
    except Exception:
        # A history write must not hide a translation task that already started.
        agent_registry.record_event(
            "history_write_failed",
            project_id=plan["project_id"],
            job_id=job_id,
        )
    return await _build_job_response(job_id)


@router.get("/jobs/{job_id}", response_model=AgentJobResponse)
async def get_agent_job(job_id: str):
    return await _build_job_response(job_id)


@router.get("/jobs/{job_id}/validation")
async def get_agent_job_validation(job_id: str):
    metadata = agent_registry.get_job(job_id)
    task = task_state.get_task(job_id) or {}
    project_id = task.get("project_id") or (metadata or {}).get("project_id")
    if not project_id:
        raise _error(404, "job_not_found", "Agent job not found")
    payload = await _validation_payload(project_id, include_items=True)
    return {
        "job_id": job_id,
        "project_id": project_id,
        "summary": payload["summary"],
        "items": payload["items"],
        "last_updated_at": payload.get("last_updated_at"),
        "scope": payload.get("scope"),
        "allowed_actions": (
            ["repair"] if payload["summary"].total else ["approve_export"]
        ),
    }


@router.post("/jobs/{job_id}/retry", response_model=AgentPlanResponse)
async def retry_agent_job(job_id: str):
    metadata = agent_registry.get_job(job_id)
    if not metadata:
        raise _error(404, "job_not_found", "Agent job not found")
    args = metadata.get("execution_args") or {}
    try:
        plan = await create_translation_plan(
            project_id=metadata["project_id"],
            target_lang_codes=args.get("target_lang_codes", []),
            api_provider=args.get("api_provider", "lm_studio"),
            model=args.get("model", "local-model"),
            batch_size_limit=args.get("batch_size_limit"),
            concurrency_limit=args.get("concurrency_limit"),
            rpm_limit=args.get("rpm_limit", 40),
            use_resume=True,
            use_main_glossary=args.get("use_main_glossary", True),
            embedded_workshop_enabled=(
                args.get("embedded_workshop", {}).get("enabled", True)
            ),
        )
    except ValueError as exc:
        raise _error(400, "retry_not_available", str(exc)) from exc
    record = agent_registry.create_plan(
        project_id=metadata["project_id"],
        execution_args=plan["execution_args"],
        dry_run=False,
        summary="Resume or retry the existing Remis workflow from its checkpoint.",
    )
    return AgentPlanResponse(
        plan_id=record["plan_id"],
        status="awaiting_approval",
        project_id=metadata["project_id"],
        requires_approval=True,
        risk={
            "writes_output": True,
            "may_use_paid_api": args.get("api_provider") not in LOCAL_PROVIDER_IDS,
            "resumes_checkpoint": True,
        },
        summary=record["summary"],
        allowed_actions=["approve_start"],
        expires_at=record["expires_at"],
    )


@router.post("/jobs/{job_id}/repair", response_model=AgentJobResponse)
async def repair_agent_job(
    job_id: str,
    request: AgentRepairRequest,
    background_tasks: BackgroundTasks,
):
    if not request.approved:
        raise _error(
            409,
            "approval_required",
            "Explicit approval is required before repair may call a model or write fixes.",
        )
    metadata = agent_registry.get_job(job_id)
    if not metadata:
        raise _error(404, "job_not_found", "Agent job not found")
    validation = await _validation_payload(
        metadata["project_id"], include_items=True
    )
    issues = validation["_raw_items"]
    if not issues:
        raise _error(409, "no_repair_items", "No active validation items need repair")
    args = metadata.get("execution_args") or {}
    api_provider = request.api_provider or args.get("api_provider") or "lm_studio"
    api_model = request.api_model or args.get("model") or "local-model"
    repair_scope = (
        f"{job_id}:{metadata['project_id']}:{api_provider}:{api_model}:"
        f"{[(item.get('file_name'), item.get('key'), item.get('status')) for item in issues]}"
    )
    idempotency_key = request.idempotency_key or f"agent-repair:{uuid.uuid5(uuid.NAMESPACE_URL, repair_scope)}"
    response = await start_fix_run(
        FixRunRequest(
            project_id=metadata["project_id"],
            api_provider=api_provider,
            api_model=api_model,
            batch_size_limit=request.batch_size_limit,
            concurrency_limit=request.concurrency_limit,
            rpm_limit=request.rpm_limit,
            max_retries=request.max_retries,
            issues=issues,
            approval={
                "approved": request.approved,
                "issue_count": len(issues),
                "api_provider": api_provider,
                "api_model": api_model,
            },
            idempotency_key=idempotency_key,
            created_by={"type": "remis_agent", "label": "Remis Agent"},
        ),
        background_tasks,
    )
    repair_job_id = response.task_id
    task_state.update_task(
        repair_job_id,
        fields={
            "project_id": metadata["project_id"],
            "parent_job_id": job_id,
            "parent_task_id": job_id,
            "agent_job_kind": "repair",
            "created_by": {"type": "remis_agent", "label": "Remis Agent"},
        },
    )
    agent_registry.record_job(
        job_id=repair_job_id,
        project_id=metadata["project_id"],
        plan_id=metadata["plan_id"],
        kind="repair",
        execution_args=args,
    )
    agent_registry.record_event(
        "repair_approved",
        project_id=metadata["project_id"],
        job_id=repair_job_id,
        parent_job_id=job_id,
    )
    return await _build_job_response(repair_job_id)


def _export_candidate(
    task: Dict[str, Any],
    metadata: Dict[str, Any],
    requested_name: Optional[str],
) -> tuple[str, Path]:
    persisted_snapshot = metadata.get("last_snapshot") or {}
    raw_output_paths = (
        task.get("output_dirs")
        or persisted_snapshot.get("output_dirs")
        or []
    )
    output_paths = [Path(item).resolve() for item in raw_output_paths]
    destination_root = Path(DEST_DIR).resolve()
    candidates = {
        item.name: item for item in output_paths if item.parent == destination_root
    }
    if requested_name:
        if (
            requested_name in {".", ".."}
            or "/" in requested_name
            or "\\" in requested_name
        ):
            raise _error(
                400,
                "invalid_output_folder",
                "output_folder_name must be a single folder name",
            )
        requested = candidates.get(requested_name)
        if requested is None:
            raise _error(
                400,
                "unknown_output_folder",
                "The requested output folder does not belong to this job",
            )
        return requested.name, requested
    if len(candidates) != 1:
        raise _error(
            409,
            "output_selection_required",
            "Select one output folder from the job before export",
        )
    candidate = next(iter(candidates.values()))
    return candidate.name, candidate


def _validate_deploy_target(
    game_id: str,
    output_folder_name: str,
    target_deploy_path: Optional[str],
) -> Path:
    try:
        _, target = deploy_manager.mod_deployer.resolve_deploy_target(
            output_folder_name,
            game_id,
            target_deploy_path,
        )
        return target
    except ValueError as exc:
        logger.info("Agent rejected deployment target: %s", exc)
        raise _error(
            403,
            "export_path_not_allowed",
            "Agent exports are restricted to the detected game mod directory",
        ) from exc


@router.get("/jobs/{job_id}/export-preview")
async def preview_agent_export(job_id: str, output_folder_name: Optional[str] = None):
    metadata = agent_registry.get_job(job_id)
    task = task_state.get_task(job_id) or {}
    if not metadata:
        raise _error(404, "job_not_found", "Agent job not found")
    folder_name, source_path = _export_candidate(
        task, metadata, output_folder_name
    )
    project = await project_manager.get_project(metadata["project_id"])
    game_id = str((project or {}).get("game_id") or "")
    target = _validate_deploy_target(game_id, folder_name, None)
    return {
        "job_id": job_id,
        "project_id": metadata["project_id"],
        "source_path": str(source_path),
        "target_path": str(target),
        "target_exists": target.exists(),
        "requires_approval": True,
        "requires_overwrite_confirmation": target.exists(),
        "allowed_actions": ["approve_export"],
    }


@router.post("/jobs/{job_id}/approve-export")
async def approve_agent_export(job_id: str, request: AgentExportRequest):
    if not request.approved:
        raise _error(
            409,
            "approval_required",
            "Explicit approval is required before exporting to a game directory",
        )
    if request.target_deploy_path and not request.confirm_overwrite:
        raise _error(
            409,
            "overwrite_confirmation_required",
            "Custom export targets require overwrite confirmation",
        )
    metadata = agent_registry.get_job(job_id)
    task = task_state.get_task(job_id) or {}
    if not metadata:
        raise _error(404, "job_not_found", "Agent job not found")
    validation = (await _validation_payload(metadata["project_id"]))["summary"]
    if validation.errors:
        raise _error(
            409,
            "validation_errors_block_export",
            "Resolve validation errors before exporting",
        )
    folder_name, _ = _export_candidate(
        task, metadata, request.output_folder_name
    )
    project = await project_manager.get_project(metadata["project_id"])
    game_id = request.game_id or str((project or {}).get("game_id") or "")
    target = _validate_deploy_target(
        game_id, folder_name, request.target_deploy_path
    )
    if target.exists() and not request.confirm_overwrite:
        raise _error(
            409,
            "overwrite_confirmation_required",
            "The target already exists. Confirm overwrite before exporting.",
        )
    result = deploy_manager.mod_deployer.deploy_mod(
        output_folder_name=folder_name,
        game_id=game_id,
        target_deploy_path=str(target),
        clean_fake_loc=False,
    )
    if result.get("status") == "error":
        logger.error("Agent export failed")
        raise _error(
            500,
            "export_failed",
            "Export failed. Check Remis logs for details.",
            retryable=True,
        )
    await project_manager.log_history_event(
        metadata["project_id"],
        "agent_export_approved",
        "Codex-approved Agent API export completed.",
        metadata={"job_id": job_id, "target_path": str(target)},
    )
    agent_registry.record_event(
        "export_approved",
        project_id=metadata["project_id"],
        job_id=job_id,
        target_path=str(target),
    )
    return {
        "job_id": job_id,
        "status": "completed",
        "target_path": str(target),
        "warnings": (
            ["Deployment completed, but the launcher descriptor may need review."]
            if result.get("status") == "warning"
            else []
        ),
        "allowed_actions": [],
    }
