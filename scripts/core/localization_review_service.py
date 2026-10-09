"""Plan and dispatch native model reviews over retained translation candidates."""
import time
import uuid

from .batch_artifacts import fingerprint
from .batch_collection import parse_result
from .batch_repository import BatchConflict
from .batch_sources import require_current_sources
from .localization_review_prompts import build_review_requests
from .quality_reference import freeze_reference
from .openai_batch_transport import BATCH_TERMINAL_STATES


class LocalizationReviewService:
    def __init__(self, batch):
        self.batch = batch

    def candidates(self, job_id):
        batch = self.batch
        job = batch.repository.get(job_id, "job")
        if job.get("remote_status") not in BATCH_TERMINAL_STATES or not job.get("remote_artifact"):
            raise BatchConflict("translation_not_completed", "Wait for retained terminal translation results.")
        plan = batch.repository.get(job["plan_id"], "plan")
        snapshot = batch.artifacts.get(plan["source_artifact"])
        requests = batch.artifacts.get(plan["requests_artifact"])
        results = batch.artifacts.get(job["remote_artifact"]).get("results", [])
        candidates = {}
        for request in requests:
            found = [r for r in results if isinstance(r, dict) and r.get("custom_id") == request["custom_id"]]
            parsed = parse_result(found[0] if found else {}, len(found), request["entry_ids"])
            if not isinstance(parsed, str):
                candidates.update(parsed)  # Include parsed candidates even when prior tag validation failed.
        return job, plan, snapshot, candidates

    async def plan(self, request):
        batch = self.batch
        job, original, snapshot, candidates = self.candidates(request.translation_job_id)
        selected = set(request.entry_ids or candidates)
        if not selected or len(selected) != len(request.entry_ids or selected) or not selected.issubset(candidates):
            raise BatchConflict("invalid_review_selection", "Select unique IDs with retained parsed candidates.", 400)
        reference_snapshot, reference = await freeze_reference(batch.manager, request.reference_project_id, request.reference_file_ids)
        if reference_snapshot and reference_snapshot["game_id"] != snapshot["game_id"]:
            raise BatchConflict("reference_game_conflict", "The reference project belongs to another game.", 400)
        settings = {**original["settings"], **request.model_dump(), "api_provider": "openai",
                    "translation_context_mode": "term_release" if request.term_release_id else "none"}
        if settings["reasoning"].keys() - {"mode", "effort"}:
            raise BatchConflict("unsupported_reasoning_parameter", "Review uses explicit mode and effort only.", 400)
        release, terms = batch._terms(settings, snapshot["game_id"])
        catalog = await batch.transport_for(settings).model_endpoints(request.model)
        entries = []
        for file in snapshot["files"]:
            for entry in file["entries"]:
                if entry["id"] not in selected:
                    continue
                ref = reference.get(entry["key"])
                matches = bool(ref and ref["source"] == entry["source"])
                entries.append({**entry, "candidate": candidates[entry["id"]],
                    "reference": ref["translation"] if matches else None, "reference_source_matches": matches})
        identifier = "review_plan_" + uuid.uuid4().hex
        requests = build_review_requests(identifier, entries, settings, terms)
        source_artifact = batch.artifacts.put(snapshot)
        entries_artifact = batch.artifacts.put(entries)
        reference_artifact = batch.artifacts.put(reference_snapshot)
        requests_artifact = batch.artifacts.put(requests)
        return batch.repository.put("review_plan", {"id": identifier, "project_id": job["project_id"],
            "translation_job_id": job["id"], "settings": settings, "source_artifact": source_artifact,
            "entries_artifact": entries_artifact, "reference_artifact": reference_artifact,
            "requests_artifact": requests_artifact, "term_release": release,
            "model_catalog_artifact": batch.artifacts.put(catalog), "created_at": time.time(),
            "expires_at": time.time() + 86400, "entry_count": len(entries), "request_count": len(requests),
            "reference_match_count": sum(e["reference_source_matches"] for e in entries),
            "fingerprint": fingerprint([source_artifact, entries_artifact, reference_artifact, requests_artifact, settings]),
            "paid_calls": 0, "allowed_actions": ["start_review"], "overwrites_translation": False})

    def get(self, job_id):
        job = self.batch.repository.get(job_id, "review_job")
        actions = ["read_report"] if job.get("report_artifact") else ["wait"] if job.get("remote_status") in {"queued", "running"} else []
        if job.get("request_artifacts"):
            actions.append("read_saved_results")
        if job.get("execution_mode") == "background":
            if any(r["state"] == "accepted" for r in job.get("response_submissions", {}).values()):
                actions.extend(["refresh", "read_saved_results"])
            if any(r["state"] == "submission_unknown" for r in job.get("response_submissions", {}).values()):
                actions.append("reconcile_response")
        elif job.get("remote_id"):
            actions.append("refresh")
        elif job["submission_state"] == "submission_unknown":
            actions.append("reconcile_submission")
        result = {**job, "allowed_actions": list(dict.fromkeys(actions))}
        if job.get("execution_mode") == "background":
            from .localization_review_background import background_recovery_ready
            result["shutdown_recovery_ready"] = background_recovery_ready(job)
        return result

    async def start(self, request):
        batch = self.batch
        if not request.approved:
            raise BatchConflict("approval_required", "Paid model review requires authorization.")
        plan = batch.repository.get(request.plan_id, "review_plan")
        intent = batch.repository.find_intent(plan["project_id"], request.idempotency_key)
        if intent:
            if intent["fingerprint"] != plan["fingerprint"]:
                raise BatchConflict("idempotency_conflict", "This key belongs to another workflow.")
            return self.get(intent["job_id"])
        if time.time() > plan["expires_at"]:
            raise BatchConflict("plan_expired", "Create a new review plan.")
        await require_current_sources(batch.manager, batch.artifacts.get(plan["source_artifact"]))
        reference = batch.artifacts.get(plan["reference_artifact"])
        if reference:
            await require_current_sources(batch.manager, reference)
        batch.transport_for(plan["settings"]).ensure_configured()
        job, winner = batch.repository.reserve(plan, request.idempotency_key, kind="review_job")
        if winner and plan["settings"]["execution_mode"] == "background":
            from .localization_review_background import submit_review_responses
            await submit_review_responses(batch, plan, job["id"])
            return self.get(job["id"])
        if winner and plan["settings"]["execution_mode"] == "batch":
            from .localization_review_batch import submit_review_batch
            await submit_review_batch(batch, plan, job["id"])
            return self.get(job["id"])
        if winner:
            batch.repository.update(job["id"], {"submission_state": "submitted", "remote_status": "queued",
                                               "completed_requests": 0, "request_artifacts": []})
        return {**self.get(job["id"]), "dispatch_review": winner}

    async def refresh(self, job_id):
        from .localization_review_batch import refresh_review_batch
        job = self.batch.repository.get(job_id, "review_job")
        plan = self.batch.repository.get(job["plan_id"], "review_plan")
        if plan["settings"]["execution_mode"] == "background":
            from .localization_review_background import refresh_review_responses
            await refresh_review_responses(self.batch, job, plan)
        else:
            await refresh_review_batch(self.batch, job, plan)
        return self.get(job_id)

    async def reconcile(self, job_id, request):
        from .localization_review_batch import reconcile_review_batch
        if not request.approved:
            raise BatchConflict("approval_required", "Binding a remote review Batch requires authorization.")
        job = self.batch.repository.get(job_id, "review_job")
        plan = self.batch.repository.get(job["plan_id"], "review_plan")
        if plan["settings"]["execution_mode"] == "background":
            raise BatchConflict("execution_mode_conflict", "Use per-response reconciliation for ordinary background jobs.", 400)
        await reconcile_review_batch(self.batch, job, plan, request.remote_id)
        return self.get(job_id)

    async def reconcile_response(self, job_id, request):
        from .localization_review_background import reconcile_review_response
        if not request.approved:
            raise BatchConflict("approval_required", "Binding a native response requires authorization.")
        job = self.batch.repository.get(job_id, "review_job")
        plan = self.batch.repository.get(job["plan_id"], "review_plan")
        if plan["settings"]["execution_mode"] != "background":
            raise BatchConflict("execution_mode_conflict", "This is not a background Responses job.", 400)
        await reconcile_review_response(self.batch, job, plan, request)
        return self.get(job_id)

    def artifact(self, job_id, kind):
        job = self.batch.repository.get(job_id, "review_job")
        if kind == "saved_results":
            from .openai_batch_transport import usage_totals
            background = job.get("response_submissions", {})
            refs = [r["response_artifact"] for r in background.values() if r.get("response_artifact")] if background else job.get("request_artifacts", [])
            results = [self.batch.artifacts.get(ref) for ref in refs]
            return {"results": results, "usage": usage_totals(results), "job_status": job["remote_status"],
                    "in_flight_response_may_be_unknown": bool(job.get("in_flight_custom_id")) or any(r["state"] == "submission_unknown" for r in background.values())}
        plan = self.batch.repository.get(job["plan_id"], "review_plan")
        refs = {"entries": plan["entries_artifact"], "requests": plan["requests_artifact"],
                "source": plan["source_artifact"], "reference": plan["reference_artifact"],
                "remote": job.get("remote_artifact"), "report": job.get("report_artifact")}
        if not refs.get(kind):
            raise BatchConflict("artifact_unavailable", "This review artifact is not available.", 404)
        return self.batch.artifacts.get(refs[kind])
