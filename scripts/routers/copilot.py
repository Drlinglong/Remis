"""HTTP API for Remis Help Copilot (Phase 1)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from scripts.core.copilot import list_actions, run_copilot_chat
from scripts.core.copilot.actions import get_client_handler
from scripts.schemas.copilot import (
    CopilotActionDescriptor,
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotStatusResponse,
    CopilotWorkflowApprovalRequest,
    CopilotWorkflowPlanRequest,
    CopilotTranslationPlanRequest,
    CopilotAgentRecommendationRequest,
    CopilotSettingsUpdate,
)
from scripts.core.copilot.settings import (
    get_copilot_settings,
    list_copilot_providers,
    update_copilot_settings,
)
from scripts.core.copilot.agent_planner import recommend_initial_translation
from scripts.core.copilot.workflow import (
    approve_and_execute_plan,
    create_localization_plan,
    create_translation_plan,
    ensure_localization_provider_ready,
    ensure_translation_provider_ready,
    get_localization_translation_args,
    release_plan_reservation,
    reserve_translation_plan,
)
from scripts.core.copilot.provider_readiness import ProviderReadinessError
from scripts.core.copilot.service import resolve_copilot_context_budget
from scripts.routers.translation import start_translation_project
from scripts.schemas.translation import InitialTranslationRequest
from scripts.shared import task_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


def _copilot_settings_with_budget() -> dict[str, Any]:
    settings = get_copilot_settings()
    return {
        **settings,
        "context_budget_tokens": resolve_copilot_context_budget(
            settings["provider"], settings.get("model"), None
        ),
    }


def _workflow_plan_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail={
            "code": "workflow_plan_not_found",
            "message": "The workflow plan was not found or Remis restarted.",
            "retryable": False,
        })
    if isinstance(exc, TimeoutError):
        return HTTPException(status_code=410, detail={
            "code": "workflow_plan_expired",
            "message": "The workflow plan expired. Generate a fresh read-only preview.",
            "retryable": False,
        })
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail={
            "code": "workflow_plan_already_used",
            "message": "The workflow plan was already used and cannot be approved again.",
            "retryable": False,
        })
    return HTTPException(status_code=400, detail={
        "code": "workflow_plan_invalid",
        "message": str(exc),
        "retryable": False,
    })


@router.get("/settings")
def copilot_settings():
    return {"settings": _copilot_settings_with_budget(), "providers": list_copilot_providers()}


@router.put("/settings")
def save_copilot_settings(request: CopilotSettingsUpdate):
    try:
        update_copilot_settings(**request.model_dump())
        return _copilot_settings_with_budget()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status", response_model=CopilotStatusResponse)
def copilot_status():
    settings = _copilot_settings_with_budget()
    return CopilotStatusResponse(
        phase=2,
        context_budget_tokens=settings["context_budget_tokens"],
        default_provider=settings["provider"],
        default_model=settings["model"],
        reasoning_enabled=settings["reasoning_enabled"],
        reasoning_preset=settings["reasoning_preset"],
    )


@router.get("/actions", response_model=list[CopilotActionDescriptor])
def copilot_actions():
    return [CopilotActionDescriptor(**item) for item in list_actions(phase=2)]


@router.get("/actions/{action_id}")
def copilot_action_detail(action_id: str):
    handler = get_client_handler(action_id)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Unknown action: {action_id}")
    return handler


@router.post("/chat", response_model=CopilotChatResponse)
def copilot_chat(request: CopilotChatRequest):
    """
    Non-streaming help chat.

    Phase 1 defaults to local LM Studio for testing. The request body already
    accepts provider/model so the frontend picker can be wired later without
    another API change.
    """
    try:
        settings = get_copilot_settings()
        kwargs = {
            "messages": request.messages,
            "provider": request.provider or settings["provider"],
            "model": request.model or settings["model"],
            "reasoning_override": {
                "reasoning_builtin_enabled": settings["reasoning_enabled"],
                "reasoning_preset": settings["reasoning_preset"],
                "custom_parameters": {},
            },
            "locale": request.locale,
            "page_context": request.page_context,
        }
        if request.context_budget_tokens:
            kwargs["context_budget_tokens"] = request.context_budget_tokens
        return run_copilot_chat(**kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Copilot chat endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/workflows/localize-mod/plan")
def plan_localize_mod(request: CopilotWorkflowPlanRequest):
    """Read-only inspection plus an immutable, approval-gated project plan."""
    try:
        return create_localization_plan(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/execute")
async def execute_workflow(request: CopilotWorkflowApprovalRequest):
    """Execute only the server-side plan previously shown to the user."""
    try:
        return await approve_and_execute_plan(request.plan_id)
    except (KeyError, TimeoutError, RuntimeError, ValueError) as exc:
        raise _workflow_plan_http_error(exc) from exc


@router.post("/workflows/localize-mod/execute")
async def execute_guided_localization(
    request: CopilotWorkflowApprovalRequest,
    background_tasks: BackgroundTasks,
):
    """Execute the exact project + translation parameters shown in chat."""
    try:
        # This must run before approve_and_execute_plan, whose first effect is
        # creating the Remis project. Failed readiness therefore leaves no
        # project or copied source files behind and the plan remains retryable.
        readiness = await ensure_localization_provider_ready(request.plan_id)
        translation_args = get_localization_translation_args(request.plan_id)
        project_result = await approve_and_execute_plan(request.plan_id)
        project_id = project_result["project"]["project_id"]
        try:
            translation_plan = await create_translation_plan(
                project_id=project_id, **translation_args
            )
        except Exception as exc:
            return _guided_localization_partial_success(
                request.plan_id,
                project_result["project"],
                exc,
                readiness=readiness,
                stage="translation_plan",
            )
        try:
            args = reserve_translation_plan(translation_plan["plan_id"])
        except Exception as exc:
            return _guided_localization_partial_success(
                request.plan_id,
                project_result["project"],
                exc,
                readiness=readiness,
                stage="translation_plan_reservation",
                translation_plan_id=translation_plan["plan_id"],
            )
        try:
            response = await start_translation_project(
                InitialTranslationRequest(
                    **{**args, "idempotency_key": translation_plan["plan_id"]}
                ),
                background_tasks,
            )
        except Exception as exc:
            release_plan_reservation(translation_plan["plan_id"])
            return _guided_localization_partial_success(
                request.plan_id,
                project_result["project"],
                exc,
                readiness=readiness,
                stage="translation_start",
                translation_plan_id=translation_plan["plan_id"],
            )
        try:
            task_state.update_task(
                response["task_id"],
                fields={
                    "created_by": {"type": "remis_agent", "label": "Remis Copilot"},
                    "idempotency_key": translation_plan["plan_id"],
                },
            )
        except Exception:
            # The task has already been accepted; metadata enrichment must not
            # turn a started translation into a false failure response.
            logger.exception("Unable to enrich guided translation task metadata")
        return {
            "plan_id": request.plan_id,
            "translation_plan_id": translation_plan["plan_id"],
            "workflow_status": "started",
            "provider_readiness": readiness,
            "project": project_result["project"],
            **response,
        }
    except ProviderReadinessError as exc:
        raise HTTPException(status_code=409, detail=exc.as_detail()) from exc
    except (KeyError, TimeoutError, RuntimeError, ValueError) as exc:
        raise _workflow_plan_http_error(exc) from exc


def _guided_localization_partial_success(
    plan_id: str,
    project: dict[str, Any],
    error: Exception,
    *,
    readiness: dict[str, Any] | None,
    stage: str,
    translation_plan_id: str | None = None,
) -> dict[str, Any]:
    """Return a recoverable result after the project write has succeeded."""
    if isinstance(error, HTTPException):
        detail = error.detail
        if isinstance(detail, dict):
            error_code = str(detail.get("code") or "translation_start_failed")
            message = str(detail.get("message") or "Initial translation did not start.")
            retryable = bool(detail.get("retryable", True))
        else:
            error_code = "translation_start_failed"
            message = str(detail)
            retryable = True
    else:
        error_code = "translation_plan_failed" if stage == "translation_plan" else "translation_start_failed"
        message = "Initial translation did not start; the created project is preserved for recovery."
        retryable = True
    if translation_plan_id:
        recovery = {
            "safe_to_retry": retryable,
            "action": "retry_initial_translation",
            "label": "重试初次翻译",
            "args": {"plan_id": translation_plan_id},
            "requires_approval": True,
        }
    else:
        recovery = {
            "safe_to_retry": retryable,
            "action": "open_initial_translation",
            "label": "进入初次翻译并重新检查参数",
            "args": {"project_id": project.get("project_id")},
            "requires_approval": True,
        }
    result = {
        "plan_id": plan_id,
        "code": "project_created_translation_not_started",
        "workflow_status": "project_created_translation_not_started",
        "status": "project_created_translation_not_started",
        "partial_success": True,
        "project_created": True,
        "translation_started": False,
        "failure_stage": stage,
        "project": project,
        "provider_readiness": readiness,
        "error": {
            "code": error_code,
            "message": message,
            "retryable": retryable,
            "stage": stage,
        },
        "recovery": recovery,
        "next_action": recovery,
        "allowed_recovery_actions": [
            "replan_initial_translation",
            "open_existing_project",
        ],
    }
    if translation_plan_id:
        result["translation_plan_id"] = translation_plan_id
    return result


@router.post("/workflows/initial-translation/plan")
async def plan_initial_translation(request: CopilotTranslationPlanRequest):
    try:
        return await create_translation_plan(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/initial-translation/recommend")
async def recommend_translation(request: CopilotAgentRecommendationRequest):
    try:
        settings = get_copilot_settings()
        return await recommend_initial_translation(
            project_id=request.project_id,
            target_lang_codes=request.target_lang_codes,
            preferred_provider=request.preferred_provider,
            provider=request.planner_provider or settings["provider"],
            model=request.planner_model or settings["model"],
            reasoning_enabled=settings["reasoning_enabled"],
            reasoning_preset=settings["reasoning_preset"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/initial-translation/execute")
async def execute_initial_translation(
    request: CopilotWorkflowApprovalRequest,
    background_tasks: BackgroundTasks,
):
    try:
        readiness = await ensure_translation_provider_ready(request.plan_id)
        args = reserve_translation_plan(request.plan_id)
        response = await start_translation_project(
            InitialTranslationRequest(**{**args, "idempotency_key": request.plan_id}),
            background_tasks,
        )
        task_state.update_task(
            response["task_id"],
            fields={
                "created_by": {"type": "remis_agent", "label": "Remis Copilot"},
                "idempotency_key": request.plan_id,
            },
        )
        return {
            "plan_id": request.plan_id,
            "workflow_status": "started",
            "provider_readiness": readiness,
            **response,
        }
    except ProviderReadinessError as exc:
        raise HTTPException(status_code=409, detail=exc.as_detail()) from exc
    except (KeyError, TimeoutError, RuntimeError) as exc:
        raise _workflow_plan_http_error(exc) from exc
    except (ValueError, HTTPException):
        release_plan_reservation(request.plan_id)
        raise
    except Exception:
        release_plan_reservation(request.plan_id)
        raise
