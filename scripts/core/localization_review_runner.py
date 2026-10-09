"""Persist each paid review response, never retry or apply suggestions implicitly."""
from .batch_repository import BatchConflict
from .localization_review_persistence import save_review_results
from .openai_batch_transport import native_response_completed, usage_totals


class LocalizationReviewRunner:
    def __init__(self, service):
        self.service, self.batch = service, service.batch

    async def run(self, job_id):
        batch = self.batch
        job = batch.repository.get(job_id, "review_job")
        if job.get("remote_status") != "queued":
            return
        plan = batch.repository.get(job["plan_id"], "review_plan")
        requests = batch.artifacts.get(plan["requests_artifact"])
        results, refs = [], []
        batch.repository.update(job_id, {"remote_status": "running"})
        for request in requests:
            batch.repository.update(job_id, {"in_flight_custom_id": request["custom_id"]})
            try:
                body = await batch.transport_for(plan["settings"]).complete(request["body"])
                row = {"custom_id": request["custom_id"], "response": {"status_code": 200, "body": body}}
            except BatchConflict as error:
                row = {"custom_id": request["custom_id"], "error": {"code": error.code}}
            except Exception:
                row = {"custom_id": request["custom_id"], "error": {"code": "review_response_unknown"}}
            results.append(row)
            refs.append(batch.artifacts.put(row))
            batch.repository.update(job_id, {"request_artifacts": refs, "completed_requests": len(results), "in_flight_custom_id": None})
            if row.get("error") or not native_response_completed(row["response"]["body"]):
                break
        remote = {"results": results, "usage": usage_totals(results)}
        save_review_results(batch, plan, job_id, remote)
