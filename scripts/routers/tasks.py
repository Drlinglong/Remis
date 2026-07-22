from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from scripts.core.agent_service import agent_registry
from scripts.schemas.tasks import TaskCheckpoint, TaskCreator, TaskDetail, TaskEvent, TaskResult, TaskSummary, TaskSummaryList
from scripts.shared import task_state


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

ACTIVE_STATUSES = {"queued", "running", "awaiting_approval"}
ATTENTION_STATUSES = {"awaiting_approval", "failed", "interrupted"}
BLOCKING_KINDS = {
    "initial_translation",
    "translation",
    "incremental_translation",
    "agent_workshop",
    "repair",
    "neologism_mining",
}
TERMINAL_STATUS_MAP = {
    "completed": "completed",
    "complete": "completed",
    "success": "completed",
    "failed": "failed",
    "partial_failed": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "interrupted": "interrupted",
}
ROUTE_BY_KIND = {
    "initial_translation": "/translation",
    "translation": "/translation",
    "incremental_translation": "/incremental-translation",
    "agent_workshop": "/agent-workshop",
    "repair": "/agent-workshop",
    "neologism_mining": "/neologism-review",
    "dry_run": "/project-management",
}
TITLE_BY_KIND = {
    "initial_translation": "Initial translation",
    "translation": "Translation",
    "incremental_translation": "Incremental translation",
    "agent_workshop": "Agent Workshop",
    "repair": "Agent repair",
    "neologism_mining": "Neologism mining",
    "dry_run": "Agent dry run",
}


def _status(raw_status: Optional[str]) -> str:
    value = str(raw_status or "unknown").lower()
    if value in TERMINAL_STATUS_MAP:
        return TERMINAL_STATUS_MAP[value]
    if value in {"pending", "starting", "queued"}:
        return "queued"
    if value in {"running", "processing", "in_progress"}:
        return "running"
    if value in {"awaiting_approval", "waiting_approval"}:
        return "awaiting_approval"
    return "unknown"


def _progress(task: Dict[str, Any]) -> int:
    progress = task.get("progress") or {}
    percent = progress.get("percent")
    if percent is None:
        total = int(progress.get("total") or 0)
        current = int(progress.get("current") or 0)
        percent = int((current / total) * 100) if total else 0
    return max(0, min(100, int(percent or 0)))


def _allowed_actions(status: str, archived_at: Optional[str] = None) -> list[str]:
    if archived_at:
        return ["view_task", "restore_task"]
    if status in ACTIVE_STATUSES:
        return ["view_task"]
    if status in {"failed", "interrupted"}:
        return ["view_task", "retry", "archive_task"]
    if status == "completed":
        return ["view_task", "archive_task"]
    if status == "cancelled":
        return ["view_task", "archive_task"]
    return []


def _from_live_task(task: Dict[str, Any], agent_job: Optional[Dict[str, Any]]) -> TaskSummary:
    kind = str(
        task.get("kind")
        or task.get("task_kind")
        or task.get("agent_job_kind")
        or (agent_job or {}).get("kind")
        or "task"
    )
    status = _status(task.get("status"))
    progress = task.get("progress") or {}
    project_id = task.get("project_id") or (task.get("summary") or {}).get("project_id") or (agent_job or {}).get("project_id")
    creator = task.get("created_by") or ({"type": "remis_agent", "label": "Remis Agent"} if agent_job else {"type": "user"})
    checkpoint = task.get("checkpoint") or {}
    result = task.get("result") or {}
    if not result and (task.get("output_dirs") or task.get("result_path")):
        output_paths = [str(path) for path in task.get("output_dirs") or [] if path]
        if task.get("result_path") and str(task["result_path"]) not in output_paths:
            output_paths.append(str(task["result_path"]))
        result = {"types": ["files"], "output_paths": output_paths}
    if not result and task.get("results") is not None:
        result = {
            "types": ["change_summary"],
            "summary": f"{len(task.get('results') or [])} change(s) recorded",
        }
    if not result and kind == "neologism_mining" and task.get("summary"):
        summary = task.get("summary") or {}
        result = {
            "types": ["glossary_entries"],
            "summary": f"{int(summary.get('new_terms') or 0)} new term(s)",
        }
    return TaskSummary(
        task_id=str(task.get("task_id") or (agent_job or {}).get("job_id")),
        kind=kind,
        project_id=project_id,
        parent_task_id=task.get("parent_task_id"),
        created_by=TaskCreator.model_validate(creator),
        title=str(task.get("title") or TITLE_BY_KIND.get(kind, "Background task")),
        status=status,
        stage=str(progress.get("stage") or task.get("stage") or ""),
        progress=_progress(task),
        created_at=task.get("created_at") or (agent_job or {}).get("created_at"),
        started_at=task.get("started_at"),
        updated_at=task.get("updated_at") or (agent_job or {}).get("updated_at"),
        finished_at=task.get("finished_at"),
        archived_at=task.get("archived_at"),
        message=task.get("message"),
        attention_reason=task.get("attention_reason") or (task.get("message") if status in ATTENTION_STATUSES else None),
        checkpoint=TaskCheckpoint.model_validate(checkpoint),
        result=TaskResult.model_validate(result),
        blocking=bool(task.get("blocking", status in ACTIVE_STATUSES and kind in BLOCKING_KINDS)),
        dedupe_key=task.get("dedupe_key"),
        idempotency_key=task.get("idempotency_key"),
        source_route=str(task.get("source_route") or ROUTE_BY_KIND.get(kind, "/")),
        allowed_actions=_allowed_actions(status, task.get("archived_at")),
    )


