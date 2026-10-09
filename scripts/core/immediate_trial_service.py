"""Immediate paid trials reuse frozen prompts, the collector and apply workflow."""
import time
from .batch_collection import collect_results
from .batch_repository import BatchConflict
from .batch_sources import require_current_sources
from .openai_batch_transport import native_response_completed, usage_totals


class ImmediateTrialService:
    def __init__(self, batch):
        self.batch = batch

    async def start(self, request, plan):
        batch = self.batch
        if plan.get("execution_mode") != "immediate":
            raise BatchConflict("execution_mode_conflict", "This is not an immediate trial plan.")
        existing = batch.repository.find_intent(plan["project_id"], request.idempotency_key)
        if existing:
            if existing["fingerprint"] != plan["fingerprint"]:
                raise BatchConflict("idempotency_conflict", "This key belongs to another plan.")
            return batch.get(existing["job_id"])
        if time.time() > plan["expires_at"]:
            raise BatchConflict("plan_expired", "Refresh the plan before a new paid submission.")
        snapshot = batch.artifacts.get(plan["source_artifact"])
        await require_current_sources(batch.manager, snapshot)
        batch._terms(plan["settings"], snapshot["game_id"])
        batch.transport_for(plan["settings"]).ensure_configured()
        job, winner = batch.repository.reserve(plan, request.idempotency_key)
        if winner:
            batch.repository.update(job["id"], {"execution_mode": "immediate", "submission_state": "submitted",
                "remote_status": "queued", "completed_requests": 0, "request_artifacts": []})
        return {**batch.get(job["id"]), "dispatch_immediate": winner}

    async def run(self, job_id):
        batch = self.batch
        job = batch.repository.get(job_id, "job")
        if job.get("execution_mode") != "immediate" or job.get("remote_status") != "queued":
            return
        plan = batch.repository.get(job["plan_id"], "plan")
        transport = batch.transport_for(plan["settings"])
        requests = batch.artifacts.get(plan["requests_artifact"])
        snapshot = batch.artifacts.get(plan["source_artifact"])
        results, references = [], []
        batch.repository.update(job_id, {"remote_status": "running"})
        for item in requests:
            batch.repository.update(job_id, {"in_flight_custom_id": item["custom_id"]})
            try:
                body = await transport.complete(item["body"])
                row = {"custom_id": item["custom_id"], "response": {"status_code": 200, "body": body}}
            except BatchConflict as error:
                row = {"custom_id": item["custom_id"], "error": {"code": error.code}}
            except Exception:
                # Never print provider exception text or automatically repeat a paid call.
                row = {"custom_id": item["custom_id"], "error": {"code": "immediate_response_unknown"}}
            results.append(row)
            references.append(batch.artifacts.put(row))
            batch.repository.update(job_id, {"request_artifacts": references,
                "completed_requests": len(results), "in_flight_custom_id": None})
            if row.get("error") or not native_response_completed(row["response"]["body"]):
                break
        remote = {"results": results, "usage": usage_totals(results)}
        _, terms = batch._terms(plan["settings"], snapshot["game_id"])
        collection = collect_results(snapshot, requests, remote, plan["settings"]["target_locale"], terms)
        collection["parser_version"] = "batch-collection/v1"
        batch.repository.update(job_id, {"remote_status": "completed", "remote_artifact": batch.artifacts.put(remote),
            "usage": remote["usage"], "collection_artifact": batch.artifacts.put(collection),
            "collection_status": "collected_with_errors" if collection["diagnostics"] else "collected"})
