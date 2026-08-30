"""HTTP contracts for reading and editing context archive tree v2 drafts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, status

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.repositories.context_tree_v2_repository import (
    ContextTreeV2ConflictError,
    ContextTreeV2DraftClosedError,
    ContextTreeV2NotFoundError,
    ContextTreeV2OwnershipError,
    ContextTreeV2Repository,
    ContextTreeV2ValidationError,
)
from scripts.schemas.context_tree_v2 import (
    PrePublicationValidationRequest,
    PrePublicationValidationResult,
    PublishTreeDraftRequest,
    ReadTreeResponse,
    TreeDraft,
    TreeDraftOverrideOperation,
)


router = APIRouter(prefix="/api/context/tree-v2", tags=["context-tree-v2"])
repository = ContextTreeV2Repository(PROJECTS_DB_PATH)


def _error(code: str, message: str, status_code: int, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": False, **extra},
    )


def _map_error(error: Exception, *, validation_status: int = 422) -> HTTPException:
    if isinstance(error, (ContextTreeV2NotFoundError, ContextTreeV2OwnershipError)):
        return _error("context_tree_v2_not_found", str(error), 404)
    if isinstance(error, ContextTreeV2DraftClosedError):
        return _error("context_tree_v2_draft_closed", str(error), 409)
    if isinstance(error, ContextTreeV2ConflictError):
        return _error("context_tree_v2_conflict", str(error), 409)
    if isinstance(error, ContextTreeV2ValidationError):
        return _error(
            "context_tree_v2_validation_failed",
            str(error),
            validation_status,
            issues=error.issues,
        )
    return _error("context_tree_v2_request_failed", str(error), validation_status)


@router.get(
    "/projects/{project_id}/trees/{tree_id}",
    response_model=ReadTreeResponse,
)
def read_context_tree_v2(
    project_id: str,
    tree_id: str,
    draft_id: str | None = Query(default=None),
):
    try:
        return repository.get_tree(project_id, tree_id, draft_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.get(
    "/projects/{project_id}/latest",
    response_model=ReadTreeResponse,
)
def read_latest_context_tree_v2(project_id: str):
    try:
        return repository.get_latest_tree(project_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.get(
    "/projects/{project_id}/latest-release",
    response_model=ReadTreeResponse,
)
def read_latest_context_tree_v2_release(project_id: str):
    try:
        return repository.get_latest_release_tree(project_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.get(
    "/projects/{project_id}/releases/{release_id}",
    response_model=ReadTreeResponse,
)
def read_context_tree_v2_release(project_id: str, release_id: str):
    try:
        return repository.get_release_tree(project_id, release_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.post(
    "/projects/{project_id}/trees/{tree_id}/drafts",
    response_model=TreeDraft,
    status_code=status.HTTP_201_CREATED,
)
def create_context_tree_v2_draft(project_id: str, tree_id: str):
    try:
        return repository.create_draft(project_id, tree_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.get(
    "/projects/{project_id}/drafts/{draft_id}",
    response_model=TreeDraft,
)
def get_context_tree_v2_draft(project_id: str, draft_id: str):
    try:
        return repository.get_draft(project_id, draft_id)
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.post(
    "/projects/{project_id}/drafts/{draft_id}/operations",
    response_model=TreeDraft,
)
@router.put(
    "/projects/{project_id}/drafts/{draft_id}/operations",
    response_model=TreeDraft,
)
@router.post(
    "/projects/{project_id}/drafts/{draft_id}/overrides",
    response_model=TreeDraft,
)
@router.put(
    "/projects/{project_id}/drafts/{draft_id}/overrides",
    response_model=TreeDraft,
)
def save_context_tree_v2_operation(
    project_id: str,
    draft_id: str,
    operation: TreeDraftOverrideOperation,
):
    try:
        return repository.save_draft_operation(project_id, draft_id, operation)
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/projects/{project_id}/drafts/{draft_id}/operations/batch",
    response_model=TreeDraft,
)
def save_context_tree_v2_operations(
    project_id: str,
    draft_id: str,
    operations: list[TreeDraftOverrideOperation],
):
    try:
        return repository.save_draft_overrides(project_id, draft_id, operations)
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/projects/{project_id}/drafts/{draft_id}/validate",
    response_model=PrePublicationValidationResult,
)
def validate_context_tree_v2_draft(
    project_id: str,
    draft_id: str,
    request: PrePublicationValidationRequest | None = Body(default=None),
):
    if request is not None and (
        request.project_id != project_id
        or request.draft_id != draft_id
    ):
        raise _error("context_tree_v2_request_mismatch", "Validation body does not match the route", 422)
    try:
        return repository.validate_draft(
            project_id,
            draft_id,
            reject_unresolved=True if request is None else request.reject_unresolved,
            include_warnings=True if request is None else request.include_warnings,
        )
    except Exception as error:
        raise _map_error(error, validation_status=400) from error


@router.post(
    "/projects/{project_id}/drafts/{draft_id}/publish",
    status_code=status.HTTP_201_CREATED,
)
def publish_context_tree_v2_draft(
    project_id: str,
    draft_id: str,
    request: PublishTreeDraftRequest | None = Body(default=None),
):
    try:
        return repository.publish_draft(
            project_id,
            draft_id,
            idempotency_key=request.idempotency_key if request else None,
        )
    except Exception as error:
        raise _map_error(error) from error


__all__ = ["repository", "router"]
