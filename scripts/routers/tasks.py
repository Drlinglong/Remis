from datetime import datetime, timezone
import re
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from scripts.core.agent_service import agent_registry
from scripts.schemas.tasks import TaskCheckpoint, TaskChildAggregate, TaskCreator, TaskDetail, TaskEvent, TaskProjectContext, TaskResult, TaskSummary, TaskSummaryList
from scripts.shared import task_state
from scripts.shared.services import project_manager


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

ACTIVE_STATUSES = {"queued", "running", "awaiting_approval"}
ATTENTION_STATUSES = {"awaiting_approval", "failed", "interrupted"}
RAW_STATUS_BY_NORMALIZED = {
    "queued": {"pending", "starting", "queued"},
    "running": {"running", "processing", "in_progress"},
    "awaiting_approval": {"awaiting_approval", "waiting_approval"},
    "completed": {"completed", "complete", "success"},
    "failed": {"failed", "partial_failed"},
    "cancelled": {"cancelled", "canceled"},
    "interrupted": {"interrupted"},
    "unknown": {"unknown"},
}
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
    "agent_workshop": "Format Repair",
    "agent_workshop_batch": "Format Repair batch",
    "repair": "Format repair",
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
        # Remis workflows have different retry inputs and approval boundaries.
        # Route users back to the owning workflow instead of advertising a
        # generic restart or cancellation operation that cannot be honored.
        return ["view_task", "return_to_workflow", "archive_task"]
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
    blocking = status in ACTIVE_STATUSES and bool(task.get("blocking", kind in BLOCKING_KINDS))
    return TaskSummary(
        task_id=str(task.get("task_id") or (agent_job or {}).get("job_id")),
        kind=kind,
        project_id=project_id,
        project_context=(TaskProjectContext.model_validate(task["project_context"]) if task.get("project_context") else None),
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
        blocking=blocking,
        blocking_reason=(
            task.get("blocking_reason")
            or (
                "This task is changing project files. Conflicting writes are blocked until it finishes."
                if blocking
                else None
            )
        ),
        dedupe_key=task.get("dedupe_key"),
        idempotency_key=task.get("idempotency_key"),
        source_route=str(task.get("source_route") or ROUTE_BY_KIND.get(kind, "/")),
        workflow_context=dict(task.get("workflow_context") or {}),
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

    repository = task_state.get_repository()
    persisted_tasks = (
        repository.list_tasks(include_events=False)
        if repository is not None
        else []
    )
    tasks_by_id = {
        str(task.get("task_id")): task
        for task in persisted_tasks
        if task.get("task_id")
    }
    for task in task_state.list_tasks():
        task_id = str(task.get("task_id") or "")
        persisted = tasks_by_id.get(task_id)
        if task_id and (
            persisted is None
            or str(task.get("updated_at") or "") >= str(persisted.get("updated_at") or "")
        ):
            tasks_by_id[task_id] = task
    for task in tasks_by_id.values():
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


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _persisted_task_page(
    *,
    jobs: Dict[str, Dict[str, Any]],
    include_archived: bool,
    active_only: bool,
    status: Optional[str],
    kind: Optional[str],
    from_time: Optional[datetime],
    to_time: Optional[datetime],
    offset: int,
    limit: int,
) -> Optional[TaskSummaryList]:
    repository = task_state.get_repository()
    if repository is None:
        return None

    # Registry-only legacy jobs still need the compatibility merge below.
    for job_id in jobs:
        if task_state.get_task(job_id) is None:
            return None

    normalized_statuses: Optional[set[str]] = None
    if active_only:
        normalized_statuses = ACTIVE_STATUSES | ATTENTION_STATUSES
    if status:
        normalized_statuses = {status}
    raw_statuses = (
        {
            raw_status
            for normalized in normalized_statuses
            for raw_status in RAW_STATUS_BY_NORMALIZED.get(normalized, {normalized})
        }
        if normalized_statuses is not None
        else None
    )
    page = repository.query_task_page(
        include_archived=include_archived,
        statuses=raw_statuses,
        kind=kind,
        from_time=_iso_utc(from_time),
        to_time=_iso_utc(to_time),
        offset=offset,
        limit=limit,
    )
    summaries = [
        _from_live_task(task, jobs.get(str(task.get("task_id") or "")))
        for task in page["tasks"]
    ]
    return TaskSummaryList(
        tasks=summaries,
        active_count=page["active_count"],
        attention_count=page["attention_count"],
        total_count=page["total_count"],
    )


async def _enrich_project_context(summaries: list[TaskSummary]) -> None:
    unresolved_ids = {
        item.project_id
        for item in summaries
        if item.project_id and item.project_context is None
    }
    if not unresolved_ids:
        return
    try:
        projects = await project_manager.get_projects()
    except Exception:
        return
    projects_by_id = {
        str(project.get("project_id")): project
        for project in projects
        if project.get("project_id")
    }
    for item in summaries:
        project = projects_by_id.get(str(item.project_id))
        if project and project.get("name"):
            item.project_context = TaskProjectContext(
                name=str(project["name"]),
                game_id=project.get("game_id"),
            )


def _parse_task_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _task_matches_glossary(summary: TaskSummary, glossary_id: int) -> bool:
    metadata = summary.result.metadata or {}
    report = metadata.get("preview") if isinstance(metadata.get("preview"), dict) else metadata
    glossary_ids = report.get("glossary_ids") if isinstance(report, dict) else []
    return glossary_id in {
        int(item)
        for item in (glossary_ids or [])
        if str(item).isdigit()
    }


@router.get("", response_model=TaskSummaryList)
async def list_task_summaries(
    active_only: Annotated[bool, Query()] = False,
    include_archived: Annotated[bool, Query()] = False,
    status: Annotated[Optional[str], Query()] = None,
    kind: Annotated[Optional[str], Query()] = None,
    glossary_id: Annotated[Optional[int], Query(ge=1)] = None,
    from_time: Annotated[Optional[datetime], Query()] = None,
    to_time: Annotated[Optional[datetime], Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    normalized_status = _status(status) if status else None
    jobs = {
        str(job.get("job_id")): job
        for job in agent_registry.list_jobs()
        if job.get("job_id")
    }
    if glossary_id is None:
        persisted_page = _persisted_task_page(
            jobs=jobs,
            include_archived=include_archived,
            active_only=active_only,
            status=normalized_status,
            kind=kind,
            from_time=from_time,
            to_time=to_time,
            offset=offset,
            limit=limit,
        )
        if persisted_page is not None:
            await _enrich_project_context(persisted_page.tasks)
            return persisted_page

    summaries = _collect_task_summaries(include_archived=include_archived)
    await _enrich_project_context(summaries)
    active_count = sum(item.status in ACTIVE_STATUSES for item in summaries)
    attention_count = sum(item.status in ATTENTION_STATUSES for item in summaries)
    if active_only:
        summaries = [item for item in summaries if item.status in ACTIVE_STATUSES or item.status in ATTENTION_STATUSES]
    if normalized_status:
        summaries = [item for item in summaries if item.status == normalized_status]
    if kind:
        summaries = [item for item in summaries if item.kind == kind]
    if glossary_id is not None:
        summaries = [item for item in summaries if _task_matches_glossary(item, glossary_id)]
    normalized_from = _parse_task_time(from_time.isoformat()) if from_time else None
    normalized_to = _parse_task_time(to_time.isoformat()) if to_time else None
    if normalized_from or normalized_to:
        summaries = [
            item
            for item in summaries
            if (
                (task_time := _parse_task_time(item.created_at or item.started_at)) is not None
                and (normalized_from is None or task_time >= normalized_from)
                and (normalized_to is None or task_time < normalized_to)
            )
        ]
        summaries.sort(key=lambda item: item.created_at or item.started_at or "", reverse=True)
    total_count = len(summaries)
    summaries = summaries[offset:offset + limit]
    return TaskSummaryList(
        tasks=summaries,
        active_count=active_count,
        attention_count=attention_count,
        total_count=total_count,
    )


def _raw_task_and_job(task_id: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    task = task_state.get_task(task_id)
    job = agent_registry.get_job(task_id)
    if task is None and job is not None:
        snapshot = job.get("last_snapshot") or {}
        task = {**snapshot, "task_id": task_id}
    return task, job


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task_detail(
    task_id: str,
    include_diagnostics: Annotated[bool, Query()] = False,
):
    task, job = _raw_task_and_job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    summary = _from_live_task(task, job)
    await _enrich_project_context([summary])
    events = task_state.get_task_events(
        task_id,
        include_diagnostics=include_diagnostics,
    )
    if not events:
        events = [
            {
                "event_id": f"legacy-{index}",
                "task_id": task_id,
                "sequence": index + 1,
                "timestamp": None,
                "level": "error" if summary.status in {"failed", "interrupted"} else "info",
                "event_type": "legacy_log",
                "audience": "user",
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
    child_aggregate = TaskChildAggregate(
        total=len(children),
        active=sum(item.status in ACTIVE_STATUSES for item in children),
        attention=sum(item.status in ATTENTION_STATUSES for item in children),
        completed=sum(item.status == "completed" for item in children),
        progress=(
            round(sum(item.progress for item in children) / len(children))
            if children
            else 0
        ),
    )
    return TaskDetail(
        **summary.model_dump(),
        events=[TaskEvent.model_validate(event) for event in events],
        children=children,
        child_aggregate=child_aggregate,
    )


@router.get("/{task_id}/events/export", response_class=PlainTextResponse)
async def export_task_events(
    task_id: str,
    include_diagnostics: Annotated[bool, Query()] = False,
):
    task, _job = _raw_task_and_job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    events = task_state.get_task_events(
        task_id,
        limit=5000,
        include_diagnostics=include_diagnostics,
    )
    lines = [
        "# Remis task event export",
        f"# Task ID: {task_id}",
        f"# Diagnostics included: {'yes' if include_diagnostics else 'no'}",
        "",
    ]
    lines.extend(
        (
            f"[{event.get('timestamp') or '--'}] "
            f"[{event.get('level', 'info')}] "
            f"[{event.get('audience', 'user')}] "
            f"[{event.get('event_type', 'log')}] "
            f"{event.get('message', '')}"
        )
        for event in events
    )
    safe_task_id = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._") or "task"
    return PlainTextResponse(
        "\n".join(lines),
        headers={
            "Content-Disposition": (
                f'attachment; filename="remis-task-{safe_task_id}-events.txt"'
            ),
        },
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
