"""Focused contracts for guided localization readiness and recovery."""

from fastapi import BackgroundTasks, HTTPException

import pytest

from scripts.core.copilot.provider_readiness import ProviderReadinessError
from scripts.core.copilot import provider_readiness
from scripts.routers import copilot as copilot_router
from scripts.schemas.copilot import CopilotWorkflowApprovalRequest


@pytest.mark.asyncio
async def test_readiness_failure_precedes_project_creation(monkeypatch):
    called = False

    async def fail_readiness(_plan_id):
        raise ProviderReadinessError(
            "provider_model_mismatch",
            "The selected model is not available from the configured provider.",
            checks={"provider": "lm_studio", "model": "wrong-model"},
        )

    async def should_not_create_project(_plan_id):
        nonlocal called
        called = True
        raise AssertionError("project creation must not run after readiness failure")

    monkeypatch.setattr(copilot_router, "ensure_localization_provider_ready", fail_readiness)
    monkeypatch.setattr(copilot_router, "approve_and_execute_plan", should_not_create_project)
    with pytest.raises(HTTPException) as exc_info:
        await copilot_router.execute_guided_localization(
            CopilotWorkflowApprovalRequest(plan_id="plan-1"), BackgroundTasks()
        )

    assert called is False
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "provider_model_mismatch"
    assert exc_info.value.detail["retryable"] is True


@pytest.mark.asyncio
async def test_project_created_but_translation_plan_failure_is_recoverable(monkeypatch):
    async def approve_plan(_plan_id):
        return {"project": {"project_id": "project-1", "name": "Demo"}}

    async def fail_translation_plan(**_kwargs):
        raise ValueError("fixture translation setup failed")

    monkeypatch.setattr(copilot_router, "ensure_localization_provider_ready", lambda _id: _ready())
    monkeypatch.setattr(copilot_router, "approve_and_execute_plan", approve_plan)
    monkeypatch.setattr(copilot_router, "get_localization_translation_args", lambda _id: {
        "target_lang_codes": ["zh-CN"],
        "api_provider": "lm_studio",
        "model": "local-model",
    })
    monkeypatch.setattr(copilot_router, "create_translation_plan", fail_translation_plan)

    result = await copilot_router.execute_guided_localization(
        CopilotWorkflowApprovalRequest(plan_id="plan-1"), BackgroundTasks()
    )

    assert result["code"] == "project_created_translation_not_started"
    assert result["status"] == "project_created_translation_not_started"
    assert result["project_created"] is True
    assert result["translation_started"] is False
    assert result["failure_stage"] == "translation_plan"
    assert result["error"]["stage"] == "translation_plan"
    assert result["recovery"]["action"] == "open_initial_translation"
    assert result["recovery"]["requires_approval"] is True
    assert result["allowed_recovery_actions"] == [
        "replan_initial_translation",
        "open_existing_project",
    ]


@pytest.mark.asyncio
async def test_existing_project_translation_readiness_fails_before_plan_reservation(monkeypatch):
    reserved = False

    async def fail_readiness(_plan_id):
        raise ProviderReadinessError(
            "provider_setup_required",
            "Configure the selected provider credential in Remis Settings before continuing.",
            checks={"provider": "fixture_cloud", "credential_configured": False},
        )

    def should_not_reserve(_plan_id):
        nonlocal reserved
        reserved = True
        raise AssertionError("readiness must fail before plan reservation")

    monkeypatch.setattr(copilot_router, "ensure_translation_provider_ready", fail_readiness)
    monkeypatch.setattr(copilot_router, "reserve_translation_plan", should_not_reserve)

    with pytest.raises(HTTPException) as exc_info:
        await copilot_router.execute_initial_translation(
            CopilotWorkflowApprovalRequest(plan_id="plan-1"), BackgroundTasks()
        )

    assert reserved is False
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "provider_setup_required"


