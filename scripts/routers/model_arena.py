"""HTTP API for the Remis model arena."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from scripts import app_settings
from scripts.schemas.model_arena import (
    CreateModelArenaRunRequest,
    ModelArenaVoteRequest,
    StartModelArenaRunRequest,
)
from scripts.shared import task_state
from scripts.shared.services import model_arena_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/model-arena", tags=["Model Arena"])


class ModelArenaExportRequest(BaseModel):
    approved: bool
    mode: Literal["evidence", "summary-only"] = "evidence"


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    return HTTPException(status_code=409, detail=str(exc))


def _run_arena_task(run_id: str, task_id: str, retry: bool = False) -> None:
    try:
        task_state.update_task(
            task_id,
            status="running",
            append_log="Model arena execution started.",
            progress={"stage": "Running models serially", "current": 0, "percent": 5},
        )
        result = (
            model_arena_service.execute_retry(run_id)
            if retry
            else model_arena_service.execute_run(run_id)
        )
        run_status = result["status"]
        if run_status == "failed":
            task_status = "failed"
            message = "Every arena contestant failed. Review the run before retrying."
        elif run_status == "partial_failed":
            task_status = "partial_failed"
            message = "Arena execution finished with one or more failed contestants."
        else:
            task_status = "completed"
            message = "Arena translations are ready for anonymous judging."
        task_state.update_task(
            task_id,
            status=task_status,
            append_log=message,
            progress={
                "stage": "Ready for judging" if run_status != "failed" else "Failed",
                "current": 1,
                "total": 1,
                "percent": 100,
            },
            summary={"run_id": run_id, "arena_status": run_status},
        )
    except Exception as exc:
        logger.exception("Model arena task %s failed", task_id)
        try:
            model_arena_service.repository.update_run(run_id, status="failed")
            model_arena_service.repository.append_event(
                run_id,
                {
                    "event_type": "execution_crashed",
                    "level": "error",
                    "failure_code": "arena_internal_error",
                },
            )
        except Exception:
            logger.exception("Failed to persist model arena crash state")
        task_state.update_task(
            task_id,
            status="failed",
            append_log=f"Model arena execution failed: {type(exc).__name__}",
            progress={"stage": "Failed", "percent": 100},
        )


@router.post("/runs", status_code=201)
async def create_model_arena_run(request: CreateModelArenaRunRequest):
    try:
        return await model_arena_service.create_run(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/resample")
async def resample_model_arena_run(run_id: str):
    try:
        return await model_arena_service.resample(run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/start")
def start_model_arena_run(
    run_id: str,
    request: StartModelArenaRunRequest,
    background_tasks: BackgroundTasks,
):
    if not request.confirmed_model_calls:
        raise HTTPException(
            status_code=409,
            detail="Explicit confirmation is required before model calls.",
        )
    task_id = str(uuid.uuid4())
    try:
        prepared = model_arena_service.prepare_start(
            run_id,
            idempotency_key=request.idempotency_key,
            task_id=task_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    if prepared.get("idempotent_replay"):
        return prepared

    task_state.create_task(
        task_id,
        status="queued",
        log_message="Model arena queued after explicit model-call confirmation.",
        fields={
            "kind": "model_arena",
            "title": "Run model arena",
            "source_route": f"/model-arena?run={run_id}",
            "created_by": {"type": "user"},
            "blocking": False,
            "idempotency_key": f"model_arena:{run_id}:{request.idempotency_key}",
            "run_id": run_id,
        },
        dedupe_key=f"model_arena:{run_id}",
        reject_duplicate=True,
    )
    task_state.init_progress(
        task_id,
        {"total": 1, "current": 0, "percent": 0, "stage": "Queued"},
    )
    background_tasks.add_task(_run_arena_task, run_id, task_id)
    return prepared


@router.post("/runs/{run_id}/retry-failures")
def retry_model_arena_failures(
    run_id: str,
    request: StartModelArenaRunRequest,
    background_tasks: BackgroundTasks,
):
    if not request.confirmed_model_calls:
        raise HTTPException(
            status_code=409,
            detail="Explicit confirmation is required before retrying model calls.",
        )
    task_id = str(uuid.uuid4())
    try:
        prepared = model_arena_service.prepare_retry(
            run_id,
            idempotency_key=request.idempotency_key,
            task_id=task_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    if prepared.get("idempotent_replay"):
        return prepared

    task_state.create_task(
        task_id,
        status="queued",
        log_message="Failed arena contestants queued for an explicitly approved retry.",
        fields={
            "kind": "model_arena_retry",
            "title": "Retry failed arena models",
            "source_route": f"/model-arena?run={run_id}",
            "created_by": {"type": "user"},
            "blocking": False,
            "idempotency_key": (
                f"model_arena_retry:{run_id}:{request.idempotency_key}"
            ),
            "run_id": run_id,
        },
        dedupe_key=f"model_arena:{run_id}",
        reject_duplicate=True,
    )
    task_state.init_progress(
        task_id,
        {"total": 1, "current": 0, "percent": 0, "stage": "Queued"},
    )
    background_tasks.add_task(_run_arena_task, run_id, task_id, True)
    return prepared


@router.get("/runs/{run_id}")
def get_model_arena_run(run_id: str):
    try:
        return model_arena_service.get_run(run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/runs/{run_id}/samples/{sample_id}/vote")
def vote_model_arena_sample(
    run_id: str, sample_id: str, request: ModelArenaVoteRequest
):
    try:
        return model_arena_service.save_vote(run_id, sample_id, request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/complete")
def complete_model_arena_run(run_id: str):
    try:
        return model_arena_service.complete_run(run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/runs")
def list_model_arena_runs(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    source_lang_code: Optional[str] = None,
    target_lang_code: Optional[str] = None,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    statuses = [item.strip() for item in status.split(",") if item.strip()] if status else None
    return model_arena_service.list_runs(
        project_id=project_id,
        statuses=statuses,
        source_lang_code=source_lang_code,
        target_lang_code=target_lang_code,
        provider_id=provider_id,
        model_id=model_id,
        offset=offset,
        limit=limit,
    )


@router.get("/runs/{run_id}/export-preview")
def preview_model_arena_export(
    run_id: str,
    mode: Literal["evidence", "summary-only"] = "evidence",
):
    try:
        return model_arena_service.export_preview(run_id, mode=mode)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/export")
def export_model_arena_run(run_id: str, request: ModelArenaExportRequest):
    if not request.approved:
        raise HTTPException(
            status_code=409,
            detail="Export requires explicit approval after preview.",
        )
    try:
        artifact = model_arena_service.export_preview(run_id, mode=request.mode)
    except Exception as exc:
        raise _http_error(exc) from exc
    content = json.dumps(artifact, ensure_ascii=False, indent=2)
    export_dir = Path(app_settings.OUTPUT_DIR) / "model_arena_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"remis-model-arena-{run_id}.json"
    export_path = export_dir / filename
    export_path.write_text(content, encoding="utf-8")
    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=filename,
        headers={
            "X-Remis-Export-Path": quote(str(export_path)),
        },
    )


@router.delete("/runs/{run_id}", status_code=204)
def delete_model_arena_run(
    run_id: str,
    confirmed: bool = Query(default=False),
):
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Deleting arena history requires explicit confirmation.",
        )
    if not model_arena_service.delete_run(run_id):
        raise HTTPException(status_code=404, detail="Model arena run not found")
    return Response(status_code=204)
