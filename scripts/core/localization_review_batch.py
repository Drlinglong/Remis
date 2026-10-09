"""Native Batch review dispatch retains unknown submissions without retries."""
from .batch_prompts import wire_payload
from .batch_repository import BatchConflict
from .localization_review_persistence import save_review_results
from .openai_batch_transport import BATCH_TERMINAL_STATES


async def submit_review_batch(batch, plan, job_id):
    try:
        requests = batch.artifacts.get(plan["requests_artifact"])
        remote = await batch.transport_for(plan["settings"]).submit(wire_payload(plan["settings"], requests))
        if not isinstance(remote, dict) or not isinstance(remote.get("id"), str) or not remote["id"]:
            raise BatchConflict("submission_unknown", "No durable remote review Batch ID returned.")
        batch.repository.update(job_id, {"submission_state": "submitted", "remote_id": remote["id"],
            "remote_status": remote.get("status"), "remote_artifact": batch.artifacts.put(remote)})
    except Exception as error:
        changes = {"submission_error_code": error.code if isinstance(error, BatchConflict) else "submission_unknown"}
        if getattr(error, "uploaded_file_id", None):
            changes["uploaded_file_id"] = error.uploaded_file_id
        batch.repository.update(job_id, changes)


async def refresh_review_batch(batch, job, plan):
    if not job.get("remote_id"):
        raise BatchConflict("submission_unknown", "Bind a verified remote review Batch before retrieval.")
    remote = await batch.transport_for(plan["settings"]).retrieve(job["remote_id"])
    if not isinstance(remote, dict) or remote.get("id") != job["remote_id"]:
        raise BatchConflict("remote_identity_conflict", "The remote review Batch identity changed.")
    if remote.get("status") in BATCH_TERMINAL_STATES:
        save_review_results(batch, plan, job["id"], remote)
    else:
        batch.repository.update(job["id"], {"remote_status": remote.get("status"),
            "remote_artifact": batch.artifacts.put(remote), "request_counts": remote.get("request_counts")})


async def reconcile_review_batch(batch, job, plan, remote_id):
    if job.get("remote_id") or job["submission_state"] != "submission_unknown":
        raise BatchConflict("submission_already_bound", "Only unknown unbound review submissions can be reconciled.")
    remote = await batch.transport_for(plan["settings"]).retrieve(remote_id)
    expected = {r["custom_id"] for r in batch.artifacts.get(plan["requests_artifact"])}
    results = remote.get("results", []) if isinstance(remote, dict) else []
    actual = [r.get("custom_id") for r in results if isinstance(r, dict)]
    if (not isinstance(remote, dict) or remote.get("id") != remote_id or remote.get("status") not in BATCH_TERMINAL_STATES
            or len(actual) != len(expected) or set(actual) != expected):
        raise BatchConflict("unverified_remote_binding", "Verify a terminal review Batch with exactly the persisted custom IDs.")
    batch.repository.update(job["id"], {"remote_id": remote_id, "submission_state": "submitted"})
    save_review_results(batch, plan, job["id"], remote)
