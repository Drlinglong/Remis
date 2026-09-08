"""Developer-only HTTP boundary for archive A/B human spot checks."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from scripts.core.feature_policy import archive_ab_review_enabled
from scripts.developer_tools import archive_ab_review_adapter as adapter
from scripts.schemas.archive_ab_review import ArchiveABReviewRequest


router = APIRouter(prefix="/api/archive-ab-review", tags=["Developer Archive A/B Review"])


def _require_enabled() -> None:
    if not archive_ab_review_enabled():
        raise HTTPException(
            status_code=404,
            detail="Archive A/B human review is unavailable outside the Agent Preview developer build.",
        )


@router.get("/status")
def get_status() -> dict[str, object]:
    enabled = archive_ab_review_enabled()
    return {
        "enabled": enabled,
        "reason": None if enabled else "Agent Preview build and REMIS_ENABLE_ARCHIVE_AB_REVIEW are required.",
    }


@router.get("/cases")
def get_cases(
    manifest_id: str | None = None,
    dataset_id: str | None = None,
    case_kind: str | None = Query(default=None, pattern="^(event_chain|reference_batch)$"),
    chain_id: str | None = None,
    reference_batch_id: str | None = None,
    status: str = Query(default="all", pattern="^(all|reviewed|unreviewed)$"),
) -> dict[str, object]:
    _require_enabled()
    try:
        return adapter.load_cases(
            manifest_id=manifest_id,
            dataset_id=dataset_id,
            case_kind=case_kind,
            chain_id=chain_id,
            reference_batch_id=reference_batch_id,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reviews")
def post_review(request: ArchiveABReviewRequest) -> dict[str, object]:
    _require_enabled()
    try:
        reviewed = adapter.submit_review(
            manifest_id=request.manifest_id,
            case_id=request.case_id,
            selection=request.selection,
            error_tags=request.error_tags,
            confidence=request.confidence,
            note=request.note or "",
            reviewer=os.getenv("USERNAME") or os.getenv("USER") or "local-developer",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"case": reviewed, "history": adapter.review_history(
        manifest_id=request.manifest_id, case_id=request.case_id,
    )}


@router.get("/reviews")
def get_review_history(manifest_id: str | None = None, case_id: str | None = None) -> dict[str, object]:
    _require_enabled()
    return {"records": adapter.review_history(manifest_id=manifest_id, case_id=case_id)}


@router.get("/summary")
def get_review_summary(manifest_id: str | None = None) -> dict[str, object]:
    _require_enabled()
    return adapter.review_summary(manifest_id=manifest_id)


__all__ = ["router"]
