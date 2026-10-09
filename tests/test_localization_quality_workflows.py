import json

import pytest

from scripts.core.batch_repository import BatchConflict
from scripts.core.localization_quality_checks import check_quality
from scripts.core.localization_review_collection import collect_reviews, parse_review
from scripts.core.localization_review_prompts import build_review_requests
from scripts.core.localization_review_runner import LocalizationReviewRunner
from scripts.core.localization_review_service import LocalizationReviewService
from scripts.core.quality_reference import reference_table
from scripts.core.terminology_coverage import scan_coverage
from scripts.schemas.agent_batch import BatchPlanRequest, BatchStartRequest
from scripts.schemas.localization_quality import LocalizationReviewPlanRequest, ReviewStartRequest
from tests.test_agent_batch_workflow import batch_environment
from tests.test_native_openai_trials import FakeNativeTransport, response
from scripts.core.immediate_trial_service import ImmediateTrialService
from scripts.core.openai_batch_transport import normalize_response


def review_result(value):
    return {"custom_id": "request-1", "response": {"status_code": 200,
        "body": {"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}]}}}


def entry(identifier="e-1"):
    return {"id": identifier, "key": "123", "source": "<em>Asteroid</em>",
            "candidate": "小<em>行星</em>", "context": "source.csv:1 BuildingTemplate Asteroid display_name", "reference": "小行星"}


def test_review_sends_complete_tokens_but_sparse_short_labels_and_no_gold_issue_hints():
    settings = {"group_size": 20, "max_group_chars": 40000, "target_locale": "zh-TW", "reference_locale": "zh-CN",
                "style_guide": "", "model": "gpt-6-luna", "reasoning": {"mode": "pro", "effort": "max"}}
    requests = build_review_requests("plan", [entry()], settings, [])
    item = requests[0]
    data = json.loads(item["body"]["input"][1]["content"])
    assert data["entries"][0]["id"] == "001"
    assert data["entries"][0]["source"] == "<em>Asteroid</em>"
    assert "candidate_checks" not in data["entries"][0]
    assert item["entry_labels"] == {"001": "e-1"}
    assert item["body"]["reasoning"] == {"mode": "pro", "effort": "max"}
    assert "max_output_tokens" not in item["body"]
    schema = item["body"]["text"]["format"]["schema"]
    assert schema["required"] == ["findings"]
    assert schema["$defs"]["ReviewFinding"]["properties"]["entry_label"]["enum"] == ["001"]


def test_sparse_no_issue_is_not_certification_and_missing_request_is_unreviewed():
    requests = [{"custom_id": "request-1", "entry_ids": ["e-1"], "entry_labels": {"001": "e-1"}},
                {"custom_id": "request-2", "entry_ids": ["e-2"], "entry_labels": {"001": "e-2"}}]
    report = collect_reviews([entry(), entry("e-2")], requests, {"results": [review_result({"findings": []})]}, [])
    assert report["reviewed_count"] == 1
    assert report["reviews"]["e-1"]["status"] == "no_reported_issue"
    assert "e-2" not in report["reviews"]
    assert report["diagnostics"] == [{"custom_id": "request-2", "code": "missing_result"}]
    assert report["automatic_apply"] is False


def test_review_rejects_foreign_ids_and_ambiguous_edits_without_overwriting_candidate():
    finding = {"entry_label": "999", "category": "format", "severity": "minor", "confidence": "high",
               "explanation": "Split emphasis", "edits": [{"find": "行星", "replace": "小行星"}]}
    assert parse_review(review_result({"findings": [finding]}), 1, {"001": "e-1"}) == "foreign_entry_label"
    finding["entry_label"] = "001"
    finding["edits"] = [{"find": "absent", "replace": "text"}]
    original = entry()
    requests = [{"custom_id": "request-1", "entry_ids": ["e-1"], "entry_labels": {"001": "e-1"}}]
    report = collect_reviews([original], requests, {"results": [review_result({"findings": [finding]})]}, [])
    assert report["reviews"]["e-1"]["edits_applicable"] is False
    assert report["reviews"]["e-1"]["suggested_translation"] is None
    assert original["candidate"] == "小<em>行星</em>"


def test_checks_detect_balanced_count_wrong_structure_and_warn_on_percentage_units_and_split_terms():
    assert any(i["code"] == "emphasis_structure_error" for i in check_quality("<em>A</em>", "</em>A<em>"))
    assert any(i["code"] == "percentage_person_unit_review" and i["severity"] == "warning"
               for i in check_quality("<percent(loss)> Medics", "<percent(loss)> 名醫護人員"))
    terms = [{"concept_id": "asteroid", "source": "Asteroid", "translation": "小行星", "aliases": []}]
    assert any(i["code"] == "terminology_emphasis_scope_review" for i in check_quality("<em>Asteroid</em>", "小<em>行星</em>", terms))
    terms[0]["aliases"] = ["Asteroids"]
    assert any(i["code"] == "terminology_emphasis_scope_review" for i in check_quality(
        "<em>Asteroids</em> and <em>Asteroid</em>", "<em>小行星</em>與小<em>行星</em>", terms))
    assert not any(i["code"] == "terminology_emphasis_scope_review" for i in check_quality(
        "<em>Asteroids</em> and <em>Asteroid</em>", "<em>小行星</em>與<em>小行星</em>", terms))


def test_coverage_finds_same_object_alias_gap_preserves_reference_matching_and_existing_pending_state():
    entries = [{"id": "a", "key": "1", "source": "Power Accumulator", "context": "source.csv:2 BuildingTemplate Battery display_name"},
               {"id": "b", "key": "2", "source": "Power Accumulators", "context": "source.csv:3 BuildingTemplate Battery display_name_pl"}]
    snapshot = {"source_locale": "en", "files": [{"selected": True, "entries": entries}]}
    row = {"entry_id": "term-1", "translations": {"en": "Power Accumulator"}, "variants": {},
        "raw_metadata": {"source_text": "Power Accumulator", "terminology": {"concept_id": "battery", "source_id": "1"}}}
    report = scan_coverage(snapshot, [row], {"2": {"source": "Different English", "translation": "wrong reference"}}, minimum=1)
    plural = next(c for c in report["candidates"] if c["source"] == "Power Accumulators")
    assert plural["official_sc"] is None
    assert plural["status"] == "uncovered"
    assert report["alias_gaps"][0]["concept_id"] == "battery"
    assert plural["archive_evidence"][0]["source_item_id"] == "b"
    assert row["variants"] == {}


def test_coverage_does_not_merge_upgrade_or_specialized_building_into_base_name():
    entries = [{"id": "a", "key": "1", "source": "Bakery", "context": "x.csv:2 BuildingTemplate Bakery display_name"},
               {"id": "b", "key": "2", "source": "Baked Goods", "context": "x.csv:3 BuildingTemplate Bakery display_name"},
               {"id": "c", "key": "3", "source": "Bakeries", "context": "x.csv:4 BuildingTemplate Bakery display_name_pl"}]
    snapshot = {"source_locale": "en", "files": [{"selected": True, "entries": entries}]}
    row = {"entry_id": "term", "translations": {"en": "Bakery"}, "variants": {},
        "raw_metadata": {"terminology": {"concept_id": "bakery", "source_id": "1"}}}
    report = scan_coverage(snapshot, [row], {})
    assert [gap["source"] for gap in report["alias_gaps"]] == ["Bakeries"]


class ReviewTransport(FakeNativeTransport):
    async def complete(self, body):
        self.calls.append(body)
        if self.failure:
            raise BatchConflict("insufficient_quota", "Simulated provider failure")
        return normalize_response(response(json.dumps({"findings": []})))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_review_is_persisted_idempotent_isolated_from_apply_and_survives_service_restart(batch_environment, failure):
    batch = batch_environment["service"]()
    batch.native_transport = FakeNativeTransport()
    translation = await batch.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none"))
    job = await batch.start(BatchStartRequest(plan_id=translation["id"], idempotency_key="translation", approved=True))
    await ImmediateTrialService(batch).run(job["id"])
    original_remote = batch.artifacts.get(batch.repository.get(job["id"])["remote_artifact"])
    batch.native_transport = ReviewTransport(failure)
    service = LocalizationReviewService(batch)
    plan = await service.plan(LocalizationReviewPlanRequest(translation_job_id=job["id"]))
    request = ReviewStartRequest(plan_id=plan["id"], idempotency_key="review", approved=True)
    reviewed = await service.start(request)
    await LocalizationReviewRunner(service).run(reviewed["id"])
    report = service.artifact(reviewed["id"], "report")
    assert report["reviewed_count"] == (0 if failure else 2)
    assert bool(report["diagnostics"]) == failure
    assert batch.artifacts.get(batch.repository.get(job["id"])["remote_artifact"]) == original_remote
    with pytest.raises(BatchConflict):
        batch.get(reviewed["id"])
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = batch.native_transport
    assert restarted.artifact(reviewed["id"], "report") == report
    batch.repository.update(plan["id"], {"expires_at": 0})
    replay = await restarted.start(request)
    await LocalizationReviewRunner(restarted).run(replay["id"])
    assert replay["id"] == reviewed["id"]
    assert len(batch.native_transport.calls) == 1


@pytest.mark.asyncio
async def test_native_batch_review_retrieved_after_restart_without_resubmission(batch_environment):
    batch = batch_environment["service"]()
    batch.native_transport = FakeNativeTransport()
    translation = await batch.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none"))
    job = await batch.start(BatchStartRequest(plan_id=translation["id"], idempotency_key="source", approved=True))
    await ImmediateTrialService(batch).run(job["id"])
    transport = ReviewTransport()
    batch.native_transport = transport
    service = LocalizationReviewService(batch)
    plan = await service.plan(LocalizationReviewPlanRequest(translation_job_id=job["id"], execution_mode="batch"))
    request = ReviewStartRequest(plan_id=plan["id"], idempotency_key="batch-review", approved=True)
    submitted = await service.start(request)
    assert submitted["remote_id"] == "batch-persisted-native"
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = transport
    await restarted.refresh(submitted["id"])
    assert restarted.artifact(submitted["id"], "report")["reviewed_count"] == 2
    assert (await restarted.start(request))["id"] == submitted["id"]
    assert len(transport.calls) == 1


@pytest.mark.parametrize("status", ["failed", "incomplete", "in_progress"])
def test_failed_native_response_with_parseable_json_is_not_reviewed_or_translation_accepted(status):
    from scripts.core.batch_collection import parse_result
    body = response('{"findings":[]}')
    body["status"] = status
    row = {"custom_id": "request-1", "response": {"status_code": 200, "body": normalize_response(body)}}
    expected = "truncated_output" if status == "incomplete" else "remote_failure"
    assert parse_review(row, 1, {"001": "e-1"}) == expected
    report = collect_reviews([entry()], [{"custom_id": "request-1", "entry_ids": ["e-1"], "entry_labels": {"001": "e-1"}}],
        {"results": [row]}, [])
    assert report["reviewed_count"] == 0
    assert report["reviews"] == {}
    body["output"][0]["content"][0]["text"] = '{"translations":{"e-1":"譯文"}}'
    row["response"]["body"] = normalize_response(body)
    assert parse_result(row, 1, ["e-1"]) == expected


def test_review_history_and_coverage_are_discoverable_with_bounded_project_pagination(tmp_path):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from scripts.core.batch_repository import BatchRepository
    from scripts.routers.agent_localization_quality import router, coverage_service, review_service
    repository = BatchRepository(tmp_path / "ledger.sqlite")
    repository.put("coverage", {"id": "scan-one", "project_id": "p1", "summary": {"entry_count": 1}})
    repository.put("coverage", {"id": "scan-two", "project_id": "p2", "summary": {"entry_count": 2}})
    job = {"id": "review-one", "project_id": "p1", "submission_state": "submitted", "remote_status": "completed"}
    repository.put("review_job", job)
    repository.put("job", {"id": "translation-one", "project_id": "p1"})
    batch = SimpleNamespace(repository=repository)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[coverage_service] = lambda: SimpleNamespace(batch=batch)
    app.dependency_overrides[review_service] = lambda: LocalizationReviewService(batch)
    with TestClient(app) as client:
        scans = client.get("/api/agent/terminology-coverage/scans?project_id=p1").json()
        assert [r["id"] for r in scans["scans"]] == ["scan-one"]
        reviews = client.get("/api/agent/localization-reviews?project_id=p1").json()
        assert [r["id"] for r in reviews["jobs"]] == ["review-one"]
        assert client.get("/api/agent/localization-reviews?project_id=p2").json()["jobs"] == []
        assert client.get("/api/agent/terminology-coverage/scans?limit=1&offset=1").json()["scans"][0]["id"] == "scan-one"
        assert client.get("/api/agent/localization-reviews?limit=101").status_code == 422
        assert client.get("/api/agent/terminology-coverage/scans?offset=-1").status_code == 422


@pytest.mark.asyncio
async def test_expired_review_reports_partial_coverage_and_preserves_remote_status_after_restart(batch_environment):
    batch = batch_environment["service"]()
    batch.native_transport = FakeNativeTransport()
    translation = await batch.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none"))
    source = await batch.start(BatchStartRequest(plan_id=translation["id"], idempotency_key="source", approved=True))
    await ImmediateTrialService(batch).run(source["id"])
    transport = ReviewTransport()
    batch.native_transport = transport
    service = LocalizationReviewService(batch)
    plan = await service.plan(LocalizationReviewPlanRequest(translation_job_id=source["id"], execution_mode="batch", group_size=1))
    job = await service.start(ReviewStartRequest(plan_id=plan["id"], idempotency_key="partial-review", approved=True))
    transport.remote["status"] = "expired"
    transport.remote["results"] = transport.remote["results"][:1]
    restarted = LocalizationReviewService(batch_environment["service"]())
    restarted.batch.native_transport = transport
    status = await restarted.refresh(job["id"])
    assert status["remote_status"] == "expired"
    assert status["collection_status"] == "collected_with_errors"
    report = restarted.artifact(job["id"], "report")
    assert report["reviewed_count"] == 1
    assert report["expected_count"] == 2
    assert len(report["failed_custom_ids"]) == 1
    assert len(transport.calls) == 2


def test_archive_bridge_preserves_same_spelling_object_evidence_and_existing_confirmed_decisions():
    from scripts.core.terminology_candidate_bridge import persist_coverage_candidates
    from scripts.core.neologism_manager import Candidate
    entries = [{"id": "e1", "key": "1", "source": "Factory"}, {"id": "e2", "key": "2", "source": "Factory"}]
    snapshot = {"source_locale": "en", "files": [{"selected": True, "relative_path": "names.csv", "entries": entries}]}
    candidates = [{"candidate_id": "c" + e["id"], "source": "Factory", "examples": [{"entry_id": e["id"], "source_id": e["key"]}]} for e in entries]

    class Store:
        values = []
        def load_candidates(self, project_id):
            return self.values
        def save_candidates(self, project_id, values):
            self.values = values

    store = Store()
    result = persist_coverage_candidates(store, "project", candidates, snapshot, "zh-TW")
    assert result["new_terms"] == 1
    assert len(store.values[0].suggestion_variants) == 2
    assert {e["source_item_id"] for v in store.values[0].suggestion_variants for e in v["evidence"]} == {"e1", "e2"}
    pending = store.values[0]
    pending.suggestion, pending.reasoning, pending.confidence = "待審譯名", "Existing model rationale", 0.8
    old_variant = {"variant_id": "older", "suggestion": "待審譯名", "evidence": [{"source_item_id": "older-source"}]}
    pending.suggestion_variants.append(old_variant)
    pending.context_snippets.append("older context")
    persist_coverage_candidates(store, "project", candidates[:1], snapshot, "zh-TW")
    assert store.values[0].suggestion == "待審譯名"
    assert store.values[0].reasoning == "Existing model rationale"
    assert store.values[0].confidence == 0.8
    assert "older context" in store.values[0].context_snippets
    assert old_variant in store.values[0].suggestion_variants
    assert len(store.values[0].suggestion_variants) == 3
    confirmed = Candidate(id="fixed", project_id="project", original="Factory", context_snippets=[],
        suggestion="已確認譯名", reasoning="Human decision", status="approved")
    store.values = [confirmed]
    repeated = persist_coverage_candidates(store, "project", candidates, snapshot, "zh-TW")
    assert repeated["duplicate_terms"] == 1
    assert store.values[0].suggestion == "已確認譯名"
    assert store.values[0].status == "approved"


@pytest.mark.asyncio
async def test_native_failed_review_saves_raw_response_and_stops_remaining_paid_requests(batch_environment):
    batch = batch_environment["service"]()
    batch.native_transport = FakeNativeTransport()
    plan = await batch.plan(BatchPlanRequest(project_id="project-mars", file_ids=["source-1"],
        api_provider="openai", execution_mode="immediate", model="gpt-6-luna", target_locale="zh-TW",
        game_language_slot="Schinese", translation_context_mode="none"))
    source = await batch.start(BatchStartRequest(plan_id=plan["id"], idempotency_key="source", approved=True))
    await ImmediateTrialService(batch).run(source["id"])

    class FailedReview(ReviewTransport):
        async def complete(self, body):
            self.calls.append(body)
            value = response('{"findings":[]}')
            value.update(status="failed", error={"code": "server_error"})
            return normalize_response(value)

    batch.native_transport = FailedReview()
    service = LocalizationReviewService(batch)
    plan = await service.plan(LocalizationReviewPlanRequest(translation_job_id=source["id"], group_size=1))
    job = await service.start(ReviewStartRequest(plan_id=plan["id"], idempotency_key="failed-review", approved=True))
    await LocalizationReviewRunner(service).run(job["id"])
    assert len(batch.native_transport.calls) == 1
    assert service.artifact(job["id"], "saved_results")["results"][0]["response"]["body"]["status"] == "failed"
    report = service.artifact(job["id"], "report")
    assert report["reviewed_count"] == 0
    assert {r["code"] for r in report["diagnostics"]} == {"remote_failure", "missing_result"}


@pytest.fixture(autouse=True)
def enable_test_experiments(monkeypatch):
    monkeypatch.setenv("REMIS_ENABLE_TRANSLATION_TRIALS", "1")
    monkeypatch.setenv("REMIS_ENABLE_LOCALIZATION_REVIEWS", "1")
    monkeypatch.setenv("REMIS_ENABLE_TERMINOLOGY_COVERAGE", "1")
