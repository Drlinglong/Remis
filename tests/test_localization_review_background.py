import json

import pytest

from scripts.core.batch_repository import BatchConflict
from scripts.core.immediate_trial_service import ImmediateTrialService
from scripts.core.localization_review_service import LocalizationReviewService
from scripts.schemas.agent_batch import BatchPlanRequest, BatchStartRequest
from scripts.schemas.localization_quality import LocalizationReviewPlanRequest, ReviewResponseReconcileRequest, ReviewStartRequest
from tests.test_agent_batch_workflow import batch_environment
from tests.test_native_openai_trials import FakeNativeTransport, response


class BackgroundTransport(FakeNativeTransport):
    def __init__(self, lost_ack=False):
        super().__init__()
        self.created, self.responses, self.downloaded = [], {}, []
        self.lost_ack = lost_ack
        self.completed = set()

    async def start_background_response(self, body):
        assert body["background"] is True and body["store"] is True
        self.created.append(body)
        identifier = f"resp-{len(self.created)}"
        self.responses[identifier] = {"id": identifier, "status": "queued", "output": [], "background": True, "store": True,
                                      "metadata": body["metadata"], "reasoning": body["reasoning"]}
        if self.lost_ack:
            raise BatchConflict("upstream_transport_error", "Simulated lost acknowledgement")
        return dict(self.responses[identifier])

    async def retrieve_response(self, identifier):
        self.downloaded.append(identifier)
        original = self.responses[identifier]
        if identifier in self.completed:
            return {**response('{"findings":[]}'), "id": identifier, "background": True, "store": True, "metadata": original["metadata"],
                    "reasoning": original["reasoning"]}
        return dict(original)

    async def submit(self, payload):
        raise AssertionError("Ordinary background review must never call the Batch endpoint")

    async def complete(self, body):
        raise AssertionError("Ordinary background review must never wait on a long foreground connection")


async def prepared(batch_environment, transport):
    batch = batch_environment["service"]()
    batch.native_transport = FakeNativeTransport()
    source_plan = await batch.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none"))
    source = await batch.start(BatchStartRequest(plan_id=source_plan["id"], idempotency_key="source", approved=True))
    await ImmediateTrialService(batch).run(source["id"])
    batch.native_transport = transport
    service = LocalizationReviewService(batch)
    plan = await service.plan(LocalizationReviewPlanRequest(translation_job_id=source["id"], execution_mode="background", group_size=1))
    request = ReviewStartRequest(plan_id=plan["id"], idempotency_key="ordinary-background-review", approved=True)
    return batch, service, plan, request


@pytest.mark.asyncio
async def test_ordinary_background_review_survives_restart_and_only_gets_persisted_response_ids(batch_environment):
    transport = BackgroundTransport()
    batch, service, plan, request = await prepared(batch_environment, transport)
    job = await service.start(request)
    assert job["execution_mode"] == "background"
    assert job["remote_id"] is None
    assert job["remote_status"] == "running"
    assert job["shutdown_recovery_ready"] is True
    assert [r["response_id"] for r in job["response_submissions"].values()] == ["resp-1", "resp-2"]
    assert len(transport.created) == 2
    assert all(body["reasoning"] == {"mode": "pro", "effort": "max"} for body in transport.created)
    original = batch.artifacts.get(plan["entries_artifact"])
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = transport
    replay = await restarted.start(request)
    assert replay["id"] == job["id"]
    assert len(transport.created) == 2
    transport.completed = {"resp-1", "resp-2"}
    finished = await restarted.refresh(job["id"])
    assert finished["collection_status"] == "collected"
    assert restarted.artifact(job["id"], "report")["reviewed_count"] == 2
    assert restarted.artifact(job["id"], "entries") == original
    assert transport.downloaded == ["resp-1", "resp-2"]
    await restarted.refresh(job["id"])
    assert transport.downloaded == ["resp-1", "resp-2"]  # Terminal responses are retained locally.
    assert finished["usage"]["reasoning_tokens"] == 12


@pytest.mark.asyncio
async def test_background_partial_results_do_not_certify_pending_entries(batch_environment):
    transport = BackgroundTransport()
    _, service, _, request = await prepared(batch_environment, transport)
    job = await service.start(request)
    transport.completed = {"resp-1"}
    partial = await service.refresh(job["id"])
    assert partial["remote_status"] == "running"
    assert partial["collection_status"] == "partial"
    report = service.artifact(job["id"], "report")
    assert report["reviewed_count"] == 1 and report["expected_count"] == 2
    assert len(report["reviews"]) == 1


@pytest.mark.asyncio
async def test_lost_background_ack_is_not_resubmitted_and_reconciliation_requires_exact_metadata(batch_environment):
    transport = BackgroundTransport(lost_ack=True)
    batch, service, plan, request = await prepared(batch_environment, transport)
    job = await service.start(request)
    assert job["submission_state"] == "submission_unknown"
    assert service.artifact(job["id"], "saved_results")["in_flight_response_may_be_unknown"] is True
    assert len(transport.created) == 1
    assert (await service.start(request))["id"] == job["id"]
    assert len(transport.created) == 1
    custom_id = batch.artifacts.get(plan["requests_artifact"])[0]["custom_id"]
    transport.responses["resp-foreign"] = {**transport.responses["resp-1"], "id": "resp-foreign", "metadata": {"other": "plan"}}
    with pytest.raises(BatchConflict) as caught:
        await service.reconcile_response(job["id"], ReviewResponseReconcileRequest(custom_id=custom_id, response_id="resp-foreign", approved=True))
    assert caught.value.code == "unverified_remote_binding"
    transport.completed = {"resp-1"}
    recovered = await service.reconcile_response(job["id"], ReviewResponseReconcileRequest(custom_id=custom_id, response_id="resp-1", approved=True))
    assert recovered["submission_state"] == "partially_submitted"
    assert service.artifact(job["id"], "report")["reviewed_count"] == 1
    assert len(transport.created) == 1  # The other request remains explicitly not_submitted.


