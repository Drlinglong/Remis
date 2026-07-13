"""HTTP API for Remis Help Copilot (Phase 1)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from scripts.core.copilot import list_actions, run_copilot_chat
from scripts.core.copilot.actions import get_client_handler
from scripts.schemas.copilot import (
    CopilotActionDescriptor,
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


@router.get("/status", response_model=CopilotStatusResponse)
def copilot_status():
    from scripts.core.copilot.context_budget import DEFAULT_INPUT_TOKEN_BUDGET

    return CopilotStatusResponse(context_budget_tokens=DEFAULT_INPUT_TOKEN_BUDGET)


@router.get("/actions", response_model=list[CopilotActionDescriptor])
def copilot_actions():
    return [CopilotActionDescriptor(**item) for item in list_actions(phase=1)]


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
