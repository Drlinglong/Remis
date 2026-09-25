"""Reconcile explicitly reviewed file edits with an existing job's baseline."""

import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from scripts.core.archive_manager import archive_manager
from scripts.core.loc_parser import parse_loc_file
from scripts.shared import task_state
from scripts.shared.services import project_manager

router = APIRouter(prefix="/api/agent", tags=["agent-baseline"])


class BaselineSyncRequest(BaseModel):
    approved: bool = False
    file_name: str
    keys: list[str] = Field(min_length=1, max_length=100)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _error(status, code, message):
    return HTTPException(status, detail={"code": code, "message": message, "retryable": False})


def reviewed_entries(root: Path, request: BaselineSyncRequest):
    root = root.resolve()
    candidate = (root / request.file_name).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() != ".yml":
        raise _error(403, "invalid_output_file", "Select a localization file inside this job's output.")
    if not candidate.is_file():
        raise _error(404, "output_file_missing", "The selected output file is missing.")
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != request.expected_sha256:
        raise _error(409, "output_revision_conflict", "The reviewed file has changed.")
    values = dict(parse_loc_file(candidate))
    keys = list(dict.fromkeys(request.keys))
    if any(key not in values for key in keys):
        raise _error(400, "entry_not_found", "Every key must identify an eligible entry in the reviewed file.")
    return candidate, [{"key": key, "translation": values[key]} for key in keys]


@router.post("/jobs/{job_id}/baseline/sync")
async def sync_reviewed_baseline(job_id: str, request: BaselineSyncRequest):
    if not request.approved:
        raise _error(409, "approval_required", "Explicit approval is required to synchronize reviewed edits.")
    # Reuse the same registered-output boundary as export; never accept a root from callers.
    from scripts.routers.agent import agent_registry, _export_candidate

    job = agent_registry.get_job(job_id)
    if not job:
        raise _error(404, "job_not_found", "Agent job not found.")
    task = task_state.get_task(job_id) or {}
    if task.get("status", (job.get("last_snapshot") or {}).get("status")) != "completed":
        raise _error(409, "job_not_completed", "Wait for this job to finish before synchronizing edits.")
    args = job.get("execution_args") or {}
    languages = args.get("target_lang_codes") or []
    if len(languages) != 1:
        raise _error(409, "ambiguous_language", "Baseline synchronization requires a single target language.")
    _, root = _export_candidate(task, job, None)
    candidate, entries = reviewed_entries(root, request)
    project = await project_manager.get_project(job["project_id"])
    if not project:
        raise _error(404, "project_not_found", "Project not found.")
    try:
        count = archive_manager.update_translations(
            project["name"], str(candidate), entries, str(languages[0]),
            project_id=job["project_id"],
        )
    except Exception as exc:
        raise _error(409, "baseline_sync_failed", "Existing baseline could not be synchronized; no keys were skipped.") from exc
    agent_registry.record_event("baseline_synchronized", project_id=job["project_id"], job_id=job_id, entry_count=count)
    return {"status": "synchronized", "updated_entries": count, "language": languages[0],
            "file_sha256": request.expected_sha256, "validation_refreshed": False}
