import logging
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from scripts.core.repositories.task_repository import TaskRepository
from scripts.shared.state import tasks
from scripts.shared.ws_manager import ws_manager

_LOCK = threading.RLock()
_UPDATE_LISTENERS: list[Callable[[str, Dict[str, Any]], None]] = []
MAX_STORED_LOG_LINES = 1000
MAX_PAYLOAD_LOG_LINES = 100
TASK_RETENTION_DAYS = 365
MAX_TERMINAL_TASKS = 5000
MIN_TERMINAL_TASKS = 1000
ACTIVE_TASK_STATUSES = {
    "pending",
    "starting",
    "queued",
    "running",
    "processing",
    "in_progress",
    "awaiting_approval",
    "waiting_approval",
    "cancelling",
}
TERMINAL_TASK_STATUSES = {"completed", "complete", "success", "failed", "partial_failed", "cancelled", "canceled", "interrupted"}
_repository: Optional[TaskRepository] = None
_CANCELLATION_EVENTS: Dict[str, threading.Event] = {}


class DuplicateTaskError(RuntimeError):
    def __init__(self, existing_task: Dict[str, Any]):
        self.existing_task = deepcopy(existing_task)
        super().__init__(f"Task {existing_task.get('task_id')} already owns this operation")


class TaskPersistenceError(RuntimeError):
    def __init__(self, task_id: str, failure: Dict[str, Any]):
        self.task_id = task_id
        self.failure = deepcopy(failure)
        super().__init__(f"Task {task_id} could not be persisted")


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
    "glossary_issue_details": [],
    "recovered_retries": 0,
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
        try:
            repository.prune_terminal_tasks(
                retention_days=TASK_RETENTION_DAYS,
                max_terminal_tasks=MAX_TERMINAL_TASKS,
                min_terminal_tasks=MIN_TERMINAL_TASKS,
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            logging.error("Failed to apply task retention policy: %s", exc)
        # Only active work needs an in-memory mirror for live updates and
        # duplicate-write protection. Historical tasks remain queryable from
        # SQLite by exact ID and through the paginated task API.
        persisted = repository.list_tasks(
            statuses=ACTIVE_TASK_STATUSES,
            include_events=False,
        )
        if replace:
            tasks.clear()
        for task in persisted:
            task_id = str(task.get("task_id") or "")
            if not task_id:
                continue
            recovery = _restart_recovery(task)
            if recovery is not None:
                message, attention_reason, preserve_checkpoint = recovery
                _mark_restart_interrupted(
                    task,
                    message,
                    attention_reason,
                    preserve_checkpoint=preserve_checkpoint,
                )
                now = task["updated_at"]
                try:
                    repository.save_task(
                        task,
                        event={
                            "timestamp": now,
                            "level": "warning",
                            "event_type": "recovery_interrupted",
                            "audience": "user",
                            "message": attention_reason,
                        },
                    )
                except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                    _mark_persistence_failure(task, exc)
                    logging.error(
                        "Failed to mark persisted task %s interrupted: %s",
                        task_id,
                        exc,
                    )
            current = tasks.get(task_id)
            if current is None or str(task.get("updated_at") or "") >= str(current.get("updated_at") or ""):
                tasks[task_id] = task


def get_repository() -> Optional[TaskRepository]:
    return _repository


def find_active_task_by_dedupe_key(dedupe_key: str) -> Optional[Dict[str, Any]]:
    """Return the exact active task currently holding a shared operation key."""
    with _LOCK:
        existing = next(
            (
                item
                for item in tasks.values()
                if (
                    item.get("dedupe_key") == dedupe_key
                    and str(item.get("status") or "").lower() in ACTIVE_TASK_STATUSES
                )
            ),
            None,
        )
        if existing is None and _repository is not None:
            existing = _repository.find_active_by_dedupe_key(
                dedupe_key,
                active_statuses=ACTIVE_TASK_STATUSES,
            )
        return deepcopy(existing) if existing is not None else None


def find_task_by_idempotency_key(idempotency_key: str) -> Optional[Dict[str, Any]]:
    """Return the exact task already bound to a caller-stable operation key."""
    with _LOCK:
        existing = next(
            (
                item
                for item in tasks.values()
                if item.get("idempotency_key") == idempotency_key
            ),
            None,
        )
        if existing is None and _repository is not None:
            existing = _repository.find_by_idempotency_key(idempotency_key)
        return deepcopy(existing) if existing is not None else None


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


def _mark_persistence_failure(task: Dict[str, Any], error: Exception) -> None:
    task["persistence_failure"] = {
        "code": "task_persistence_failed",
        "retryable": True,
        "error_type": type(error).__name__,
        "last_attempt_at": task.get("updated_at") or _utc_now_iso(),
    }


def _restart_recovery(task: Dict[str, Any]) -> Optional[tuple[str, str, bool]]:
    """Return restart interruption messaging for work that has no live worker."""

    kind = task.get("kind")
    checkpoint = task.get("checkpoint") or {}
    if kind == "initial_translation":
        checkpoint_available = checkpoint.get("available") is True
        return (
            "The app restarted before this initial translation finished.",
            (
                "The previous translation worker is no longer running. "
                "Resume from the saved checkpoint or start a new translation."
                if checkpoint_available
                else "The previous translation worker is no longer running. "
                "Return to Initial Translation to check for saved progress or start again."
            ),
            checkpoint_available,
        )
    if kind == "reference_library_maintenance":
        return (
            "The app restarted before official reference library maintenance finished.",
            "This reference library task cannot resume automatically. Review the current library state before retrying.",
            False,
        )
    if kind in {"neologism_mining", "context_archive_analysis"}:
        return (
            "The app restarted before this context-analysis task finished.",
            "This context-analysis task cannot resume automatically. Start it again.",
            False,
        )
    if (
        kind in {"agent_workshop", "agent_workshop_batch"}
        and checkpoint.get("resume_supported") is False
    ):
        return (
            "The app restarted before this repair task finished.",
            "This Agent Workshop task cannot resume automatically. Return to the workflow and review current validation results before retrying.",
            False,
        )
    return None


def _mark_restart_interrupted(
    task: Dict[str, Any],
    message: str,
    attention_reason: str,
    *,
    preserve_checkpoint: bool = False,
) -> None:
    now = _utc_now_iso()
    task["status"] = "interrupted"
    task["updated_at"] = now
    task["finished_at"] = now
    task["message"] = message
    task["attention_reason"] = attention_reason
    task.setdefault("progress", {})["stage"] = "Interrupted"
    if not preserve_checkpoint:
        checkpoint = task.setdefault("checkpoint", {})
        checkpoint["available"] = False
        checkpoint["stage"] = "interrupted"
        checkpoint["updated_at"] = now


def _persist_task(
    task: Dict[str, Any],
    *,
    event_message: Optional[str] = None,
    event_type: str = "log",
    event_audience: str = "user",
    event_level: Optional[str] = None,
    event_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    if _repository is None:
        return True
    task.pop("persistence_failure", None)
    try:
        event = None
        if event_message:
            event = {
                "timestamp": task.get("updated_at") or _utc_now_iso(),
                "level": event_level or _event_level(task.get("status"), event_message),
                "event_type": event_type,
                "audience": event_audience,
                "message": event_message,
                "metadata": event_metadata or {},
            }
        _repository.save_task(task, event=event)
        return True
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        _mark_persistence_failure(task, exc)
        logging.error("Failed to persist task %s: %s", task.get("task_id"), exc)
        return False


def register_task_update_listener(
    listener: Callable[[str, Dict[str, Any]], None],
) -> None:
    """Register an in-process observer for persisted task projections."""
    with _LOCK:
        if listener not in _UPDATE_LISTENERS:
            _UPDATE_LISTENERS.append(listener)


def _notify_task_update_listeners(task_id: str, snapshot: Dict[str, Any]) -> None:
    with _LOCK:
        listeners = list(_UPDATE_LISTENERS)
    for listener in listeners:
        try:
            listener(task_id, deepcopy(snapshot))
        except Exception as exc:
            logging.error("Task update listener failed for %s: %s", task_id, exc)


def create_task(
    task_id: str,
    *,
    status: str = "pending",
    log_message: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    reject_duplicate: bool = False,
    event_audience: str = "user",
    require_persistence: bool = False,
) -> Dict[str, Any]:
    with _LOCK:
        _CANCELLATION_EVENTS.pop(task_id, None)
        idempotency_key = str((fields or {}).get("idempotency_key") or "").strip() or None
        if idempotency_key:
            existing = next(
                (
                    item
                    for item in tasks.values()
                    if item.get("idempotency_key") == idempotency_key
                ),
                None,
            )
            if existing is None and _repository is not None:
                existing = _repository.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                raise DuplicateTaskError(existing)
        if dedupe_key and reject_duplicate:
            existing = next(
                (
                    item
                    for item in tasks.values()
                    if (
                        item.get("dedupe_key") == dedupe_key
                        and str(item.get("status") or "").lower() in ACTIVE_TASK_STATUSES
                    )
                ),
                None,
            )
            if existing is None and _repository is not None:
                existing = _repository.find_active_by_dedupe_key(
                    dedupe_key,
                    active_statuses=ACTIVE_TASK_STATUSES,
                )
            if existing is not None:
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
        persisted = _persist_task(
            tasks[task_id],
            event_message=log_message,
            event_type="task_created",
            event_audience=event_audience,
        )
        if require_persistence and not persisted:
            failed_task = tasks.pop(task_id)
            raise TaskPersistenceError(task_id, failed_task["persistence_failure"])
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
    event_audience: str = "user",
    event_level: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        task = _ensure_task(task_id)
        if status is not None:
            current_status = str(task.get("status") or "").lower()
            requested_status = str(status or "").lower()
            if not (
                current_status == "cancelling"
                and requested_status not in {"cancelling", "cancelled", "canceled"}
            ):
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
            _CANCELLATION_EVENTS.pop(task_id, None)
        task["updated_at"] = now
        if event_audience == "user":
            _append_log(task, append_log)
        _persist_task(
            task,
            event_message=append_log or message,
            event_type="status_changed" if status is not None else "log",
            event_audience=event_audience,
            event_level=event_level,
        )
        snapshot = deepcopy(task)
    _notify_task_update_listeners(task_id, snapshot)
    if push:
        push_task_update(task_id)
    return snapshot


def request_task_cancellation(task_id: str) -> Dict[str, Any]:
    """Request cooperative cancellation without releasing the task's lock early."""
    with _LOCK:
        task = _ensure_task(task_id)
        event = _CANCELLATION_EVENTS.setdefault(task_id, threading.Event())
        event.set()
    return update_task(
        task_id,
        status="cancelling",
        message="Cancellation requested. Waiting for the active provider request to stop safely.",
        append_log="Cancellation requested. No new translation batches will be started.",
        fields={"cancellation_requested_at": _utc_now_iso()},
        push=True,
    )


def is_task_cancellation_requested(task_id: str) -> bool:
    with _LOCK:
        event = _CANCELLATION_EVENTS.get(task_id)
        return bool(event and event.is_set())


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
    glossary_issue_details: Optional[list[Dict[str, Any]]] = None,
    recovered_retries: Optional[int] = None,
    format_issues: Optional[int] = None,
    format_repair: Optional[Dict[str, Any]] = None,
    workshop_progress: Optional[Dict[str, Any]] = None,
    log_message: Optional[str] = None,
    push: bool = False,
    event_audience: str = "user",
    event_level: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
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
    if glossary_issue_details is not None:
        progress_updates["glossary_issue_details"] = glossary_issue_details
    if recovered_retries is not None:
        progress_updates["recovered_retries"] = recovered_retries
    if format_issues is not None:
        progress_updates["format_issues"] = format_issues
    if format_repair is not None:
        progress_updates["format_repair"] = format_repair
    if workshop_progress is not None:
        progress_updates["workshop_progress"] = workshop_progress

    if total and current is not None:
        progress_updates["percent"] = int((current / total) * 100)

    return update_task(
        task_id,
        progress=progress_updates,
        append_log=log_message,
        push=push,
        event_audience=event_audience,
        event_level=event_level,
        fields=fields,
    )


def append_task_event(
    task_id: str,
    message: str,
    *,
    audience: str = "diagnostic",
    level: str = "debug",
    event_type: str = "diagnostic",
    metadata: Optional[Dict[str, Any]] = None,
    push: bool = False,
) -> Dict[str, Any]:
    if audience not in {"user", "diagnostic"}:
        raise ValueError("Task event audience must be user or diagnostic")
    with _LOCK:
        task = _ensure_task(task_id)
        task["updated_at"] = _utc_now_iso()
        if audience == "user":
            _append_log(task, message)
        _persist_task(
            task,
            event_message=message,
            event_type=event_type,
            event_audience=audience,
            event_level=level,
            event_metadata=metadata,
        )
        snapshot = deepcopy(task)
    if push:
        push_task_update(task_id)
    return snapshot


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


def get_task_events(
    task_id: str,
    *,
    limit: int = 500,
    include_diagnostics: bool = False,
) -> list[Dict[str, Any]]:
    if _repository is not None:
        try:
            return _repository.list_events(
                task_id,
                limit=limit,
                audience=None if include_diagnostics else "user",
            )
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
            "audience": "user",
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
