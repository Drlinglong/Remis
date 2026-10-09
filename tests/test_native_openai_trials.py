import json

import httpx
import pytest

from scripts.core.batch_repository import BatchConflict
from scripts.core.immediate_trial_service import ImmediateTrialService
from scripts.core.openai_batch_transport import OpenAIBatchTransport, normalize_response, responses_body
from scripts.schemas.agent_batch import BatchPlanRequest, BatchStartRequest
from tests.test_agent_batch_workflow import batch_environment


def response(text):
    return {"id": "resp-test", "status": "completed", "output": [{"type": "message",
        "content": [{"type": "output_text", "text": text}]}], "usage": {"input_tokens": 8,
        "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 6}}}


def test_responses_conversion_preserves_semantic_tokens_and_explicit_pro_mode():
    body = {"messages": [{"role": "user", "content": "<em>Drones</em> $COUNT$ [scope.name]\nNext"}],
        "reasoning": {"mode": "pro", "effort": "medium"},
        "response_format": {"json_schema": {"name": "translations", "strict": True, "schema": {"type": "object"}}}}
    native = responses_body(body, "gpt-6-luna")
    assert native["input"] == body["messages"]
    assert native["reasoning"] == {"mode": "pro", "effort": "medium"}
    assert native["text"]["format"]["type"] == "json_schema"
    assert "max_output_tokens" not in native


@pytest.mark.asyncio
async def test_native_batch_upload_create_download_and_normalize_reordered_results():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.headers["authorization"] == "Bearer fake-native-key"
        path = request.url.path
        if path == "/v1/files":
            assert b'"url": "/v1/responses"' in request.content
            assert b'"model": "gpt-6-luna"' in request.content
            return httpx.Response(200, json={"id": "file-input"})
        if path == "/v1/batches":
            assert json.loads(request.content) == {"input_file_id": "file-input", "endpoint": "/v1/responses", "completion_window": "24h"}
            return httpx.Response(200, json={"id": "batch-native", "status": "validating"})
        if path == "/v1/batches/batch-native":
            return httpx.Response(200, json={"id": "batch-native", "status": "completed", "output_file_id": "file-output"})
        if path == "/v1/files/file-output/content":
            return httpx.Response(200, text="\n".join(json.dumps({"custom_id": value,
                "response": {"status_code": 200, "body": response(value)}}) for value in ["r2", "r1"]))
        raise AssertionError(path)

    transport = OpenAIBatchTransport(lambda: "fake-native-key", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await transport.submit({"requests": [{"custom_id": "r1", "body": {"model": "gpt-6-luna"}}]})
    completed = await transport.retrieve("batch-native")
    assert [row["custom_id"] for row in completed["results"]] == ["r2", "r1"]
    assert completed["usage"]["output_tokens"] == 20
    assert completed["usage"]["reasoning_tokens"] == 12
    assert completed["results"][0]["response"]["body"]["choices"][0]["message"]["content"] == "r2"
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_native_rejection_sanitizes_error_and_preserves_uploaded_file_identity():
    def handler(request):
        if request.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "file-input"})
        return httpx.Response(400, json={"error": {"message": "fake-secret", "code": "bad_argument"}})
    transport = OpenAIBatchTransport(lambda: "fake-secret", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(BatchConflict) as caught:
        await transport.submit({"requests": [{"custom_id": "r1", "body": {"model": "gpt-6-luna"}}]})
    assert "fake-secret" not in str(caught.value)
    assert caught.value.uploaded_file_id == "file-input"


class FakeNativeTransport:
    def __init__(self, failure=False):
        self.calls = []
        self.failure = failure

    def ensure_configured(self):
        pass

    async def model_endpoints(self, model):
        assert model == "gpt-6-luna"
        return {"id": model}

    async def complete(self, body):
        self.calls.append(body)
        if self.failure:
            raise BatchConflict("insufficient_quota", "Simulated quota rejection")
        data = json.loads(body["input"][1]["content"])
        value = {"translations": {entry["id"]: "火星译文" + entry["key"] for entry in data["entries"]}}
        return normalize_response(response(json.dumps(value, ensure_ascii=False)))

    async def submit(self, payload):
        self.batch_payload = payload
        self.remote = {"id": "batch-persisted-native", "status": "completed", "results": [
            {"custom_id": row["custom_id"], "response": {"status_code": 200, "body": await self.complete(row["body"])}}
            for row in payload["requests"]]}
        return {"id": self.remote["id"], "status": "validating", "input_file_id": "file-persisted-input"}

    async def retrieve(self, remote_id):
        assert remote_id == self.remote["id"]
        return self.remote


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_immediate_native_trial_is_idempotent_and_retains_validation_results(batch_environment, failure):
    service = batch_environment["service"]()
    service.native_transport = FakeNativeTransport(failure)
    plan = await service.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none", group_size=1, reasoning={"mode": "pro"}))
    assert plan["entry_count"] == 2
    assert plan["execution_mode"] == "immediate"
    start = BatchStartRequest(plan_id=plan["id"], idempotency_key="native-test", approved=True)
    job = await service.start(start)
    assert job["dispatch_immediate"] is True
    await ImmediateTrialService(service).run(job["id"])
    finished = service.get(job["id"])
    collection = service.artifacts.get(finished["collection_artifact"])
    assert finished["remote_status"] == "completed"
    assert len(collection["translations"]) == (0 if failure else 2)
    assert bool(collection["diagnostics"]) == failure
    assert len(service.native_transport.calls) == (1 if failure else 2)
    service.repository.update(plan["id"], {"expires_at": 0})
    replay = await service.start(start)
    await ImmediateTrialService(service).run(replay["id"])
    assert replay["id"] == job["id"]
    assert len(service.native_transport.calls) == (1 if failure else 2)
    if not failure:
        apply_plan = await service.apply_plan(job["id"])
        applied = await service.apply(job["id"], apply_plan["id"], True)
        assert applied["apply_status"] == "applied"


@pytest.mark.asyncio
async def test_native_batch_retrieval_after_service_restart_preserves_ids_and_never_resubmits(batch_environment):
    service = batch_environment["service"]()
    native = FakeNativeTransport()
    service.native_transport = native
    plan = await service.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", model="gpt-6-luna", target_locale="zh-TW", game_language_slot="Schinese",
        translation_context_mode="none", reasoning={"mode": "pro"}))
    request = BatchStartRequest(plan_id=plan["id"], idempotency_key="native-restart", approved=True)
    submitted = await service.start(request)
    assert submitted["remote_id"] == "batch-persisted-native"
    restarted = batch_environment["service"]()
    restarted.native_transport = native
    persisted = restarted.get(submitted["id"])
    assert persisted["remote_id"] == submitted["remote_id"]
    collected = await restarted.collect(submitted["id"])
    assert len(collected["collection"]["translations"]) == 2
    assert not collected["collection"]["diagnostics"]
    replay = await restarted.start(request)
    assert replay["id"] == submitted["id"]
    assert len(native.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "expired", "cancelled", "failed"])
