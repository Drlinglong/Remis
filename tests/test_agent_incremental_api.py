"""Exercise provider-free previews and the approval-to-new-source connection."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from scripts.core.agent_service import AgentRegistry
from scripts.core.services import agent_incremental_preview_service as preview_service
from scripts.routers import agent as agent_router
from scripts.shared import task_state


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    from scripts.web_server import app

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "ModTexts.csv").write_text("ID,Text,Translation,VoiceActor,Context\n1,Old,,,\n", encoding="utf-8")
    (new / "ModTexts.csv").write_text("ID,Text,Translation,VoiceActor,Context\n1,New,,,\n2,Added,,,\n", encoding="utf-8")
    project = {"project_id": "incremental-fixture", "name": "Fixture", "game_id": "surviving_mars",
               "source_language": "en", "source_path": str(old)}
    monkeypatch.setattr(agent_router.project_manager, "get_project", AsyncMock(return_value=project))
    monkeypatch.setattr(agent_router.project_manager, "get_project_files", AsyncMock(return_value=[]))
    monkeypatch.setattr(agent_router.project_manager, "log_history_event", AsyncMock())
    monkeypatch.setattr(preview_service.IncrementalArchiveService, "get_language_entries",
                        lambda *_: [{"file_path": "ModTexts.csv", "key": "1", "original": "Old",
                                    "translation": "旧译文"}])
    monkeypatch.setattr(agent_router, "agent_registry", AgentRegistry(str(tmp_path / "registry.json")))
    return TestClient(app), project, new


def test_provider_free_preview_and_incremental_dry_job(scenario, monkeypatch):
    client, project, new = scenario
    provider = AsyncMock(side_effect=AssertionError("Preview must not plan a provider call"))
    monkeypatch.setattr(agent_router, "create_translation_plan", provider)
    body = {"custom_source_path": str(new), "target_lang_codes": ["zh-CN"]}
    response = client.post(f"/api/agent/projects/{project['project_id']}/incremental-preview", json=body)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["summary"] == dict(total=2, new=1, changed=1, unchanged=0, deleted=0,
                                     model_submitted=2, review_required=0)
    plan = client.post("/api/agent/jobs/plan", json={**body, "project_id": project["project_id"],
                       "workflow": "incremental", "dry_run": True, "api_provider": "unconfigured"})
    assert plan.status_code == 200, plan.text
    assert plan.json()["translation"]["incremental_preview"]["fingerprint"] == preview["fingerprint"]
    started = client.post("/api/agent/jobs", json={"plan_id": plan.json()["plan_id"]})
    assert started.status_code == 200, started.text
    job_id = started.json()["job_id"]
    try:
        result = client.get(f"/api/agent/jobs/{job_id}").json()["result"]
        assert result["metadata"]["diff_executed"] is True
        assert result["metadata"]["incremental_preview"]["summary"]["model_submitted"] == 2
        assert result["output_paths"] == []
        provider.assert_not_called()
    finally:
        task_state.tasks.pop(job_id, None)


def test_paid_plan_carries_new_path_and_rejects_stale_source(scenario, monkeypatch):
    from scripts.routers import projects as projects_router
    client, project, new = scenario
    inspections = []

    async def plan_factory(**kwargs):
        return {"execution_args": kwargs, "inspection": {
            "game_id": "surviving_mars", "source_path": project["source_path"], "source_language": "en"}}

    class Readiness:
        async def inspect(self, _project_id, _mode, inspection, **_kwargs):
            inspections.append(inspection)
            return {"status": "ready", "can_start": True}

    async def run(project_id, request, background):
        assert request.custom_source_path == str(new)
        assert request.dry_run is False
        assert project_id == project["project_id"]
        task_state.create_task("new-source-job", status="running", fields={
            "project_id": project_id, "agent_job_kind": "incremental_translation"})
        return {"task_id": "new-source-job"}

    runner = AsyncMock(side_effect=run)
    monkeypatch.setattr(agent_router, "create_translation_plan", plan_factory)
    monkeypatch.setattr(agent_router, "translation_context_readiness", Readiness())
    monkeypatch.setattr(projects_router, "run_incremental_update", runner)
    body = {"project_id": project["project_id"], "workflow": "incremental", "custom_source_path": str(new),
            "api_provider": "lm_studio", "model": "fixture", "translation_context_mode": "none",
            "target_lang_codes": ["zh-CN"]}
    planned = client.post("/api/agent/jobs/plan", json=body)
    assert planned.status_code == 200, planned.text
    assert inspections[-1]["source_path"] == str(new)
    plan_id = planned.json()["plan_id"]
    denied = client.post("/api/agent/jobs", json={"plan_id": plan_id})
    assert denied.status_code == 409
    runner.assert_not_called()
    original = (new / "ModTexts.csv").read_text(encoding="utf-8")
    (new / "ModTexts.csv").write_text(original.replace("New", "Changed again"), encoding="utf-8")
    stale = client.post("/api/agent/jobs", json={"plan_id": plan_id, "approved": True})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "incremental_preview_stale"
    runner.assert_not_called()
    fresh = client.post("/api/agent/jobs/plan", json=body).json()
    started = client.post("/api/agent/jobs", json={"plan_id": fresh["plan_id"], "approved": True})
    try:
        assert started.status_code == 200, started.text
        assert runner.await_count == 1
    finally:
        task_state.tasks.pop("new-source-job", None)


def test_reviewed_fingerprint_is_required_to_still_match(scenario):
    client, project, new = scenario
    response = client.post("/api/agent/jobs/plan", json={
        "project_id": project["project_id"], "workflow": "incremental", "custom_source_path": str(new),
        "target_lang_codes": ["zh-CN"], "dry_run": True, "expected_preview_fingerprint": "stale"})
    assert response.status_code == 400
    assert "stale" in response.json()["detail"]["message"]


def test_legacy_task_result_includes_entry_counts_and_details():
    from scripts.core.services.incremental_result_service import build_incremental_task_result
    fields = {"file_summaries": [{"dirty_entries": [{"key": "7", "status": "new"}]}],
              "warning_count": 0, "source_advancement": {}, "context": {}}
    result = build_incremental_task_result("p", fields, [], [], {"total": 171, "new": 5,
                                           "changed": 1, "unchanged": 165})
    assert result["metadata"]["entry_summary"]["new"] == 5
    assert result["metadata"]["file_summaries"][0]["dirty_entries"][0]["key"] == "7"
    assert result["summary"].startswith("5 new, 1 changed, 165 unchanged")
