"""Advanced-user Batch and terminology API; no GUI or automatic paid retries."""
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from scripts.core.agent_batch_service import AgentBatchService
from scripts.core.batch_artifacts import BatchArtifacts
from scripts.core.batch_project_guard import BatchProjectGuard
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.openrouter_batch_transport import OpenRouterBatchTransport
from scripts.core.openai_batch_transport import OpenAIBatchTransport
from scripts.schemas.agent_batch import (
    BatchApplyPlanRequest, BatchApplyRequest, BatchPlanRequest, BatchReconcileRequest,
    BatchRetryRequest, BatchStartRequest, TermReleaseRequest, TranslationTrialPlanRequest,
)

from .advanced_agent_policy import require_advanced_route

router = APIRouter(dependencies=[Depends(require_advanced_route)], prefix="/api/agent", tags=["Agent Batch (experimental)"])


@lru_cache(maxsize=1)
def get_batch_service():
    from scripts.app_settings import DEST_DIR, REMIS_DB_PATH, get_api_key, get_app_data_dir
    from scripts.core.repositories.task_repository import TaskRepository
    from scripts.shared.services import archive_manager, project_manager
    storage = Path(get_app_data_dir()) / "agent_batch"
    return AgentBatchService(BatchRepository(storage / "batch.sqlite"), BatchArtifacts(storage / "artifacts"),
        OpenRouterBatchTransport(lambda: get_api_key("openrouter", "OPENROUTER_API_KEY")),
        project_manager, archive_manager, Path(DEST_DIR) / "agent_batch",
        BatchProjectGuard(TaskRepository(REMIS_DB_PATH)),
        native_transport=OpenAIBatchTransport(lambda: get_api_key("openai", "OPENAI_API_KEY")))


async def operation(function, *args):
    try:
        import inspect
        result = function(*args)
        return await result if inspect.isawaitable(result) else result
    except BatchConflict as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc), "retryable": False}) from None


@router.post("/batch-jobs/plan")
async def plan(request: BatchPlanRequest, service=Depends(get_batch_service)):
    return await operation(service.plan, request)


@router.get("/batch-jobs/plans/{plan_id}")
async def read_plan(plan_id: str, service=Depends(get_batch_service)):
    return await operation(service.repository.get, plan_id, "plan")


@router.post("/batch-jobs")
async def submit(request: BatchStartRequest, background_tasks: BackgroundTasks, service=Depends(get_batch_service)):
    result = await operation(service.start, request)
    if result.pop("dispatch_immediate", False):
        from scripts.core.immediate_trial_service import ImmediateTrialService
        background_tasks.add_task(ImmediateTrialService(service).run, result["id"])
    return result


@router.post("/translation-trials/plan")
async def trial_plan(request: TranslationTrialPlanRequest, service=Depends(get_batch_service)):
    return await operation(service.plan, request)


@router.post("/translation-trials")
async def trial_start(request: BatchStartRequest, background_tasks: BackgroundTasks, service=Depends(get_batch_service)):
    persisted = await operation(service.repository.get, request.plan_id, "plan")
    if persisted.get("execution_mode") != "immediate":
        raise HTTPException(400, detail={"code": "execution_mode_conflict"})
    return await submit(request, background_tasks, service)


@router.get("/batch-jobs")
async def list_jobs(project_id: str | None = None, limit: int = Query(50, ge=1, le=100),
                    offset: int = Query(0, ge=0), service=Depends(get_batch_service)):
    rows = service.repository.list_jobs(project_id, limit, offset)
    return {"jobs": [service.get(row["id"]) for row in rows], "limit": limit, "offset": offset}


@router.get("/batch-jobs/{job_id}")
async def read_job(job_id: str, service=Depends(get_batch_service)):
    return await operation(service.get, job_id)


@router.post("/batch-jobs/{job_id}/refresh")
async def refresh(job_id: str, service=Depends(get_batch_service)):
    return await operation(service.refresh, job_id)


@router.post("/batch-jobs/{job_id}/collect")
async def collect(job_id: str, revalidate: bool = False, service=Depends(get_batch_service)):
    return await operation(service.collect, job_id, revalidate)


@router.post("/batch-jobs/{job_id}/retry/plan")
async def retry_plan(job_id: str, request: BatchRetryRequest, service=Depends(get_batch_service)):
    return await operation(service.retry_plan, job_id, request.custom_ids)


@router.post("/batch-jobs/{job_id}/reconcile")
async def reconcile(job_id: str, request: BatchReconcileRequest, service=Depends(get_batch_service)):
    return await operation(service.reconcile, job_id, request.remote_id, request.approved)


@router.post("/batch-jobs/{job_id}/apply/plan")
async def apply_plan(job_id: str, request: BatchApplyPlanRequest, service=Depends(get_batch_service)):
    return await operation(service.apply_plan, job_id, request.file_ids)


@router.post("/batch-jobs/{job_id}/apply")
async def apply(job_id: str, request: BatchApplyRequest, service=Depends(get_batch_service)):
    return await operation(service.apply, job_id, request.apply_plan_id, request.approved)


@router.get("/batch-jobs/{job_id}/artifacts/{artifact_kind}")
async def artifact(job_id: str, artifact_kind: str, service=Depends(get_batch_service)):
    job = await operation(service.repository.get, job_id, "job")
    plan = await operation(service.repository.get, job["plan_id"], "plan")
    refs = {"source": plan["source_artifact"], "requests": plan["requests_artifact"],
            "catalog": plan["model_catalog_artifact"], "remote": job.get("remote_artifact"),
            "collection": job.get("collection_artifact")}
    if not refs.get(artifact_kind):
        raise HTTPException(404, detail={"code": "artifact_unavailable"})
    return await operation(service.artifacts.get, refs[artifact_kind])


@router.post("/term-releases")
async def publish_terms(request: TermReleaseRequest, service=Depends(get_batch_service)):
    return await operation(service.terms.publish, request)


@router.get("/term-releases/{release_id}")
async def read_terms(release_id: str, service=Depends(get_batch_service)):
    record, terms = await operation(service.terms.get, release_id)
    return {**record, "terms": terms}
