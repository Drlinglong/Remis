import logging
import threading
from copy import deepcopy
from typing import Any, Dict, Optional

from scripts.shared.state import tasks
from scripts.shared.ws_manager import ws_manager

_LOCK = threading.RLock()
MAX_STORED_LOG_LINES = 1000
MAX_PAYLOAD_LOG_LINES = 100

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
}


def _merge_dict(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def _ensure_task(task_id: str) -> Dict[str, Any]:
    task = tasks.setdefault(task_id, {"status": "pending", "log": []})
    task.setdefault("status", "pending")
    task.setdefault("log", [])
    return task


def _append_log(task: Dict[str, Any], message: Optional[str]) -> None:
    if not message:
        return
    task["log"].append(message)
    if len(task["log"]) > MAX_STORED_LOG_LINES:
        task["log"] = task["log"][-500:]


def create_task(task_id: str, *, status: str = "pending", log_message: Optional[str] = None) -> Dict[str, Any]:
    with _LOCK:
        tasks[task_id] = {"task_id": task_id, "status": status, "log": []}
        _append_log(tasks[task_id], log_message)
        return deepcopy(tasks[task_id])


def init_progress(task_id: str, progress: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _LOCK:
        task = _ensure_task(task_id)
        task["progress"] = deepcopy(DEFAULT_PROGRESS)
        if progress:
            _merge_dict(task["progress"], progress)
        return deepcopy(task["progress"])


def update_task(
    task_id: str,
    *,
    status: Optional[str] = None,
    message: Optional[str] = None,
    append_log: Optional[str] = None,
    progress: Optional[Dict[str, Any]] = None,
    summary: Optional[Dict[str, Any]] = None,
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
        if clear_result_path:
            task.pop("result_path", None)
        elif result_path is not None:
            task["result_path"] = result_path
        _append_log(task, append_log)
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

    if total and current is not None:
        progress_updates["percent"] = int((current / total) * 100)

    return update_task(task_id, progress=progress_updates, append_log=log_message, push=push)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        task = tasks.get(task_id)
        return deepcopy(task) if task is not None else None


def get_task_payload(task_id: str) -> Optional[Dict[str, Any]]:
    task = get_task(task_id)
    if task is None:
        return None
    if "log" in task and len(task["log"]) > MAX_PAYLOAD_LOG_LINES:
        task["log"] = task["log"][-MAX_PAYLOAD_LOG_LINES:]
    return task


def push_task_update(task_id: str) -> None:
    payload = get_task_payload(task_id)
    if payload is None:
        return
    try:
        ws_manager.sync_send_task_update(task_id, payload)
    except Exception as e:
        logging.error(f"WebSocket push failed for task {task_id}: {e}")
