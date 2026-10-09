import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from scripts.core.batch_artifacts import BatchArtifacts, fingerprint
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.openrouter_batch_transport import OpenRouterBatchTransport


TEST_KEY = "TEST-ONLY-never-real-key"
UPSTREAM_ECHO = "TEST-ONLY upstream echoed this private payload"


def make_plan(*, plan_id="plan-1", project_id="project-1", item="entry-1"):
    return {
        "id": plan_id,
        "project_id": project_id,
        "fingerprint": fingerprint({"item": item, "locale": "zh-CN"}),
    }


def test_reserve_survives_sqlite_restart_and_same_key_returns_original_job(tmp_path):
    db_path = tmp_path / "batch.sqlite3"
    plan = make_plan()

    first_job, created = BatchRepository(db_path).reserve(plan, "request-1")
    restarted_job, recreated = BatchRepository(db_path).reserve(plan, "request-1")

    assert created is True
    assert recreated is False
    assert restarted_job == first_job
    assert restarted_job["submission_state"] == "submission_unknown"


def test_reserve_rejects_same_key_with_different_fingerprint(tmp_path):
    repository = BatchRepository(tmp_path / "batch.sqlite3")
    repository.reserve(make_plan(item="first"), "request-1")

    with pytest.raises(BatchConflict) as caught:
        repository.reserve(make_plan(item="changed"), "request-1")

    assert caught.value.code == "idempotency_conflict"
    assert caught.value.status == 409


def test_reserve_rejects_same_plan_with_a_new_idempotency_key(tmp_path):
    repository = BatchRepository(tmp_path / "batch.sqlite3")
    repository.reserve(make_plan(), "request-1")

    with pytest.raises(BatchConflict) as caught:
        repository.reserve(make_plan(), "request-2")

    assert caught.value.code == "plan_already_submitted"
    assert caught.value.status == 409


def test_concurrent_reserve_has_only_one_creator(tmp_path):
    repository = BatchRepository(tmp_path / "batch.sqlite3")
    plan = make_plan()
    start = Barrier(2)

    def reserve():
        start.wait(timeout=5)
        return repository.reserve(plan, "request-1")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: reserve(), range(2)))

    jobs = [job for job, _created in outcomes]
    created_flags = [created for _job, created in outcomes]
    assert sorted(created_flags) == [False, True]
    assert jobs[0] == jobs[1]


def test_crash_after_intent_record_does_not_make_submission_retryable(tmp_path):
    db_path = tmp_path / "batch.sqlite3"
    plan = make_plan()

    # Process stops after durable reservation and before it can call HTTP.
    job, created = BatchRepository(db_path).reserve(plan, "request-1")
    assert created is True
    assert job["submission_state"] == "submission_unknown"

    recovered, created_after_restart = BatchRepository(db_path).reserve(plan, "request-1")

    assert created_after_restart is False
    assert recovered["id"] == job["id"]
    assert recovered["submission_state"] == "submission_unknown"


def test_artifacts_are_content_addressed_and_tampering_is_rejected(tmp_path):
    artifacts = BatchArtifacts(tmp_path / "artifacts")
    value = {"plan": "immutable", "entries": ["a", "b"]}

    digest = artifacts.put(value)
    assert artifacts.put(value) == digest
    assert artifacts.get(digest) == value

    changed_digest = artifacts.put({"plan": "immutable", "entries": ["a", "c"]})
    assert changed_digest != digest
    assert artifacts.get(digest) == value

    artifact_path = artifacts.path(digest)
    artifact_path.write_text('{"tampered":true}', encoding="utf-8")
    with pytest.raises(BatchConflict) as caught:
        artifacts.get(digest)
    assert caught.value.code == "artifact_integrity_error"


def test_artifact_path_rejects_non_digest_and_traversal_values(tmp_path):
    artifacts = BatchArtifacts(tmp_path / "artifacts")

    for invalid_id in ("../outside", "..", "g" * 64, "a" * 63):
        with pytest.raises(BatchConflict) as caught:
            artifacts.path(invalid_id)
        assert caught.value.code == "invalid_artifact_id"


@pytest.mark.asyncio
async def test_transport_posts_ordered_requests_once_with_mock_transport():
    observed = []

    def handler(request):
        observed.append(request)
        return httpx.Response(202, json={"id": "remote-test"})

    client_factory = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = OpenRouterBatchTransport(lambda: TEST_KEY, client_factory)
    payload = {
        "requests": [{"custom_id": "entry-1"}],
        "provider": {"order": ["endpoint-a"]},
        "model": "provider/model",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
    }

    response = await transport.submit(payload)

    assert response == {"id": "remote-test"}
    assert len(observed) == 1
    request = observed[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/batches"
    assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert list(json.loads(request.content)) == [
        "endpoint", "model", "provider", "completion_window", "requests"
    ]
    assert list(json.loads(request.content))[-1] == "requests"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "upstream_error"])
async def test_transport_failures_are_sanitized_and_not_retried(failure):
    observed = []

    def handler(request):
        observed.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(f"Bearer {TEST_KEY}; {UPSTREAM_ECHO}", request=request)
        return httpx.Response(503, text=f"Bearer {TEST_KEY}; {UPSTREAM_ECHO}")

    transport = OpenRouterBatchTransport(
        lambda: TEST_KEY,
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(BatchConflict) as caught:
        await transport.submit({"requests": [{"custom_id": "entry-1"}]})

    assert caught.value.code == (
        "upstream_transport_error" if failure == "timeout" else "upstream_http_error"
    )
    assert TEST_KEY not in str(caught.value)
    assert UPSTREAM_ECHO not in str(caught.value)
    assert len(observed) == 1


@pytest.mark.asyncio
async def test_model_catalog_get_is_anonymous():
    observed = []

    def handler(request):
        observed.append(request)
        return httpx.Response(200, json={"data": {"endpoints": [{"name": "test"}]}})

    def forbidden_key_lookup():
        pytest.fail("model catalog lookup must not resolve an API key")

    transport = OpenRouterBatchTransport(
        forbidden_key_lookup,
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await transport.model_endpoints("provider/model")

    assert result == {"endpoints": [{"name": "test"}]}
    assert len(observed) == 1
    assert observed[0].method == "GET"
    assert "authorization" not in observed[0].headers