def _from_persisted_agent_job(job: Dict[str, Any]) -> TaskSummary:
    snapshot = job.get("last_snapshot") or {}
    snapshot = {**snapshot, "task_id": job.get("job_id")}
    return _from_live_task(snapshot, job)


def _collect_task_summaries(*, include_archived: bool = False) -> list[TaskSummary]:
    jobs = {str(job.get("job_id")): job for job in agent_registry.list_jobs() if job.get("job_id")}
    summaries: list[TaskSummary] = []
    seen = set()

    for task in task_state.list_tasks():
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        summary = _from_live_task(task, jobs.get(task_id))
        if include_archived or not summary.archived_at:
            summaries.append(summary)
        seen.add(task_id)

    for job_id, job in jobs.items():
        if job_id not in seen:
            summary = _from_persisted_agent_job(job)
            if include_archived or not summary.archived_at:
                summaries.append(summary)

    summaries.sort(key=lambda item: item.updated_at or item.created_at or "", reverse=True)
    return summaries


@router.get("", response_model=TaskSummaryList)
async def list_task_summaries(
    active_only: Annotated[bool, Query()] = False,
    include_archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    summaries = _collect_task_summaries(include_archived=include_archived)
    active_count = sum(item.status in ACTIVE_STATUSES for item in summaries)
    attention_count = sum(item.status in ATTENTION_STATUSES for item in summaries)
    if active_only:
        summaries = [item for item in summaries if item.status in ACTIVE_STATUSES or item.status in ATTENTION_STATUSES]
    summaries = summaries[:limit]
    return TaskSummaryList(
        tasks=summaries,
        active_count=active_count,
        attention_count=attention_count,
    )


def _raw_task_and_job(task_id: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    task = task_state.get_task(task_id)
    job = agent_registry.get_job(task_id)
    if task is None and job is not None:
        snapshot = job.get("last_snapshot") or {}
        task = {**snapshot, "task_id": task_id}
    return task, job


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task_detail(task_id: str):
    task, job = _raw_task_and_job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    summary = _from_live_task(task, job)
    events = task_state.get_task_events(task_id)
    if not events:
        events = [
            {
                "event_id": f"legacy-{index}",
                "task_id": task_id,
                "sequence": index + 1,
                "timestamp": None,
                "level": "error" if summary.status in {"failed", "interrupted"} else "info",
                "event_type": "legacy_log",
                "message": message,
                "metadata": {},
            }
            for index, message in enumerate(task.get("log") or [])
        ]
    children = [
        item
        for item in _collect_task_summaries(include_archived=True)
        if item.parent_task_id == task_id
    ]
    return TaskDetail(
        **summary.model_dump(),
        events=[TaskEvent.model_validate(event) for event in events],
        children=children,
    )


@router.post("/{task_id}/archive")
async def archive_task(task_id: str):
    task, job = _raw_task_and_job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    status = _status(task.get("status"))
    if status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Active tasks cannot be archived")
    archived_at = task_state.utc_now_iso()
    if task_state.get_task(task_id) is not None:
        updated = task_state.update_task(
            task_id,
            fields={"archived_at": archived_at},
            append_log="Task archived from the task center.",
        )
    else:
        updated = {**task, "archived_at": archived_at, "updated_at": archived_at}
    if job is not None:
        agent_registry.update_snapshot(task_id, updated)
    return {"task_id": task_id, "archived_at": archived_at}


@router.post("/{task_id}/restore")
async def restore_task(task_id: str):
    task, job = _raw_task_and_job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task_state.get_task(task_id) is not None:
        updated = task_state.update_task(
            task_id,
            fields={"archived_at": None},
            append_log="Task restored to the task center.",
        )
    else:
        updated = {**task, "archived_at": None, "updated_at": task_state.utc_now_iso()}
    if job is not None:
        agent_registry.update_snapshot(task_id, updated)
    return {"task_id": task_id, "archived_at": None}
