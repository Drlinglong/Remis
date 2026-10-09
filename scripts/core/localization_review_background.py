"""Ordinary-price native Responses jobs with durable IDs, not OpenAI Batch."""
import uuid

from .batch_repository import BatchConflict
from .localization_review_persistence import save_review_results
from .openai_batch_transport import normalize_response

ACTIVE_RESPONSE_STATES = {"queued", "in_progress"}
TERMINAL_RESPONSE_STATES = {"completed", "failed", "incomplete", "cancelled"}
DISPATCH_INSTANCE = uuid.uuid4().hex


def all_responses_accepted(job):
    records = job.get("response_submissions", {})
    return bool(records) and all(r["state"] == "accepted" for r in records.values())


def recover_dispatch_state(batch, job):
    if not job.get("dispatch_finished"):
        if all_responses_accepted(job):
            return batch.repository.update(job["id"], {"dispatch_finished": True})
        if job.get("dispatch_owner") != DISPATCH_INSTANCE:
            return batch.repository.update(job["id"], {"dispatch_finished": True, "dispatch_interrupted": True})
    return job


def background_recovery_ready(job):
    records = job.get("response_submissions", {})
    return all_responses_accepted(job) and all(
        r["state"] == "accepted" and (
            r.get("response_status") in TERMINAL_RESPONSE_STATES and bool(r.get("response_artifact"))
            or r.get("response_status") in ACTIVE_RESPONSE_STATES
            and r.get("remote_background") is True and r.get("remote_store") is True)
        for r in records.values())


def response_row(custom_id, body):
    return {"custom_id": custom_id, "response": {"status_code": 200, "body": normalize_response(body)}}


def save_response(batch, job_id, custom_id, body, submissions):
    digest = batch.artifacts.put(response_row(custom_id, body))
    updated = batch.repository.update_review_response(job_id, custom_id,
        {"state": "accepted", "response_id": body["id"], "response_status": body.get("status"),
         "remote_background": body.get("background"), "remote_store": body.get("store"),
         "response_artifact": digest, "acceptance_artifact": digest})
    submissions.update(updated["response_submissions"])


def collect_background_results(batch, plan, job_id, submissions):
    current = recover_dispatch_state(batch, batch.repository.get(job_id, "review_job"))
    submissions = current.get("response_submissions", {})
    pending = not current.get("dispatch_finished") or any(
        r.get("response_status") not in TERMINAL_RESPONSE_STATES for r in submissions.values() if r["state"] == "accepted")
    unknown = any(r["state"] == "submission_unknown" for r in submissions.values())
    unsent = any(r["state"] == "not_submitted" for r in submissions.values())
    results = [batch.artifacts.get(r["response_artifact"]) for r in submissions.values()
               if r["state"] == "accepted" and r.get("response_status") in TERMINAL_RESPONSE_STATES]
    status = "running" if pending else "submission_unknown" if unknown else "completed"
    if results or not pending:
        save_review_results(batch, plan, job_id, {"status": status, "results": results})
        if pending:
            batch.repository.update(job_id, {"collection_status": "partial"})
    else:
        batch.repository.update(job_id, {"remote_status": status})
    state = "submission_unknown" if unknown else "partially_submitted" if unsent else "submitted"
    return batch.repository.update(job_id, {"submission_state": state})


async def submit_review_responses(batch, plan, job_id):
    requests = batch.artifacts.get(plan["requests_artifact"])
    submissions = {r["custom_id"]: {"state": "not_submitted"} for r in requests}
    batch.repository.update(job_id, {"execution_mode": "background", "response_submissions": submissions,
                                     "dispatch_finished": False, "dispatch_owner": DISPATCH_INSTANCE})
    for request in requests:
        custom_id = request["custom_id"]
        # Whole-job reserve has a single winner; replay never dispatches this loop.
        batch.repository.update_review_response(job_id, custom_id, {"state": "submission_unknown"})
        try:
            body = await batch.transport_for(plan["settings"]).start_background_response(request["body"])
            if not isinstance(body, dict) or not isinstance(body.get("id"), str) or not body["id"]:
                raise BatchConflict("submission_unknown", "No durable native response ID was returned.")
            save_response(batch, job_id, custom_id, body, submissions)
        except Exception as error:
            batch.repository.update_review_response(job_id, custom_id,
                {"error_code": error.code if isinstance(error, BatchConflict) else "submission_unknown"})
            break
        if body.get("status") not in ACTIVE_RESPONSE_STATES | {"completed"}:
            break
    batch.repository.update(job_id, {"dispatch_finished": True})
    collect_background_results(batch, plan, job_id, submissions)


async def refresh_review_responses(batch, job, plan):
    submissions = job.get("response_submissions", {})
    for custom_id, record in submissions.items():
        if record["state"] != "accepted" or record.get("response_status") in TERMINAL_RESPONSE_STATES:
            continue
        body = await batch.transport_for(plan["settings"]).retrieve_response(record["response_id"])
        if not isinstance(body, dict) or body.get("id") != record["response_id"]:
            raise BatchConflict("remote_identity_conflict", "Native review response identity changed.")
        save_response(batch, job["id"], custom_id, body, submissions)
    collect_background_results(batch, plan, job["id"], submissions)


async def reconcile_review_response(batch, job, plan, request):
    submissions = job.get("response_submissions", {})
    record = submissions.get(request.custom_id)
    if not record or record["state"] != "submission_unknown":
        raise BatchConflict("response_already_bound", "Only an unknown background response can be reconciled.")
    expected = next(r for r in batch.artifacts.get(plan["requests_artifact"]) if r["custom_id"] == request.custom_id)
    body = await batch.transport_for(plan["settings"]).retrieve_response(request.response_id)
    if (not isinstance(body, dict) or body.get("id") != request.response_id
            or body.get("metadata") != expected["body"]["metadata"]
            or any(r.get("response_id") == request.response_id for r in submissions.values())):
        raise BatchConflict("unverified_remote_binding", "Verify the exact persisted request metadata and unique response ID.")
    save_response(batch, job["id"], request.custom_id, body, submissions)
    collect_background_results(batch, plan, job["id"], submissions)
