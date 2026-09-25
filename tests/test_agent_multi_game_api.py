"""Integration coverage for game-aware Agent routes; providers/deployers stay mocked."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.core.agent_service import AgentRegistry
from scripts.core.game_adapters.workflow_bridge import MANIFEST
from scripts.routers import agent as agent_router
from scripts.shared import task_state


@pytest.fixture
def client():
    from scripts.web_server import app

    return TestClient(app)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    registry = AgentRegistry(str(tmp_path / "agent-registry.json"))
    monkeypatch.setattr(agent_router, "agent_registry", registry)
    return registry


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _pz_source(root: Path) -> Path:
    _write(root / "mod.info", "id=agent.fixture\nname=Agent fixture\n")
    _write(root / "media/lua/shared/Translate/EN/UI.json", '{"UI_Title":"Open %1"}')
    return root


def _package(root: Path, game_id: str) -> None:
    if game_id == "project_zomboid":
        metadata = "common/mod.info"
        resource = "common/media/lua/shared/Translate/CH/UI.json"
        content = '{"UI_Title":"打开 %1"}'
    elif game_id == "rimworld":
        metadata = "About/About.xml"
        resource = "Languages/ChineseSimplified/Keyed/UI.xml"
        content = "<LanguageData><Title>打开 {0}</Title></LanguageData>"
    else:
        _write(root / "ChineseSimplified.csv", "key,value\n")
        return
    _write(root / metadata, "<ModMetaData/>" if game_id == "rimworld" else "id=agent.fixture\n")
    _write(root / resource, content)
    _write(root / MANIFEST, json.dumps({
        "schema_version": 1, "game_id": game_id, "source_mod_id": "agent.fixture",
        "files": {resource: {"language": "zh-CN", "source_path": "source.json"}},
    }),
    )


def _project(game_id: str, source: Path | None = None) -> dict:
    return {"project_id": f"project-{game_id}", "name": "API fixture", "game_id": game_id,
            "source_language": "en", "source_path": str(source or "C:/fixture"), "status": "active"}


def test_capabilities_include_detailed_project_zomboid_and_rimworld_support(client):
    response = client.get("/api/agent/capabilities")
    assert response.status_code == 200
    games = {item["id"]: item for item in response.json()["games"]}
    for game_id, expected_format in [
        ("project_zomboid", "restricted literal Lua-table TXT"),
        ("rimworld", "known translatable Defs fields"),
    ]:
        support = games[game_id]["game_support"]
        assert expected_format in support["formats"]
        assert support["runtime_verified"] is False
        assert support["capabilities"]["independent_translation_mod"] is True
        assert support["export_mode"] == "manual_install"


def test_get_game_support_and_explicit_inspect_are_read_only_and_game_aware(
    client, tmp_path, monkeypatch,
):
    source = _pz_source(tmp_path / "source")
    project = _project("project_zomboid", source)

    async def get_project(project_id):
        return project if project_id == project["project_id"] else None

    monkeypatch.setattr(agent_router.project_manager, "get_project", get_project)
    support_response = client.get(f"/api/agent/projects/{project['project_id']}/game-support")
    assert support_response.status_code == 200
    support = support_response.json()
    assert support["game_id"] == "project_zomboid"
    assert support["recognized_resource_count"] == 1
    assert support["recognized_entry_count"] == 1
    assert support["read_only"] is True

    monkeypatch.setattr(agent_router, "_validate_agent_import_path", lambda path: {
        "folder_path": str(source), "localization_file_count": 1,
    })
    inspect_response = client.post("/api/agent/projects/inspect", json={
        "folder_path": str(source), "game_id": "project_zomboid",
        "source_language": "en", "game_version": "42.15",
    })
    assert inspect_response.status_code == 200
    inspected = inspect_response.json()["inspection"]["game_support"]
    assert inspected["requested_game_version"] == "42.15"
    assert inspected["recognized_resource_count"] == 1
    assert inspected["runtime_verified"] is False


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld", "surviving_mars"])
def test_game_export_preview_is_local_and_approve_export_cannot_be_overridden(
    client, tmp_path, monkeypatch, isolated_registry, game_id,
):
    destination = tmp_path / "destination"
    output = destination / f"output-{game_id}"
    _package(output, game_id)
    monkeypatch.setattr(agent_router, "DEST_DIR", str(destination))
    project = _project(game_id)

    async def get_project(project_id):
        return project if project == _project(game_id) else None

    async def validation(_project_id, include_items=False):
        return {"summary": agent_router.AgentValidationSummary(), "items": [], "_raw_items": []}

    monkeypatch.setattr(agent_router.project_manager, "get_project", get_project)
    monkeypatch.setattr(agent_router.project_manager, "log_history_event", async_noop)
    monkeypatch.setattr(agent_router, "_validation_payload", validation)
    job_id = f"export-{game_id}"
    task_state.create_task(job_id, status="completed", fields={
        "project_id": project["project_id"], "output_dirs": [str(output)],
        "agent_job_kind": "translation",
    })
    isolated_registry.record_job(job_id=job_id, project_id=project["project_id"],
        plan_id="plan-fixture", kind="translation", execution_args={})

    preview_response = client.get(f"/api/agent/jobs/{job_id}/export-preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["ready"] is True
    assert preview["output_folder_name"] == output.name
    assert preview["export_mode"] == ("local_files" if game_id == "surviving_mars" else "manual_install")
    assert preview["runtime_verified"] is False
    assert preview["validation_scope"] == "artifact_presence_only"
    assert preview["requires_approval"] is False
    assert preview["target_path"] is None
    assert preview["allowed_actions"] == ["inspect_local_output"]

    bypass = client.post(f"/api/agent/jobs/{job_id}/approve-export", json={
        "approved": True, "game_id": "victoria3",
    })
    assert bypass.status_code == 400
    assert bypass.json()["detail"]["code"] == "game_id_mismatch"
    rejected = client.post(f"/api/agent/jobs/{job_id}/approve-export", json={
        "approved": True, "game_id": game_id,
    })
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "unsupported_game_deployment"
    task_state.tasks.pop(job_id, None)


async def async_noop(*_args, **_kwargs):
    return None


def test_incremental_plan_approval_dispatches_existing_runner_and_dry_run_skips_it(
    client, tmp_path, monkeypatch, isolated_registry,
):
    from scripts.routers import projects as projects_router
    from scripts.schemas.project import IncrementalUpdateRequest

    source = _pz_source(tmp_path / "source")
    project = _project("project_zomboid", source)
    calls = {"plan": 0, "incremental": [], "initial": 0}

    async def fake_plan_factory(**kwargs):
        calls["plan"] += 1
        return {
            "execution_args": {
                "project_id": kwargs["project_id"], "target_lang_codes": ["zh-CN"],
                "api_provider": "lm_studio", "model": "local-fixture",
                "translation_context_mode": kwargs["translation_context_mode"],
                "use_main_glossary": kwargs["use_main_glossary"],
            },
            "inspection": {"game_id": "project_zomboid", "source_path": str(source),
                           "source_language": "en"},
        }

    class Readiness:
        async def inspect(self, *_args, **_kwargs):
            return {"status": "ready", "can_start": True, "warnings": []}

    async def get_project(project_id):
        return project if project_id == project["project_id"] else None

    async def get_files(_project_id):
        return []

    async def fake_incremental(project_id, request, _background_tasks):
        assert isinstance(request, IncrementalUpdateRequest)
        calls["incremental"].append((project_id, request.dry_run, request.use_resume,
                                      request.target_lang_codes))
        task_id = "incremental-api-job"
        task_state.create_task(task_id, status="running", fields={
            "project_id": project_id, "agent_job_kind": "incremental_translation", "output_dirs": [],
        })
        return {"task_id": task_id}

    async def validation_payload(_project_id, _task=None, _status=None, **_kwargs):
        return {"summary": agent_router.AgentValidationSummary(available=True),
                "items": [], "_raw_items": []}

    monkeypatch.setattr(agent_router, "create_translation_plan", fake_plan_factory)
    monkeypatch.setattr(agent_router, "translation_context_readiness", Readiness())
    monkeypatch.setattr(agent_router.project_manager, "get_project", get_project)
    monkeypatch.setattr(agent_router.project_manager, "get_project_files", get_files)
    monkeypatch.setattr(agent_router.project_manager, "log_history_event", async_noop)
    monkeypatch.setattr(agent_router.validation_projection, "task_payload", validation_payload)
    monkeypatch.setattr(agent_router, "_validation_payload", validation_payload)
    monkeypatch.setattr(projects_router, "run_incremental_update", fake_incremental)
    monkeypatch.setattr(agent_router, "start_translation_project", AsyncMock())

    planned = client.post("/api/agent/jobs/plan", json={
        "project_id": project["project_id"], "workflow": "incremental",
        "target_lang_codes": ["zh-CN"], "api_provider": "lm_studio",
        "model": "local-fixture", "translation_context_mode": "none",
    })
    assert planned.status_code == 200, planned.text
    plan = planned.json()
    assert plan["translation"]["workflow"] == "incremental"
    assert plan["allowed_actions"] == ["approve_start"]
    assert plan["requires_approval"] is True
    started = client.post("/api/agent/jobs", json={"plan_id": plan["plan_id"], "approved": True})
    assert started.status_code == 200, started.text
    assert calls["incremental"] == [(project["project_id"], False, False, ["zh-CN"])]
    assert agent_router.start_translation_project.await_count == 0

    dry = client.post("/api/agent/jobs/plan", json={
        "project_id": project["project_id"], "workflow": "incremental",
        "target_lang_codes": ["zh-CN"], "api_provider": "lm_studio",
        "model": "local-fixture", "translation_context_mode": "none", "dry_run": True,
    })
    assert dry.status_code == 200, dry.text
    dry_plan = dry.json()
    dry_start = client.post("/api/agent/jobs", json={"plan_id": dry_plan["plan_id"]})
    assert dry_start.status_code == 200, dry_start.text
    dry_job = dry_start.json()
    assert dry_job["kind"] == "dry_run"
    assert len(calls["incremental"]) == 1
    for job_id in ["incremental-api-job", dry_job["job_id"]]:
        task_state.tasks.pop(job_id, None)


def test_incremental_retry_is_rejected_and_job_actions_replan(
    client, isolated_registry, monkeypatch,
):
    project = _project("rimworld")

    async def get_project(_project_id):
        return project

    monkeypatch.setattr(agent_router.project_manager, "get_project", get_project)
    task_state.create_task("failed-incremental-api-job", status="failed", fields={
        "project_id": project["project_id"], "agent_job_kind": "incremental_translation",
        "output_dirs": [],
    })
    isolated_registry.record_job(job_id="failed-incremental-api-job", project_id=project["project_id"],
        plan_id="plan-failed", kind="incremental_translation", execution_args={"workflow": "incremental"})

    retry = client.post("/api/agent/jobs/failed-incremental-api-job/retry")
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "incremental_resume_unsupported"
    job = client.get("/api/agent/jobs/failed-incremental-api-job")
    assert job.status_code == 200
    assert job.json()["allowed_actions"] == ["create_translation_plan"]
    assert job.json()["recovery"]["checkpoint_resume_supported"] is False
    task_state.tasks.pop("failed-incremental-api-job", None)


def test_paradox_export_preview_and_approved_deploy_path_remain_available(
    client, tmp_path, monkeypatch, isolated_registry,
):
    destination = tmp_path / "destination"
    output = destination / "paradox-output"
    _write(output / "localisation/english/test_l_english.yml", "l_english:\n key:0 \"value\"\n")
    target = tmp_path / "game-mod-target"
    monkeypatch.setattr(agent_router, "DEST_DIR", str(destination))
    monkeypatch.setattr(agent_router, "_validate_deploy_target", lambda *_args: target)
    deploy_calls = []
    monkeypatch.setattr(agent_router.deploy_manager.mod_deployer, "deploy_mod",
                        lambda **kwargs: deploy_calls.append(kwargs) or {"status": "success"})
    monkeypatch.setattr(agent_router.project_manager, "get_project", async_project(_project("victoria3")))
    monkeypatch.setattr(agent_router.project_manager, "log_history_event", async_noop)
    monkeypatch.setattr(agent_router, "_validation_payload", async_validation)
    task_state.create_task("paradox-export-job", status="completed", fields={
        "project_id": "project-victoria3", "output_dirs": [str(output)],
    })
    isolated_registry.record_job(job_id="paradox-export-job", project_id="project-victoria3",
        plan_id="plan-v3", kind="translation", execution_args={})

    preview = client.get("/api/agent/jobs/paradox-export-job/export-preview")
    assert preview.status_code == 200
    assert preview.json()["requires_approval"] is True
    assert preview.json()["output_folder_name"] == output.name
    approved = client.post("/api/agent/jobs/paradox-export-job/approve-export", json={
        "approved": True, "game_id": "victoria3",
    })
    assert approved.status_code == 200, approved.text
    assert len(deploy_calls) == 1
    assert deploy_calls[0]["game_id"] == "victoria3"
    task_state.tasks.pop("paradox-export-job", None)


def async_project(project: dict):
    async def get_project(_project_id):
        return project
    return get_project


async def async_validation(_project_id, include_items=False):
    return {"summary": agent_router.AgentValidationSummary(), "items": [], "_raw_items": []}