async def test_terminal_batch_downloads_partial_output_and_error_files(status):
    calls = []
    good = {"custom_id": "r1", "response": {"status_code": 200, "body": response('{"findings":[]}')}}
    failed = {"custom_id": "r2", "response": None, "error": {"code": "batch_expired"}}

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/batches/batch-partial":
            return httpx.Response(200, json={"id": "batch-partial", "status": status,
                "output_file_id": "file-output", "error_file_id": "file-errors"})
        return httpx.Response(200, text=json.dumps(good if "file-output" in request.url.path else failed))

    transport = OpenAIBatchTransport(lambda: "fake", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    result = await transport.retrieve("batch-partial")
    assert result["status"] == status
    assert [r["custom_id"] for r in result["results"]] == ["r1", "r2"]
    assert result["usage"]["reasoning_tokens"] == 6
    assert set(result["downloaded_files"]) == {"output_file_id", "error_file_id"}
    assert calls == ["/v1/batches/batch-partial", "/v1/files/file-output/content", "/v1/files/file-errors/content"]


@pytest.mark.asyncio
async def test_malformed_download_is_retained_as_raw_evidence_not_valid_output():
    def handler(request):
        if request.url.path == "/v1/batches/batch-invalid":
            return httpx.Response(200, json={"id": "batch-invalid", "status": "completed", "output_file_id": "file-output"})
        return httpx.Response(200, text="{invalid\n[]\n")

    transport = OpenAIBatchTransport(lambda: "fake", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    result = await transport.retrieve("batch-invalid")
    assert result["downloaded_files"]["output_file_id"]["content"] == "{invalid\n[]\n"
    assert all(r["_parse_error"] == "invalid_batch_jsonl" for r in result["results"])


@pytest.mark.asyncio
async def test_expired_translation_collects_valid_partial_results_and_preserves_missing_requests(batch_environment):
    service = batch_environment["service"]()
    native = FakeNativeTransport()
    service.native_transport = native
    plan = await service.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", model="gpt-6-luna", target_locale="zh-TW", game_language_slot="Schinese",
        translation_context_mode="none", group_size=1))
    job = await service.start(BatchStartRequest(plan_id=plan["id"], idempotency_key="partial", approved=True))
    native.remote["status"] = "expired"
    native.remote["results"] = native.remote["results"][:1]
    result = await service.collect(job["id"])
    assert result["remote_status"] == "expired"
    assert len(result["collection"]["translations"]) == 1
    assert len(result["collection"]["failed_custom_ids"]) == 1
    assert result["collection"]["complete_file_ids"] == []
    assert "plan_apply" not in result["allowed_actions"]
    assert len(native.calls) == 2
    from scripts.core.localization_review_service import LocalizationReviewService
    assert len(LocalizationReviewService(service).candidates(job["id"])[3]) == 1


@pytest.fixture(autouse=True)
def enable_test_experiments(monkeypatch):
    monkeypatch.setenv("REMIS_ENABLE_TRANSLATION_TRIALS", "1")
    monkeypatch.setenv("REMIS_ENABLE_LOCALIZATION_REVIEWS", "1")
    monkeypatch.setenv("REMIS_ENABLE_TERMINOLOGY_COVERAGE", "1")
