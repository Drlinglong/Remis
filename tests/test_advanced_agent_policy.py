"""Unfinished workflows cannot leak through discovery or alternate Batch paths."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.advanced_agent_policy import EXPERIMENTAL_FLAGS, project_experimental_capabilities
from scripts.core.agent_batch_service import AgentBatchService
from scripts.core.batch_repository import BatchConflict
from scripts.core.services.agent_capabilities_service import advanced_capabilities
from scripts.routers import agent_batch, agent_localization_quality, agent_mars_base_patch
from scripts.routers.advanced_agent_policy import include_advanced_router


@pytest.fixture(autouse=True)
def disabled_by_default(monkeypatch):
    for flag in EXPERIMENTAL_FLAGS.values():
        monkeypatch.delenv(flag, raising=False)


def app_with_advanced_routes():
    app = FastAPI()
    for module in (agent_batch, agent_localization_quality, agent_mars_base_patch):
        include_advanced_router(app, module.router)
    def unexpected_storage():
        raise AssertionError("Disabled routes must reject before database/transport construction")
    app.dependency_overrides[agent_batch.get_batch_service] = unexpected_storage
    return app


@pytest.mark.parametrize("path", ["/translation-trials", "/localization-reviews",
                                  "/terminology-coverage/scans", "/mars-base-patch/plans/x"])
def test_default_denial_precedes_storage_and_is_absent_from_openapi(path):
    app = app_with_advanced_routes()
    method = "post" if path == "/translation-trials" else "get"
    response = getattr(TestClient(app), method)("/api/agent" + path)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "experimental_feature_disabled"
    assert not any(key.startswith("/api/agent" + path.split("/scans")[0].split("/plans")[0])
                   for key in app.openapi()["paths"])


def test_default_capabilities_hide_experiments_but_keep_mature_advanced_apis():
    result = project_experimental_capabilities(advanced_capabilities())
    for feature in EXPERIMENTAL_FLAGS:
        assert result[feature]["supported"] is False
        assert "base_url" not in result[feature]
    for feature in ("batch_jobs", "chinese_conversion"):
        assert result[feature]["supported"] is True
        assert result[feature]["audience"] == "advanced_agent"
        assert result[feature]["gui"] is False


@pytest.mark.parametrize("feature,flag", list(EXPERIMENTAL_FLAGS.items()))
def test_individual_opt_in_projects_to_capabilities_and_discovery(monkeypatch, feature, flag):
    monkeypatch.setenv(flag, "1")
    result = project_experimental_capabilities(advanced_capabilities())
    assert result[feature]["supported"] is True and result[feature]["opt_in_flag"] == flag
    for other in EXPERIMENTAL_FLAGS.keys() - {feature}:
        assert result[other]["supported"] is False
    paths = app_with_advanced_routes().openapi()["paths"]
    prefix = result[feature]["base_url"]
    assert any(path.startswith(prefix) for path in paths)


def test_opt_in_route_executes_while_other_experiments_remain_denied(monkeypatch):
    monkeypatch.setenv("REMIS_ENABLE_LOCALIZATION_REVIEWS", "true")
    app = app_with_advanced_routes()
    service = SimpleNamespace(get=lambda identifier: {"id": identifier})
    app.dependency_overrides[agent_localization_quality.review_service] = lambda: service
    client = TestClient(app)
    response = client.get("/api/agent/localization-reviews/test")
    assert response.status_code == 200 and response.json() == {"id": "test"}
    assert client.get("/api/agent/terminology-coverage/scans").status_code == 403


@pytest.mark.asyncio
async def test_immediate_plan_cannot_bypass_policy_through_batch_service():
    service = object.__new__(AgentBatchService)
    with pytest.raises(BatchConflict) as raised:
        await service.plan(SimpleNamespace(execution_mode="immediate"))
    assert raised.value.code == "experimental_feature_disabled"


@pytest.mark.asyncio
async def test_persisted_immediate_plan_cannot_bypass_policy_at_submission():
    service = object.__new__(AgentBatchService)
    service.repository = SimpleNamespace(get=lambda *args: {"execution_mode": "immediate"})
    with pytest.raises(BatchConflict) as raised:
        await service.start(SimpleNamespace(approved=True, plan_id="existing"))
    assert raised.value.code == "experimental_feature_disabled"
