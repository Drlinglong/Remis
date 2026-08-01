"""Normal-user routes for editing and publishing immutable Context Releases."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.repositories.context_override_repository import (
    ContextDraftClosedError,
    ContextDraftNotFoundError,
    ContextKeyNotFoundError,
    ContextOwnershipError,
    ContextOverrideRepository,
    ContextOverrideValidationError,
    ContextReleaseNotFoundError,
)
from scripts.core.services.context_override_service import ContextOverrideService
from scripts.schemas.context import ContextDraft, ContextRelease
from scripts.schemas.context_override import (
    SaveContextOverrideRequest,
    StartContextDraftBody,
    StartContextDraftRequest,
)


router = APIRouter(prefix="/api/context", tags=["context"])
context_override_service = ContextOverrideService(
    ContextOverrideRepository(PROJECTS_DB_PATH)
)


def _context_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": False},
    )


def _map_context_error(error: Exception) -> HTTPException:
    if isinstance(error, ContextReleaseNotFoundError):
        return _context_error(404, "context_release_not_found", str(error))
    if isinstance(error, ContextDraftNotFoundError):
        return _context_error(404, "context_draft_not_found", str(error))
    if isinstance(error, ContextOwnershipError):
        return _context_error(404, "context_ownership_not_found", str(error))
    if isinstance(error, ContextKeyNotFoundError):
        return _context_error(422, "context_key_not_found", str(error))
    if isinstance(error, ContextOverrideValidationError):
        return _context_error(422, "context_override_invalid", str(error))
    if isinstance(error, ContextDraftClosedError):
        return _context_error(409, "context_draft_closed", str(error))
    return _context_error(400, "context_override_invalid", str(error))


def _parse_override_request(payload: Any) -> SaveContextOverrideRequest:
    try:
        return SaveContextOverrideRequest.model_validate(payload)
    except (TypeError, ValueError) as error:
        raise _context_error(
            422,
            "context_override_invalid",
            "Human override payload failed bounded validation",
        ) from error


@router.post(
    "/projects/{project_id}/drafts",
    response_model=ContextDraft,
    status_code=status.HTTP_201_CREATED,
)
def start_context_draft(project_id: str, request: StartContextDraftRequest):
    try:
        return context_override_service.start_draft(project_id, request.base_release_id)
    except Exception as error:
        raise _map_context_error(error) from error


@router.post(
    "/projects/{project_id}/releases/{release_id}/drafts",
    response_model=ContextDraft,
    status_code=status.HTTP_201_CREATED,
)
def start_context_draft_from_release(project_id: str, release_id: str):
    try:
        return context_override_service.start_draft(project_id, release_id)
    except Exception as error:
        raise _map_context_error(error) from error


@router.post(
    "/drafts",
    response_model=ContextDraft,
    status_code=status.HTTP_201_CREATED,
)
def start_context_draft_from_body(request: StartContextDraftBody):
    try:
        return context_override_service.start_draft(
            request.project_id, request.base_release_id
        )
    except Exception as error:
        raise _map_context_error(error) from error


@router.get(
    "/projects/{project_id}/drafts/{draft_id}",
    response_model=ContextDraft,
)
def get_context_draft(project_id: str, draft_id: str):
    try:
        return context_override_service.get_draft(project_id, draft_id)
    except Exception as error:
        raise _map_context_error(error) from error


@router.put(
    "/projects/{project_id}/drafts/{draft_id}/overrides",
    response_model=ContextDraft,
)
@router.post(
    "/projects/{project_id}/drafts/{draft_id}/overrides",
    response_model=ContextDraft,
)
def save_context_override(
    project_id: str,
    draft_id: str,
    payload: Any = Body(...),
):
    request = _parse_override_request(payload)
    try:
        return context_override_service.save_override(
            project_id,
            draft_id,
            request.context_key,
            request.value,
            request.note,
        )
    except Exception as error:
        raise _map_context_error(error) from error


@router.post(
    "/projects/{project_id}/drafts/{draft_id}/publish",
    response_model=ContextRelease,
)
def publish_context_override_draft(project_id: str, draft_id: str):
    try:
        return context_override_service.publish_draft(project_id, draft_id)
    except Exception as error:
        raise _map_context_error(error) from error