@pytest.mark.asyncio
async def test_project_is_preserved_when_translation_start_throws(monkeypatch):
    released = []

    async def approve_plan(_plan_id):
        return {"project": {"project_id": "project-1", "name": "Demo"}}

    async def create_plan(**_kwargs):
        return {"plan_id": "translation-plan-1"}

    async def fail_start(_request, _background_tasks):
        raise HTTPException(status_code=503, detail={
            "code": "provider_unavailable",
            "message": "Provider is temporarily unavailable.",
            "retryable": True,
        })

    monkeypatch.setattr(copilot_router, "ensure_localization_provider_ready", lambda _id: _ready())
    monkeypatch.setattr(copilot_router, "approve_and_execute_plan", approve_plan)
    monkeypatch.setattr(copilot_router, "get_localization_translation_args", lambda _id: {
        "target_lang_codes": ["zh-CN"],
        "api_provider": "fixture_cloud",
        "model": "fixture-model",
    })
    monkeypatch.setattr(copilot_router, "create_translation_plan", create_plan)
    monkeypatch.setattr(copilot_router, "reserve_translation_plan", lambda _id: {
        "project_id": "project-1",
        "source_lang_code": "en",
        "target_lang_codes": ["zh-CN"],
        "api_provider": "fixture_cloud",
        "model": "fixture-model",
    })
    monkeypatch.setattr(copilot_router, "start_translation_project", fail_start)
    monkeypatch.setattr(
        copilot_router,
        "release_plan_reservation",
        lambda plan_id: released.append(plan_id),
    )

    result = await copilot_router.execute_guided_localization(
        CopilotWorkflowApprovalRequest(plan_id="guided-plan"), BackgroundTasks()
    )

    assert result["code"] == "project_created_translation_not_started"
    assert result["project"]["project_id"] == "project-1"
    assert result["translation_started"] is False
    assert result["failure_stage"] == "translation_start"
    assert result["error"] == {
        "code": "provider_unavailable",
        "message": "Provider is temporarily unavailable.",
        "retryable": True,
        "stage": "translation_start",
    }
    assert result["translation_plan_id"] == "translation-plan-1"
    assert released == ["translation-plan-1"]


async def _ready():
    return {"ready": True, "checks": {"provider": "lm_studio"}}


@pytest.mark.asyncio
async def test_provider_readiness_reports_missing_credential_without_secrets(monkeypatch):
    monkeypatch.setattr(provider_readiness, "API_PROVIDERS", {
        "fixture_cloud": {
            "name": "Fixture Cloud",
            "api_key_env": "FIXTURE_KEY",
            "base_url": "https://fixture.invalid/v1",
            "available_models": ["fixture-model"],
        }
    })
    monkeypatch.setattr(provider_readiness, "get_api_key", lambda *_args: None)

    with pytest.raises(ProviderReadinessError) as exc_info:
        await provider_readiness.check_provider_readiness("fixture_cloud", "fixture-model")

    assert exc_info.value.code == "provider_setup_required"
    assert "FIXTURE" not in str(exc_info.value.as_detail())
    assert "api_key" not in exc_info.value.as_detail()


@pytest.mark.asyncio
async def test_provider_readiness_rejects_model_not_reported_by_local_endpoint(monkeypatch):
    monkeypatch.setattr(provider_readiness, "API_PROVIDERS", {
        "lm_studio": {
            "base_url": "http://127.0.0.1:1/v1",
            "available_models": ["configured-model"],
        }
    })
    monkeypatch.setattr(
        provider_readiness,
        "_probe_local_endpoint",
        lambda *_args: _probe(True, ["live-model"]),
    )

    with pytest.raises(ProviderReadinessError) as exc_info:
        await provider_readiness.check_provider_readiness("lm_studio", "configured-model")

    assert exc_info.value.code == "provider_model_mismatch"
    assert exc_info.value.checks["endpoint_reachable"] is True


@pytest.mark.asyncio
async def test_provider_readiness_blocks_unreachable_local_endpoint(monkeypatch):
    monkeypatch.setattr(provider_readiness, "API_PROVIDERS", {
        "lm_studio": {
            "base_url": "http://127.0.0.1:1/v1",
            "available_models": ["configured-model"],
        }
    })
    monkeypatch.setattr(
        provider_readiness,
        "_probe_local_endpoint",
        lambda *_args: _probe(False, []),
    )

    with pytest.raises(ProviderReadinessError) as exc_info:
        await provider_readiness.check_provider_readiness("lm_studio", "configured-model")

    assert exc_info.value.code == "provider_endpoint_unreachable"
    assert exc_info.value.checks["endpoint_reachable"] is False


async def _probe(reachable, models):
    return reachable, models
