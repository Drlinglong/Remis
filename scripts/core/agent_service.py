from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from scripts.app_settings import APP_DATA_DIR


AGENT_API_VERSION = "2026-07-18"
PLAN_TTL_MINUTES = 30
SECRET_FIELD_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _non_secret_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _non_secret_copy(item)
            for key, item in value.items()
            if not any(marker in str(key).lower() for marker in SECRET_FIELD_MARKERS)
        }
    if isinstance(value, list):
        return [_non_secret_copy(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_non_secret_copy(item) for item in value)
    return deepcopy(value)


class AgentRegistry:
    """Persist non-secret Agent plan and job metadata across backend restarts."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.path.join(APP_DATA_DIR, "agent_api_registry.json"))
        self._lock = threading.RLock()
        self._payload = self._load()

    def _empty(self) -> Dict[str, Any]:
        return {"version": 1, "plans": {}, "jobs": {}, "audit": []}

    def _load(self) -> Dict[str, Any]:
        try:
            if not self.path.exists():
                return self._empty()
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return self._empty()
        if not isinstance(payload, dict):
            return self._empty()
        payload.setdefault("version", 1)
        payload.setdefault("plans", {})
        payload.setdefault("jobs", {})
        payload.setdefault("audit", [])
        return payload

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(self._payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def create_plan(
        self,
        *,
        project_id: Optional[str],
        execution_args: Dict[str, Any],
        dry_run: bool,
        summary: str,
        kind: str = "translation",
        inspection: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = utc_now()
        plan_id = f"plan_{uuid.uuid4().hex}"
        record = {
            "plan_id": plan_id,
            "project_id": project_id,
            "kind": kind,
            "status": "ready" if dry_run else "awaiting_approval",
            "dry_run": dry_run,
            "summary": summary,
            "execution_args": _non_secret_copy(execution_args),
            "inspection": _non_secret_copy(inspection or {}),
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(minutes=PLAN_TTL_MINUTES)),
            "consumed_at": None,
        }
        with self._lock:
            self._payload["plans"][plan_id] = record
            self._audit("plan_created", project_id=project_id, plan_id=plan_id)
            self._save()
        return deepcopy(record)

    def consume_plan(self, plan_id: str, *, approved: bool) -> Dict[str, Any]:
        with self._lock:
            record = self._payload["plans"].get(plan_id)
            if not record:
                raise KeyError("Agent plan not found")
            if record.get("consumed_at"):
                raise RuntimeError("Agent plan has already been executed")
            expires_at = datetime.fromisoformat(
                str(record["expires_at"]).replace("Z", "+00:00")
            )
            if expires_at < utc_now():
                raise TimeoutError("Agent plan expired")
            if not record.get("dry_run") and not approved:
                raise PermissionError(
                    "Explicit approval is required before starting a translation job"
                )
            record["consumed_at"] = _iso(utc_now())
            record["status"] = "consumed"
            self._audit(
                "plan_consumed",
                project_id=record.get("project_id"),
                plan_id=plan_id,
            )
            self._save()
            return deepcopy(record)

    def release_plan(self, plan_id: str) -> None:
        with self._lock:
            record = self._payload["plans"].get(plan_id)
            if not record:
                return
            record["consumed_at"] = None
            record["status"] = (
                "ready" if record.get("dry_run") else "awaiting_approval"
            )
            self._save()

    def record_job(
        self,
        *,
        job_id: str,
        project_id: str,
        plan_id: str,
        kind: str,
        execution_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = {
            "job_id": job_id,
            "project_id": project_id,
            "plan_id": plan_id,
            "kind": kind,
            "execution_args": _non_secret_copy(execution_args),
            "created_at": _iso(utc_now()),
            "last_snapshot": None,
        }
        with self._lock:
            self._payload["jobs"][job_id] = record
            self._audit(
                "job_created",
                project_id=project_id,
                job_id=job_id,
                kind=kind,
            )
            self._save()
        return deepcopy(record)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._payload["jobs"].get(job_id)
            return deepcopy(record) if record else None

    def list_jobs(self) -> list[Dict[str, Any]]:
        """Return persisted, non-secret job metadata for task aggregation."""
        with self._lock:
            return [deepcopy(record) for record in self._payload["jobs"].values()]

    def update_snapshot(self, job_id: str, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            record = self._payload["jobs"].get(job_id)
            if not record:
                return
            record["last_snapshot"] = _non_secret_copy(snapshot)
            record["updated_at"] = _iso(utc_now())
            self._save()

    def record_event(self, event: str, **fields: Any) -> None:
        with self._lock:
            self._audit(event, **fields)
            self._save()

    def _audit(self, event: str, **fields: Any) -> None:
        entry = {
            "event": event,
            "timestamp": _iso(utc_now()),
            **_non_secret_copy(fields),
        }
        audit = self._payload.setdefault("audit", [])
        audit.append(entry)
        if len(audit) > 500:
            del audit[:-500]


agent_registry = AgentRegistry()