def test_atomic_response_updates_keep_sibling_ids_and_terminal_results(batch_environment):
    repository = batch_environment["repository"]
    repository.put("review_job", {"id": "review-test", "project_id": "p", "response_submissions": {
        "a": {"state": "not_submitted"}, "b": {"state": "not_submitted"}}})
    repository.update_review_response("review-test", "a", {"state": "accepted", "response_id": "resp-a", "response_status": "queued"})
    repository.update_review_response("review-test", "b", {"state": "accepted", "response_id": "resp-b", "response_status": "queued"})
    repository.update_review_response("review-test", "a", {"response_status": "completed", "response_artifact": "terminal"})
    repository.update_review_response("review-test", "a", {"response_status": "queued", "response_artifact": "stale"})
    records = repository.get("review-test")["response_submissions"]
    assert records["b"]["response_id"] == "resp-b"
    assert records["a"]["response_artifact"] == "terminal"
    with pytest.raises(BatchConflict):
        repository.update_review_response("review-test", "a", {"response_id": "resp-other"})


def test_unknown_status_or_nonstored_background_response_cannot_promise_shutdown_recovery():
    from scripts.core.localization_review_background import background_recovery_ready
    record = {"state": "accepted", "response_status": "queued", "remote_background": True,
              "remote_store": False, "response_artifact": "saved"}
    job = {"dispatch_finished": True, "response_submissions": {"request": record}}
    assert background_recovery_ready(job) is False
    record.update(remote_store=True, response_status=None)
    assert background_recovery_ready(job) is False
    record.update(response_status="queued")
    assert background_recovery_ready(job) is True


@pytest.mark.asyncio
async def test_last_response_saved_before_process_exit_does_not_leave_permanent_running_state(batch_environment):
    transport = BackgroundTransport()
    batch, service, _, request = await prepared(batch_environment, transport)
    job = await service.start(request)
    batch.repository.update(job["id"], {"dispatch_finished": False, "dispatch_owner": "previous-process"})
    transport.completed = {"resp-1", "resp-2"}
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = transport
    recovered = await restarted.refresh(job["id"])
    assert recovered["dispatch_finished"] is True
    assert recovered["remote_status"] == "completed"
    assert recovered["collection_status"] == "collected"
    assert recovered["shutdown_recovery_ready"] is True
    assert len(transport.created) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("crash_stage", ["after_first_id", "during_second_post"])
async def test_mid_dispatch_process_exit_preserves_unknown_and_unsubmitted_without_sending_again(batch_environment, monkeypatch, crash_stage):
    import scripts.core.localization_review_background as background

    class ProcessExit(BaseException):
        pass

    class InterruptedTransport(BackgroundTransport):
        async def start_background_response(self, body):
            if crash_stage == "during_second_post" and self.created:
                raise ProcessExit()
            return await super().start_background_response(body)

    transport = InterruptedTransport()
    batch, service, _, request = await prepared(batch_environment, transport)
    original = background.save_response
    if crash_stage == "after_first_id":
        def interrupt_after_save(*args):
            original(*args)
            raise ProcessExit()
        monkeypatch.setattr(background, "save_response", interrupt_after_save)
    with pytest.raises(ProcessExit):
        await service.start(request)
    monkeypatch.setattr(background, "save_response", original)
    monkeypatch.setattr(background, "DISPATCH_INSTANCE", "new-process")
    job = batch.repository.list_jobs(kind="review_job")[0]
    transport.completed = {"resp-1"}
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = transport
    recovered = await restarted.refresh(job["id"])
    assert recovered["dispatch_interrupted"] is True
    assert recovered["dispatch_finished"] is True
    assert recovered["shutdown_recovery_ready"] is False
    states = [r["state"] for r in recovered["response_submissions"].values()]
    assert states == ["accepted", "not_submitted" if crash_stage == "after_first_id" else "submission_unknown"]
    assert recovered["remote_status"] == ("completed" if crash_stage == "after_first_id" else "submission_unknown")
    assert restarted.artifact(job["id"], "report")["reviewed_count"] == 1
    assert len(transport.created) == 1
    assert (await restarted.start(request))["id"] == job["id"]
    assert len(transport.created) == 1


@pytest.fixture(autouse=True)
def enable_test_experiments(monkeypatch):
    monkeypatch.setenv("REMIS_ENABLE_TRANSLATION_TRIALS", "1")
    monkeypatch.setenv("REMIS_ENABLE_LOCALIZATION_REVIEWS", "1")
    monkeypatch.setenv("REMIS_ENABLE_TERMINOLOGY_COVERAGE", "1")
