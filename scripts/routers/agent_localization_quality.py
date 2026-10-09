"""Advanced glossary coverage and sparse review APIs, no added user GUI."""
from fastapi import APIRouter, BackgroundTasks, Depends, Query

from scripts.core.localization_review_service import LocalizationReviewService
from scripts.core.terminology_coverage_service import TerminologyCoverageService
from scripts.schemas.localization_quality import (
    CoverageCandidateImportRequest, CoverageScanRequest, LocalizationReviewPlanRequest, ReviewStartRequest, ReviewResponseReconcileRequest,
)
from scripts.schemas.agent_batch import BatchReconcileRequest
from .agent_batch import get_batch_service, operation
from .agent_glossary_terminology import get_terminology_service

from .advanced_agent_policy import require_advanced_route

router = APIRouter(dependencies=[Depends(require_advanced_route)], prefix="/api/agent", tags=["Agent localization quality (experimental)"])


def review_service(batch=Depends(get_batch_service)):
    return LocalizationReviewService(batch)


def coverage_service(batch=Depends(get_batch_service), glossary=Depends(get_terminology_service)):
    return TerminologyCoverageService(batch, glossary)


@router.post("/terminology-coverage/scans")
async def scan(request: CoverageScanRequest, service=Depends(coverage_service)):
    return await operation(service.scan, request)


@router.get("/terminology-coverage/scans")
async def list_scans(project_id: str | None = None, limit: int = Query(50, ge=1, le=100),
                     offset: int = Query(0, ge=0), service=Depends(coverage_service)):
    rows = service.batch.repository.list_jobs(project_id, limit, offset, kind="coverage")
    return {"scans": rows, "limit": limit, "offset": offset}


@router.get("/terminology-coverage/scans/{scan_id}")
async def read_scan(scan_id: str, service=Depends(coverage_service)):
    return await operation(service.get, scan_id)


@router.get("/terminology-coverage/scans/{scan_id}/artifacts/{kind}")
async def coverage_artifact(scan_id: str, kind: str, service=Depends(coverage_service)):
    return await operation(service.artifact, scan_id, kind)


@router.post("/terminology-coverage/scans/{scan_id}/candidates")
async def import_candidates(scan_id: str, request: CoverageCandidateImportRequest, service=Depends(coverage_service)):
    from scripts.core.neologism_manager import neologism_manager
    return await operation(service.import_candidates, scan_id, request, neologism_manager)


@router.post("/localization-reviews/plan")
async def plan(request: LocalizationReviewPlanRequest, service=Depends(review_service)):
    return await operation(service.plan, request)


@router.post("/localization-reviews")
async def start(request: ReviewStartRequest, background: BackgroundTasks, service=Depends(review_service)):
    result = await operation(service.start, request)
    if result.pop("dispatch_review", False):
        from scripts.core.localization_review_runner import LocalizationReviewRunner
        background.add_task(LocalizationReviewRunner(service).run, result["id"])
    return result


@router.get("/localization-reviews/{job_id}")
async def read_review(job_id: str, service=Depends(review_service)):
    return await operation(service.get, job_id)


@router.get("/localization-reviews")
async def list_reviews(project_id: str | None = None, limit: int = Query(50, ge=1, le=100),
                       offset: int = Query(0, ge=0), service=Depends(review_service)):
    rows = service.batch.repository.list_jobs(project_id, limit, offset, kind="review_job")
    return {"jobs": [service.get(row["id"]) for row in rows], "limit": limit, "offset": offset}


@router.get("/localization-reviews/{job_id}/artifacts/{kind}")
async def artifact(job_id: str, kind: str, service=Depends(review_service)):
    return await operation(service.artifact, job_id, kind)


@router.post("/localization-reviews/{job_id}/refresh")
async def refresh(job_id: str, service=Depends(review_service)):
    return await operation(service.refresh, job_id)


@router.post("/localization-reviews/{job_id}/reconcile")
async def reconcile(job_id: str, request: BatchReconcileRequest, service=Depends(review_service)):
    return await operation(service.reconcile, job_id, request)


@router.post("/localization-reviews/{job_id}/responses/reconcile")
async def reconcile_response(job_id: str, request: ReviewResponseReconcileRequest, service=Depends(review_service)):
    return await operation(service.reconcile_response, job_id, request)
