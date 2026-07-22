import logging
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from scripts.core.repositories.task_repository import TaskRepository
from scripts.shared.state import tasks
from scripts.shared.ws_manager import ws_manager

_LOCK = threading.RLock()
MAX_STORED_LOG_LINES = 1000
MAX_PAYLOAD_LOG_LINES = 100
ACTIVE_TASK_STATUSES = {"pending", "starting", "queued", "running", "processing", "awaiting_approval"}
TERMINAL_TASK_STATUSES = {"completed", "complete", "success", "failed", "partial_failed", "cancelled", "canceled", "interrupted"}
_repository: Optional[TaskRepository] = None


class DuplicateTaskError(RuntimeError):
    def __init__(self, existing_task: Dict[str, Any]):
        self.existing_task = deepcopy(existing_task)
        super().__init__(f"Task {existing_task.get('task_id')} already owns this operation")

DEFAULT_PROGRESS = {
    "total": 0,
    "current": 0,
    "percent": 0,
    "current_file": "",
    "stage": "Initializing",
    "total_batches": 0,
    "current_batch": 0,
    "successful_batches": 0,
    "failed_batches": 0,
    "error_count": 0,
    "glossary_issues": 0,
    "format_issues": 0,
    "format_repair": None,
    "workshop_progress": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    return _utc_now_iso()


def _merge_dict(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def _ensure_task(task_id: str) -> Dict[str, Any]:
    now = _utc_now_iso()
    task = tasks.setdefault(
        task_id,
        {
            "task_id": task_id,
            "status": "pending",
            "log": [],
            "created_at": now,
            "updated_at": now,
        },
    )
    task.setdefault("task_id", task_id)
    task.setdefault("created_at", now)
    task.setdefault("status", "pending")
    task.setdefault("log", [])
    return task


def _append_log(task: Dict[str, Any], message: Optional[str]) -> None:
    if not message:
        return
    task["log"].append(message)
    if len(task["log"]) > MAX_STORED_LOG_LINES:
        task["log"] = task["log"][-500:]


def configure_repository(
    repository: Optional[TaskRepository],
    *,
    hydrate: bool = False,
    replace: bool = False,
) -> None:
    """Attach the persistent ledger after database initialization."""
    global _repository
    with _LOCK:
        _repository = repository
        if not hydrate or repository is None:
            return
        persisted = repository.list_tasks()
        if replace:
            tasks.clear()
        for task in persisted:
            task_id = str(task.get("task_id") or "")
            if not task_id:
                continue
            current = tasks.get(task_id)
            if current is None or str(task.get("updated_at") or "") >= str(current.get("updated_at") or ""):
                tasks[task_id] = task


def get_repository() -> Optional[TaskRepository]:
    return _repository


def _event_level(status: Optional[str], message: Optional[str]) -> str:
    normalized = str(status or "").lower()
    lowered_message = str(message or "").lower()
    if normalized in {"failed", "partial_failed", "interrupted"} or "error" in lowered_message or "failed" in lowered_message:
        return "error"
    if normalized in {"completed", "complete", "success"}:
        return "success"
    if normalized in {"awaiting_approval"}:
        return "warning"
    return "info"


def _persist_task(
    task: Dict[str, Any],
    *,
    event_message: Optional[str] = None,
    event_type: str = "log",
) -> None:
    if _repository is None:
        return
    try:
        event = None
        if event_message:
            event = {
                "timestamp": task.get("updated_at") or _utc_now_iso(),
                "level": _event_level(task.get("status"), event_message),
                "event_type": event_type,
                "message": event_message,
            }
        _repository.save_task(task, event=event)
    except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
        logging.error("Failed to persist task %s: %s", task.get("task_id"), exc)


def create_task(
    task_id: str,
    *,
    status: str = "pending",
    log_message: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    reject_duplicate: bool = False,
) -> Dict[str, Any]:
    with _LOCK:
        if dedupe_key and reject_duplicate:
            for existing in tasks.values():
                if (
                    existing.get("dedupe_key") == dedupe_key
                    and str(existing.get("status") or "").lower() in ACTIVE_TASK_STATUSES
                ):
                    raise DuplicateTaskError(existing)
        now = _utc_now_iso()
        tasks[task_id] = {
            "task_id": task_id,
            "status": status,
            "log": [],
            "created_at": now,
            "updated_at": now,
        }
        if fields:
            _merge_dict(tasks[task_id], deepcopy(fields))
        if dedupe_key:
            tasks[task_id]["dedupe_key"] = dedupe_key
        _append_log(tasks[task_id], log_message)
        normalized_status = str(status or "").lower()
        if normalized_status in ACTIVE_TASK_STATUSES and normalized_status not in {"pending", "queued"}:
            tasks[task_id]["started_at"] = now
        if normalized_status in TERMINAL_TASK_STATUSES:
            tasks[task_id]["finished_at"] = now
        _persist_task(
            tasks[task_id],
            event_message=log_message,
            event_type="task_created",
        )
        return deepcopy(tasks[task_id])


def init_progress(task_id: str, progress: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _LOCK:
        task = _ensure_task(task_id)
        task["progress"] = deepcopy(DEFAULT_PROGRESS)
        if progress:
            _merge_dict(task["progress"], progress)
        task["updated_at"] = _utc_now_iso()
        _persist_task(task)
        return deepcopy(task["progress"])


def update_task(
    task_id: str,
    *,
    status: Optional[str] = None,
    message: Optional[str] = None,
    append_log: Optional[str] = None,
    progress: Optional[Dict[str, Any]] = None,
    summary: Optional[Dict[str, Any]] = None,
    fields: Optional[Dict[str, Any]] = None,
    result_path: Optional[str] = None,
    clear_result_path: bool = False,
    push: bool = True,
) -> Dict[str, Any]:
    with _LOCK:
        task = _ensure_task(task_id)
        if status is not None:
            task["status"] = status
        if message is not None:
            task["message"] = message
        if progress is not None:
            current_progress = task.setdefault("progress", deepcopy(DEFAULT_PROGRESS))
            _merge_dict(current_progress, progress)
        if summary is not None:
            current_summary = task.setdefault("summary", {})
            _merge_dict(current_summary, summary)
        if fields is not None:
            _merge_dict(task, fields)
        if clear_result_path:
            task.pop("result_path", None)
        elif result_path is not None:
            task["result_path"] = result_path
        now = _utc_now_iso()
        normalized_status = str(task.get("status") or "").lower()
        if normalized_status in ACTIVE_TASK_STATUSES and normalized_status not in {"pending", "queued"}:
            task.setdefault("started_at", now)
        if normalized_status in TERMINAL_TASK_STATUSES:
            task.setdefault("finished_at", now)
        task["updated_at"] = now
        _append_log(task, append_log)
        _persist_task(
            task,
            event_message=append_log or message,
            event_type="status_changed" if status is not None else "log",
        )
        snapshot = deepcopy(task)
    if push:
        push_task_update(task_id)
    return snapshot


def update_progress(
    task_id: str,
    *,
    current: Optional[int] = None,
    total: Optional[int] = None,
    current_file: Optional[str] = None,
    stage: Optional[str] = None,
    current_batch: Optional[int] = None,
    total_batches: Optional[int] = None,
    successful_batches: Optional[int] = None,
    failed_batches: Optional[int] = None,
    error_count: Optional[int] = None,
    glossary_issues: Optional[int] = None,
    format_issues: Optional[int] = None,
    format_repair: Optional[Dict[str, Any]] = None,
    workshop_progress: Optional[Dict[str, Any]] = None,
    log_message: Optional[str] = None,
    push: bool = False,
) -> Dict[str, Any]:
    progress_updates: Dict[str, Any] = {}
    if current is not None:
        progress_updates["current"] = current
    if total is not None:
        progress_updates["total"] = total
    if current_file is not None:
        progress_updates["current_file"] = current_file
    if stage is not None:
        progress_updates["stage"] = stage
    if current_batch is not None:
        progress_updates["current_batch"] = current_batch
    if total_batches is not None:
        progress_updates["total_batches"] = total_batches
    if successful_batches is not None:
        progress_updates["successful_batches"] = successful_batches
    if failed_batches is not None:
        progress_updates["failed_batches"] = failed_batches
    if error_count is not None:
        progress_updates["error_count"] = error_count
    if glossary_issues is not None:
        progress_updates["glossary_issues"] = glossary_issues
    if format_issues is not None:
        progress_updates["format_issues"] = format_issues
    if format_repair is not None:
        progress_updates["format_repair"] = format_repair
    if workshop_progress is not None:
        progress_updates["workshop_progress"] = workshop_progress

    if total and current is not None:
        progress_updates["percent"] = int((current / total) * 100)

    return update_task(task_id, progress=progress_updates, append_log=log_message, push=push)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        task = tasks.get(task_id)
        if task is not None:
            return deepcopy(task)
        if _repository is None:
            return None
        persisted = _repository.get_task(task_id)
        if persisted is not None:
            tasks[task_id] = persisted
            return deepcopy(persisted)
        return None


def list_tasks() -> list[Dict[str, Any]]:
    """Return safe snapshots for the global task center."""
    with _LOCK:
        return [deepcopy(task) for task in tasks.values()]


def get_task_events(task_id: str, *, limit: int = 500) -> list[Dict[str, Any]]:
    if _repository is not None:
        try:
            return _repository.list_events(task_id, limit=limit)
        except (OSError, sqlite3.Error) as exc:
            logging.error("Failed to load task events for %s: %s", task_id, exc)
    task = get_task(task_id) or {}
    return [
        {
            "event_id": f"legacy-{index}",
            "task_id": task_id,
            "sequence": index + 1,
            "timestamp": None,
            "level": _event_level(task.get("status"), message),
            "event_type": "legacy_log",
            "message": message,
            "metadata": {},
        }
        for index, message in enumerate(task.get("log") or [])
    ][-limit:]


def get_task_payload(task_id: str) -> Optional[Dict[str, Any]]:
    task = get_task(task_id)
    if task is None:
        return None
    if "log" in task and len(task["log"]) > MAX_PAYLOAD_LOG_LINES:
        task["log"] = task["log"][-MAX_PAYLOAD_LOG_LINES:]
    task["events"] = get_task_events(task_id, limit=MAX_PAYLOAD_LOG_LINES)
    return task


def push_task_update(task_id: str) -> None:
    payload = get_task_payload(task_id)
    if payload is None:
        return
    try:
        ws_manager.sync_send_task_update(task_id, payload)
    except Exception as e:
        logging.error(f"WebSocket push failed for task {task_id}: {e}")
