"""Agent batch orchestration over durable intents and immutable artifacts."""
import time
import uuid

from .batch_apply_service import BatchApplyService
from .batch_artifacts import fingerprint
from .batch_collection import collect_results
from .batch_prompts import build_requests, wire_payload
from .batch_repository import BatchConflict
from .batch_sources import freeze_sources, language_configuration, require_current_sources
from .term_release_service import TermReleaseService
from .openai_batch_transport import BATCH_TERMINAL_STATES


class AgentBatchService:
    def __init__(self, repository, artifacts, transport, manager, archive, output_root, project_guard=None, native_transport=None):
        self.repository, self.artifacts, self.transport = repository, artifacts, transport
        self.manager = manager
        self.native_transport = native_transport
        self.terms = TermReleaseService(repository, artifacts)
        self.apply_service = BatchApplyService(repository, artifacts, manager, archive, output_root, project_guard)

    def transport_for(self, settings):
        if settings.get("api_provider", "openrouter") == "openai":
            if self.native_transport is None:
                raise BatchConflict("native_transport_unavailable", "Native OpenAI transport is unavailable.")
            return self.native_transport
        return self.transport

    def _terms(self, settings, game_id):
        if settings["translation_context_mode"] == "none":
            if settings.get("term_release_id"):
                raise BatchConflict("context_configuration_conflict", "Select term_release mode when using terminology.", 400)
            return None, []
        if not settings.get("term_release_id"):
            raise BatchConflict("term_release_required", "Choose an immutable terminology release.", 400)
        release, terms = self.terms.get(settings["term_release_id"], game_id, settings["target_locale"])
        if release["maturity"] == "provisional" and not settings["allow_provisional_terms"]:
            raise BatchConflict("provisional_terms_require_choice", "Acknowledge provisional terminology explicitly.")
        return release, terms

    async def plan(self, request):
        if request.execution_mode == "immediate":
            from .advanced_agent_policy import require_advanced_experiment
            require_advanced_experiment("translation_trials")
        snapshot = await freeze_sources(self.manager, request)
        language_configuration(request.target_locale, request.game_language_slot)
        settings = request.model_dump()
        settings["target_locale"] = language_configuration(request.target_locale, request.game_language_slot)["code"]
        if settings["reasoning"].keys() - {"mode", "effort", "exclude"}:
            raise BatchConflict("unsupported_reasoning_parameter", "Only mode, effort and exclude are accepted.", 400)
        if "-pro" in request.model:
            if settings["reasoning"].get("mode") not in (None, "pro"):
                raise BatchConflict("reasoning_mode_conflict", "The selected Pro model requires pro mode.", 400)
            settings["reasoning"] = {**settings["reasoning"], "mode": "pro"}
        release, terms = self._terms(settings, snapshot["game_id"])
        if request.execution_mode == "immediate" and request.api_provider != "openai":
            raise BatchConflict("unsupported_immediate_provider", "Immediate trials currently use native OpenAI.", 400)
        transport = self.transport_for(settings)
        catalog_model = request.model if request.api_provider == "openai" else request.model.removesuffix(":batch") + ":batch"
        catalog = await transport.model_endpoints(catalog_model)
        identifier = "batch_plan_" + uuid.uuid4().hex
        requests = build_requests(identifier, snapshot, settings, terms)
        if request.api_provider == "openai":
            from .openai_batch_transport import responses_body
            for item in requests:
                item["body"] = responses_body(item["body"], request.model)
        source_artifact = self.artifacts.put(snapshot)
        request_artifact = self.artifacts.put(requests)
        payload = wire_payload(settings, requests)
        return self.repository.put("plan", {"id": identifier, "project_id": request.project_id,
            "execution_mode": request.execution_mode,
            "settings": settings, "source_artifact": source_artifact, "requests_artifact": request_artifact,
            "term_release": release, "model_catalog_artifact": self.artifacts.put(catalog),
            "created_at": time.time(), "expires_at": time.time() + 24 * 3600,
            "fingerprint": fingerprint([source_artifact, settings, request_artifact, release]),
            "request_count": len(requests), "entry_count": sum(len(item["entry_ids"]) for item in requests),
            "input_characters": len(str(payload)), "cost_estimate": None,
            "cost_note": "Output and reasoning use are uncalibrated; catalog pricing is pinned, not a spending guarantee.",
            "allowed_actions": ["submit"], "paid_calls": 0})

    def get(self, job_id):
        job = self.repository.get(job_id, "job")
        actions = []
        if job["remote_id"]:
            actions.append("refresh")
        elif job["submission_state"] == "submission_unknown":
            actions.append("reconcile_submission")
        if job["remote_status"] in BATCH_TERMINAL_STATES:
            actions.append("collect")
        if job.get("collection_artifact"):
            collection = self.artifacts.get(job["collection_artifact"])
            if collection["complete_file_ids"]:
                actions.append("plan_apply")
            if collection["failed_custom_ids"]:
                actions.append("plan_retry")
        if job.get("apply_plan_id") and job["apply_status"] in ("in_progress", "recovery_required"):
            actions.append("recover_apply")
        if job.get("ready_apply_plan_id") and job["apply_status"] == "not_applied":
            actions.append("apply")
        if job.get("execution_mode") == "immediate" and job.get("remote_status") in {"queued", "running"}:
            actions.append("wait")
        return {**job, "allowed_actions": actions}

    async def start(self, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Paid batch submission requires explicit authorization.")
        plan = self.repository.get(request.plan_id, "plan")
        if plan.get("execution_mode") == "immediate":
            from .advanced_agent_policy import require_advanced_experiment
            require_advanced_experiment("translation_trials")
            from .immediate_trial_service import ImmediateTrialService
            return await ImmediateTrialService(self).start(request, plan)
        existing = self.repository.find_intent(plan["project_id"], request.idempotency_key)
        if existing:
            if existing["fingerprint"] != plan["fingerprint"]:
                raise BatchConflict("idempotency_conflict", "The key belongs to a different plan.")
            return self.get(existing["job_id"])
        if time.time() > plan["expires_at"]:
            raise BatchConflict("plan_expired", "Refresh the plan before a new paid submission.")
        await require_current_sources(self.manager, self.artifacts.get(plan["source_artifact"]))
        self._terms(plan["settings"], self.artifacts.get(plan["source_artifact"])["game_id"])
        transport = self.transport_for(plan["settings"])
        if hasattr(transport, "ensure_configured"):
            transport.ensure_configured()
        job, winner = self.repository.reserve(plan, request.idempotency_key)
        if not winner:
            return self.get(job["id"])
        requests = self.artifacts.get(plan["requests_artifact"])
        try:
            remote = await transport.submit(wire_payload(plan["settings"], requests))
            if not isinstance(remote, dict) or not isinstance(remote.get("id"), str) or not remote["id"]:
                raise BatchConflict("submission_unknown", "The submission response did not provide a durable remote ID.")
            self.repository.update(job["id"], {"submission_state": "submitted", "remote_id": remote["id"],
                "remote_status": remote.get("status"), "remote_artifact": self.artifacts.put(remote)})
        except Exception as error:
            # The intent already says unknown. Do not retry or swallow the state.
            if isinstance(error, BatchConflict):
                self.repository.update(job["id"], {"submission_error_code": error.code,
                    "upstream_status": getattr(error, "upstream_status", None)})
            if getattr(error, "uploaded_file_id", None):
                self.repository.update(job["id"], {"uploaded_file_id": error.uploaded_file_id})
            return {**self.get(job["id"]), "diagnostic": {"code": "submission_unknown", "message": "Remote acceptance is uncertain; inspect and reconcile, never blindly resubmit."}}
        return self.get(job["id"])

    async def refresh(self, job_id):
        job = self.repository.get(job_id, "job")
        if not job["remote_id"]:
            raise BatchConflict("submission_unknown", "Reconcile the remote batch ID before querying.")
        plan = self.repository.get(job["plan_id"], "plan")
        remote = await self.transport_for(plan["settings"]).retrieve(job["remote_id"])
        if not isinstance(remote, dict) or remote.get("id") != job["remote_id"]:
            raise BatchConflict("remote_identity_conflict", "Remote result belongs to another batch.")
        self.repository.update(job_id, {"remote_status": remote.get("status"),
            "remote_artifact": self.artifacts.put(remote), "usage": remote.get("usage"),
            "request_counts": remote.get("request_counts"), "refreshed_at": time.time()})
        return self.get(job_id)

    async def collect(self, job_id, revalidate=False):
        job = self.repository.get(job_id, "job")
        if job.get("collection_artifact") and not revalidate:
            return {**self.get(job_id), "collection": self.artifacts.get(job["collection_artifact"])}
        if revalidate:
            if job.get("apply_status") != "not_applied":
                raise BatchConflict("revalidation_after_apply_blocked", "Revalidation cannot change already applied output state.")
            if not job.get("remote_artifact"):
                raise BatchConflict("retained_results_required", "Revalidation requires saved raw results; it makes no provider calls.")
        else:
            await self.refresh(job_id)
        job = self.repository.get(job_id, "job")
        if job["remote_status"] not in BATCH_TERMINAL_STATES:
            raise BatchConflict("batch_not_completed", "Wait for a terminal batch before collecting available results.")
        plan = self.repository.get(job["plan_id"], "plan")
        snapshot = self.artifacts.get(plan["source_artifact"])
        _, terms = self._terms(plan["settings"], snapshot["game_id"])
        collection = collect_results(snapshot, self.artifacts.get(plan["requests_artifact"]),
            self.artifacts.get(job["remote_artifact"]), plan["settings"]["target_locale"], terms,
            self.artifacts.get(plan["inherited_artifact"]) if plan.get("inherited_artifact") else {})
        collection["parser_version"] = "batch-collection/v2"
        digest = self.artifacts.put(collection)
        history = list(job.get("collection_history", []))
        if job.get("collection_artifact") and job["collection_artifact"] != digest and job["collection_artifact"] not in history:
            history.append(job["collection_artifact"])
        self.repository.update(job_id, {"collection_artifact": digest,
            "collection_history": history,
            "collection_status": "collected_with_errors" if collection["diagnostics"] else "collected"})
        return {**self.get(job_id), "collection": collection}

    async def retry_plan(self, job_id, custom_ids):
        job = self.repository.get(job_id, "job")
        if not job.get("collection_artifact"):
            raise BatchConflict("collection_required", "Collect and validate before selecting failed requests.")
        collection = self.artifacts.get(job["collection_artifact"])
        selected = set(custom_ids)
        if not selected or len(selected) != len(custom_ids) or not selected.issubset(collection["failed_custom_ids"]):
            raise BatchConflict("invalid_retry_selection", "Retry only unique, explicitly selected failed request IDs.")
        parent = self.repository.get(job["plan_id"], "plan")
        snapshot = self.artifacts.get(parent["source_artifact"])
        await require_current_sources(self.manager, snapshot)
        identifier = "batch_plan_" + uuid.uuid4().hex
        requests = [item for item in self.artifacts.get(parent["requests_artifact"]) if item["custom_id"] in selected]
        entry_ids = {entry_id for item in requests for entry_id in item["entry_ids"]}
        for index, item in enumerate(requests):
            item["custom_id"] = f"{identifier}:{index}"
        for file in snapshot["files"]:
            file["selected"] = bool(entry_ids & {entry["id"] for entry in file["entries"]})
        inherited = collection["translations"]
        body = {**parent, "id": identifier, "parent_job_id": job_id, "created_at": time.time(),
            "expires_at": time.time() + 24 * 3600, "source_artifact": self.artifacts.put(snapshot),
            "requests_artifact": self.artifacts.put(requests), "inherited_artifact": self.artifacts.put(inherited),
            "request_count": len(requests), "entry_count": len(entry_ids), "paid_calls": 0}
        body["fingerprint"] = fingerprint([body["source_artifact"], body["requests_artifact"], body["inherited_artifact"], parent["settings"]])
        return self.repository.put("plan", body)

    async def reconcile(self, job_id, remote_id, approved):
        if not approved:
            raise BatchConflict("approval_required", "Binding an unknown submission requires explicit authorization.")
        job = self.repository.get(job_id, "job")
        if job["remote_id"] or job["submission_state"] != "submission_unknown":
            raise BatchConflict("submission_already_bound", "Only an unknown unbound submission can be reconciled.")
        plan = self.repository.get(job["plan_id"], "plan")
        remote = await self.transport_for(plan["settings"]).retrieve(remote_id)
        expected = {item["custom_id"] for item in self.artifacts.get(plan["requests_artifact"])}
        results = remote.get("results") if isinstance(remote, dict) else None
        actual = [item.get("custom_id") for item in results if isinstance(item, dict)] if isinstance(results, list) else []
        if not isinstance(remote, dict) or remote.get("id") != remote_id or remote.get("status") not in BATCH_TERMINAL_STATES or len(actual) != len(expected) or any(not isinstance(value, str) for value in actual) or set(actual) != expected:
            raise BatchConflict("unverified_remote_binding", "Only a terminal batch with the exact persisted request IDs can be bound.")
        self.repository.update(job_id, {"remote_id": remote_id, "remote_status": remote["status"], "submission_state": "submitted",
                                      "remote_artifact": self.artifacts.put(remote)})
        return self.get(job_id)

    async def apply_plan(self, job_id, selected=None):
        job = self.repository.get(job_id, "job")
        if not job.get("collection_artifact"):
            raise BatchConflict("collection_required", "Collect before planning an apply.")
        plan = self.repository.get(job["plan_id"], "plan")
        journal = await self.apply_service.plan(job, plan, self.artifacts.get(plan["source_artifact"]),
                                                self.artifacts.get(job["collection_artifact"]), selected)
        self.repository.update(job_id, {"ready_apply_plan_id": journal["id"]})
        return {**journal, "allowed_actions": ["apply"], "creates_new_output": True}

    async def apply(self, job_id, apply_plan_id, approved):
        result = await self.apply_service.apply(self.repository.get(job_id, "job"),
            self.repository.get(apply_plan_id, "apply"), approved)
        return self.get(result["id"])
