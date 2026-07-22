"""HTTP API for Remis Help Copilot (Phase 1)."""

from __future__ import annotations

import logging

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
)
from scripts.core.copilot.agent_planner import recommend_initial_translation
from scripts.core.copilot.workflow import (
    approve_and_execute_plan,
    create_localization_plan,
    create_translation_plan,
    get_localization_translation_args,
    release_plan_reservation,
    reserve_translation_plan,
)
from scripts.routers.translation import start_translation_project
from scripts.schemas.translation import InitialTranslationRequest
from scripts.shared import task_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


@router.get("/status", response_model=CopilotStatusResponse)
def copilot_status():
    from scripts.core.copilot.context_budget import DEFAULT_INPUT_TOKEN_BUDGET

    return CopilotStatusResponse(phase=2, context_budget_tokens=DEFAULT_INPUT_TOKEN_BUDGET)


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
        kwargs = {
            "messages": request.messages,
            "provider": request.provider,
            "model": request.model,
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
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/localize-mod/execute")
async def execute_guided_localization(
    request: CopilotWorkflowApprovalRequest,
    background_tasks: BackgroundTasks,
):
    """Execute the exact project + translation parameters shown in chat."""
    try:
        project_result = await approve_and_execute_plan(request.plan_id)
        project_id = project_result["project"]["project_id"]
        translation_args = get_localization_translation_args(request.plan_id)
        translation_plan = await create_translation_plan(project_id=project_id, **translation_args)
        args = reserve_translation_plan(translation_plan["plan_id"])
        try:
            response = await start_translation_project(InitialTranslationRequest(**args), background_tasks)
        except Exception:
            release_plan_reservation(translation_plan["plan_id"])
            raise
        task_state.update_task(
            response["task_id"],
            fields={
                "created_by": {"type": "remis_agent", "label": "Remis Copilot"},
                "idempotency_key": translation_plan["plan_id"],
            },
        )
        return {
            "plan_id": request.plan_id,
            "translation_plan_id": translation_plan["plan_id"],
            "workflow_status": "started",
            "project": project_result["project"],
            **response,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/initial-translation/plan")
async def plan_initial_translation(request: CopilotTranslationPlanRequest):
    try:
        return await create_translation_plan(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/initial-translation/recommend")
async def recommend_translation(request: CopilotAgentRecommendationRequest):
    try:
        return await recommend_initial_translation(
            project_id=request.project_id,
            target_lang_codes=request.target_lang_codes,
            preferred_provider=request.preferred_provider,
            provider=request.planner_provider,
            model=request.planner_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/initial-translation/execute")
async def execute_initial_translation(
    request: CopilotWorkflowApprovalRequest,
    background_tasks: BackgroundTasks,
):
    try:
        args = reserve_translation_plan(request.plan_id)
        response = await start_translation_project(
            InitialTranslationRequest(**args), background_tasks
        )
        task_state.update_task(
            response["task_id"],
            fields={
                "created_by": {"type": "remis_agent", "label": "Remis Copilot"},
                "idempotency_key": request.plan_id,
            },
        )
        return {"plan_id": request.plan_id, "workflow_status": "started", **response}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, HTTPException):
        release_plan_reservation(request.plan_id)
        raise
    except Exception:
        release_plan_reservation(request.plan_id)
        raise
