from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from scripts.core.agent_service import AgentRegistry
from scripts.core.copilot import workflow
from scripts.routers import agent, agent_steam_workshop
from scripts.schemas.agent import AgentJobPlanRequest, AgentJobStartRequest
from scripts.schemas.translation import InitialTranslationRequest
from tests.test_steam_workshop_assets import workshop_client, _cover_payload

SHELL = {"name": "Italian", "code": "custom", "key": "l_english", "folder_prefix": "it-"}


@pytest.mark.parametrize("targets,config", [
    (["custom"], None), (["en"], SHELL), (["custom", "fr"], SHELL),
    (["custom"], {**SHELL, "folder_prefix": "../it-"}),
    (["custom"], {**SHELL, "key": "l_italian"}),
    (["custom"], {**SHELL, "name": " "}),
])
def test_shell_plan_rejects_ambiguous_or_unsafe_identity(targets, config):
    with pytest.raises(ValidationError):
        AgentJobPlanRequest(project_id="p", target_lang_codes=targets, custom_lang_config=config)


@pytest.mark.asyncio
async def test_shell_identity_survives_plan_start_registry_reload_and_retry(tmp_path, monkeypatch):
    registry = AgentRegistry(str(tmp_path / "agent.json"))
    monkeypatch.setattr(agent, "agent_registry", registry)
    monkeypatch.setattr(workflow.project_manager, "get_project", AsyncMock(return_value={
        "project_id": "p", "name": "Demo", "source_language": "en", "game_id": "victoria3",
    }))
    monkeypatch.setattr(workflow.project_manager, "get_project_files", AsyncMock(return_value=[]))
    monkeypatch.setattr(workflow.project_manager, "log_history_event", AsyncMock())
    monkeypatch.setattr(agent, "translation_context_readiness", SimpleNamespace(
        inspect=AsyncMock(return_value={"can_start": True, "status": "ready"}),
    ))
    request = AgentJobPlanRequest(
        project_id="p", target_lang_codes=["custom"], custom_lang_config=SHELL,
        api_provider="lm_studio", model="fixture", translation_context_mode="none",
    )
    plan = await agent.plan_agent_job(request)
    assert plan.translation["custom_lang_config"] == SHELL
    captured = []

    async def start(payload, background):
        assert isinstance(payload, InitialTranslationRequest)
        captured.append(payload.model_dump())
        return {"task_id": "shell-job"}

    monkeypatch.setattr(agent, "start_translation_project", start)
    monkeypatch.setattr(agent.task_state, "update_task", lambda *a, **kw: None)
    monkeypatch.setattr(agent, "_build_job_response", AsyncMock(return_value={"job_id": "shell-job"}))
    await agent.start_agent_job(AgentJobStartRequest(plan_id=plan.plan_id, approved=True), BackgroundTasks())
    assert captured[0]["custom_lang_config"] == SHELL
    restored = AgentRegistry(str(tmp_path / "agent.json"))
    monkeypatch.setattr(agent, "agent_registry", restored)
    assert restored.get_job("shell-job")["execution_args"]["custom_lang_config"] == SHELL
    monkeypatch.setattr(agent.translation_plan, "resolve_agent_retry_checkpoint", lambda *a, **kw: {
        "use_resume": True, "resume_from_task_id": "shell-job", "expected_checkpoint_revision": 2,
    })
    retry = await agent.retry_agent_job("shell-job")
    assert retry.translation["custom_lang_config"] == SHELL
    await agent.start_agent_job(AgentJobStartRequest(plan_id=retry.plan_id, approved=True), BackgroundTasks())
    assert captured[1]["custom_lang_config"] == SHELL
    assert captured[1]["resume_from_task_id"] == "shell-job"


def test_agent_assets_share_product_persistence_and_approval(workshop_client, monkeypatch):
    product_client, service, _ = workshop_client
    app = FastAPI()
    app.include_router(agent_steam_workshop.router)
    with TestClient(app) as client:
        base = "/api/agent/steam-workshop"
        workspace = client.post(base + "/workspaces", json={"name": "Italian Demo"}).json()
        wid = workspace["workspace_id"]
        denied = client.post(f"{base}/workspaces/{wid}/generate-description", json={
            "language": "it", "target_language_name": "Italian", "provider": "openrouter",
            "model": "fixture", "workshop_item_id": "123", "approved": False,
        })
        assert denied.status_code == 409
        assert denied.json()["detail"]["code"] == "approval_required"
        saved = client.post(f"{base}/workspaces/{wid}/versions/description", json={
            "bbcode": "[h1]Traduzione italiana[/h1]", "language": "it",
        })
        assert saved.status_code == 201, saved.text
        vid = saved.json()["version_id"]
        assert product_client.get(f"/api/steam-workshop/versions/{vid}").status_code == 200
        assert client.post(f"{base}/workspaces/{wid}/selections/description", json={"version_id": vid}).status_code == 200
        cover = client.post(f"{base}/workspaces/{wid}/versions/cover", json=_cover_payload())
        assert cover.status_code == 201, cover.text
        assert client.get(f"{base}/versions/{cover.json()['version_id']}/content").content.startswith(b"\x89PNG")
        other = client.post(base + "/workspaces", json={"name": "Other"}).json()["workspace_id"]
        assert client.post(f"{base}/workspaces/{other}/selections/description", json={"version_id": vid}).status_code != 200
        assert client.delete(f"{base}/workspaces/{wid}").status_code == 405
        monkeypatch.setattr(agent_steam_workshop.workbench.description_generation_service,
                            "fetch_source_description", lambda item: "Original description")
        source = client.get(base + "/items/123/description")
        assert source.status_code == 200
        assert len(source.json()["source_description_sha256"]) == 64
        assert client.get(base + "/items/not-an-id/description").status_code == 422


def test_agent_workshop_does_not_return_provider_exception_secrets(monkeypatch):
    def fail(item):
        raise RuntimeError("Authorization: secret-fixture")
    monkeypatch.setattr(agent_steam_workshop.workbench.description_generation_service, "fetch_source_description", fail)
    app = FastAPI()
    app.include_router(agent_steam_workshop.router)
    with TestClient(app) as client:
        response = client.get("/api/agent/steam-workshop/items/123/description")
    assert response.status_code == 502
    assert "secret-fixture" not in response.text
