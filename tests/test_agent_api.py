from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

from scripts.core.agent_service import AgentRegistry
from scripts.routers import agent as agent_router
from scripts.schemas.agent import (
    AgentJobPlanRequest,
    AgentJobStartRequest,
    AgentProjectCreateRequest,
    AgentProjectPlanRequest,
    AgentRepairRequest,
    AgentValidationSummary,
)
from scripts.shared import task_state


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    registry = AgentRegistry(str(tmp_path / "agent-registry.json"))
    monkeypatch.setattr(agent_router, "agent_registry", registry)
    return registry


@pytest.mark.asyncio
async def test_capabilities_are_discoverable_without_provider_secrets():
    payload = await agent_router.get_capabilities()

    assert payload["transport"]["localhost_only"] is True
    assert payload["actions"]["start_translation"]["requires_approval"] is True
    assert payload["actions"]["pause"]["supported"] is False
    assert payload["safety"]["api_keys_returned"] is False
    assert payload["games"]
    assert payload["providers"]
    assert all("api_key" not in provider for provider in payload["providers"])
    assert all("base_url" not in provider for provider in payload["providers"])
    assert all(
        provider["credential_status"] in {"configured", "missing", "not_required"}
        for provider in payload["providers"]
    )


def test_preflight_checks_release_and_prompts_for_first_provider_setup(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "tag_name": "v99.0.0",
                "html_url": "https://github.com/Drlinglong/Remis/releases/tag/v99.0.0",
                "published_at": "2026-07-18T00:00:00Z",
                "prerelease": False,
            }

    monkeypatch.setattr(agent_router.requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(agent_router, "get_api_key", lambda *args: None)

    payload = agent_router.get_agent_preflight()

    assert payload["required_before_every_workflow"] is True
    assert payload["release_check"]["checked"] is True
    assert payload["release_check"]["update_available"] is True
    assert payload["provider_setup"]["setup_required"] is True
    assert payload["provider_setup"]["explanation_available"] is True
    assert "configure_provider" in payload["allowed_actions"]
    assert "review_latest_release" in payload["allowed_actions"]


def test_preflight_allows_deliberately_selected_keyless_local_provider(monkeypatch):
    class OfflineResponse:
        def raise_for_status(self):
            raise agent_router.requests.RequestException("offline")

    monkeypatch.setattr(
        agent_router.requests, "get", lambda *args, **kwargs: OfflineResponse()
    )
    monkeypatch.setattr(agent_router, "get_api_key", lambda *args: None)

    payload = agent_router.get_agent_preflight("lm_studio")

    assert payload["provider_setup"]["selected_provider_ready"] is True
    assert payload["provider_setup"]["setup_required"] is False
    assert payload["release_check"]["checked"] is False
    assert payload["release_check"]["error"] == (
        "The release check is currently unavailable."
    )
    assert "offline" not in payload["release_check"]["error"]
    assert "report_release_check_unavailable" in payload["allowed_actions"]


@pytest.mark.asyncio
async def test_agent_project_summary_uses_existing_project_services(monkeypatch):
    async def fake_get_projects(status=None):
        assert status == "active"
        return [
            {
                "project_id": "project-1",
                "name": "Demo",
                "game_id": "victoria3",
                "source_language": "en",
                "status": "active",
            }
        ]

    async def fake_get_files(project_id):
        assert project_id == "project-1"
        return [{"status": "todo"}, {"status": "done"}]

    async def fake_validation(project_id, include_items=False):
        return {
            "summary": agent_router.AgentValidationSummary(),
            "items": [],
            "_raw_items": [],
        }

    monkeypatch.setattr(agent_router.project_manager, "get_projects", fake_get_projects)
    monkeypatch.setattr(agent_router.project_manager, "get_project_files", fake_get_files)
    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)

    projects = await agent_router.list_agent_projects("active")

    assert len(projects) == 1
    assert projects[0].file_count == 2
    assert projects[0].file_status_counts == {"todo": 1, "done": 1}
    assert "create_translation_plan" in projects[0].allowed_actions


@pytest.mark.asyncio
async def test_dry_run_plan_and_job_are_deterministic_and_write_no_output(
    monkeypatch,
    isolated_registry,
):
    async def fake_create_translation_plan(**kwargs):
        return {
            "execution_args": {
                "project_id": kwargs["project_id"],
                "source_lang_code": "en",
                "target_lang_codes": ["zh-CN"],
                "api_provider": kwargs["api_provider"],
                "model": kwargs["model"],
                "use_resume": True,
            }
        }

    async def fake_get_project(project_id):
        return {"project_id": project_id, "name": "Fixture"}

    async def fake_get_files(project_id):
        return [{"file_id": "1"}, {"file_id": "2"}]

    async def fake_validation(project_id, include_items=False):
        return {
            "summary": agent_router.AgentValidationSummary(),
            "items": [],
            "_raw_items": [],
        }

    monkeypatch.setattr(
        agent_router, "create_translation_plan", fake_create_translation_plan
    )
    monkeypatch.setattr(agent_router.project_manager, "get_project", fake_get_project)
    monkeypatch.setattr(agent_router.project_manager, "get_project_files", fake_get_files)
    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)

    plan = await agent_router.plan_agent_job(
        AgentJobPlanRequest(
            project_id="project-1",
            target_lang_codes=["zh-CN"],
            api_provider="lm_studio",
            model="fixture-model",
            dry_run=True,
        )
    )
    response = await agent_router.start_agent_job(
        AgentJobStartRequest(plan_id=plan.plan_id),
        BackgroundTasks(),
    )

    assert plan.requires_approval is False
    assert response.status == "completed"
    assert response.kind == "dry_run"
    assert response.progress.total_files == 2
    assert response.output_paths == []
    assert response.allowed_actions == ["create_translation_plan"]
    task_state.tasks.pop(response.job_id, None)


@pytest.mark.asyncio
async def test_real_translation_plan_requires_explicit_approval(
    monkeypatch,
    isolated_registry,
):
    monkeypatch.setattr(agent_router, "get_api_key", lambda *args: "test-key")

    async def fake_create_translation_plan(**kwargs):
        return {
            "execution_args": {
                "project_id": kwargs["project_id"],
                "target_lang_codes": ["zh-CN"],
                "api_provider": "openai",
                "model": "gpt-test",
                "use_resume": True,
            }
        }

    monkeypatch.setattr(
        agent_router, "create_translation_plan", fake_create_translation_plan
    )
    plan = await agent_router.plan_agent_job(
        AgentJobPlanRequest(
            project_id="project-1",
            target_lang_codes=["zh-CN"],
            api_provider="openai",
            model="gpt-test",
            translation_context_mode="none",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.start_agent_job(
            AgentJobStartRequest(plan_id=plan.plan_id, approved=False),
            BackgroundTasks(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "approval_required"


@pytest.mark.asyncio
async def test_agent_archive_plan_blocks_when_context_readiness_is_false(
    monkeypatch,
    isolated_registry,
):
    async def fake_create_translation_plan(**kwargs):
        return {
            "execution_args": {
                "project_id": kwargs["project_id"],
                "translation_context_mode": kwargs["translation_context_mode"],
            },
            "inspection": {"game_id": "stellaris"},
        }

    readiness = AsyncMock()
    readiness.inspect.return_value = {
        "requested_mode": "archive",
        "status": "blocked",
        "can_start": False,
        "warnings": ["context_release_missing"],
    }
    monkeypatch.setattr(agent_router, "create_translation_plan", fake_create_translation_plan)
    monkeypatch.setattr(agent_router, "translation_context_readiness", readiness)

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.plan_agent_job(
            AgentJobPlanRequest(
                project_id="project-1",
                api_provider="lm_studio",
                model="local-model",
                translation_context_mode="archive",
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "project_context_not_ready"
    assert exc_info.value.detail["context_readiness"]["warnings"] == [
        "context_release_missing"
    ]
@pytest.mark.asyncio
async def test_cloud_translation_plan_requires_provider_setup(monkeypatch):
    monkeypatch.setattr(
        agent_router,
        "API_PROVIDERS",
        {"fixture_cloud": {"name": "Fixture Cloud", "api_key_env": "FIXTURE_KEY"}},
    )
    monkeypatch.setattr(agent_router, "get_api_key", lambda *args: None)

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.plan_agent_job(
            AgentJobPlanRequest(
                project_id="project-1",
                api_provider="fixture_cloud",
                model="fixture-model",
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "provider_setup_required"
    assert "API key" in exc_info.value.detail["message"]


@pytest.mark.asyncio
async def test_missing_job_returns_machine_readable_error(isolated_registry):
    with pytest.raises(HTTPException) as exc_info:
        await agent_router.get_agent_job("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "code": "job_not_found",
        "message": "Agent job not found",
        "retryable": False,
    }


def test_http_error_envelope_matches_agent_reference(isolated_registry):
    from scripts.web_server import app

    response = TestClient(app).get("/api/agent/jobs/missing-contract-job")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "job_not_found",
            "message": "Agent job not found",
            "retryable": False,
        }
    }


def test_validation_items_are_split_into_error_warning_and_human_review():
    items, summary = agent_router._classify_issues(
        [
            {"severity": "error", "error_code": "variable_missing"},
            {"severity": "warning", "error_code": "style_warning"},
            {
                "severity": "warning",
                "error_code": "validation_invalid_key_format",
            },
            {"error_code": "ambiguous_source"},
        ]
    )

    assert summary.errors == 1
    assert summary.warnings == 1
    assert summary.human_review_items == 2
    assert [item["category"] for item in items] == [
        "error",
        "warning",
        "human_review",
        "human_review",
    ]


def test_starting_job_is_pollable():
    status = agent_router._normalize_status("starting")
    actions = agent_router._job_allowed_actions(
        status,
        agent_router.AgentValidationSummary(),
        [],
        kind="translation",
    )

    assert status == "queued"
    assert actions == ["poll"]


def test_completed_job_with_manual_review_cannot_be_approved_for_export():
    validation = AgentValidationSummary(
        available=True,
        human_review_items=1,
        total=1,
    )

    actions = agent_router._job_allowed_actions(
        "completed",
        validation,
        ["reports/translation.json"],
        kind="translation",
    )

    assert actions == ["inspect_validation"]


def test_legacy_translation_job_does_not_advertise_agent_mutations():
    validation = AgentValidationSummary(available=True)

    assert agent_router._job_allowed_actions(
        "completed",
        validation,
        ["reports/translation.json"],
        kind="translation",
        agent_managed=False,
    ) == ["inspect_validation"]


@pytest.mark.asyncio
async def test_legacy_translation_job_hides_agent_export_link(
    monkeypatch,
):
    job_id = "legacy-translation-without-agent-record"
    task_state.create_task(
        job_id,
        status="completed",
        fields={
            "project_id": "project-legacy",
            "agent_job_kind": "initial_translation",
            "output_dirs": ["C:/output"],
            "progress": {"current": 1, "total": 1, "percent": 100},
        },
    )

    async def fake_validation(_project_id, include_items=False):
        return {
            "summary": AgentValidationSummary(available=True),
            "items": [],
            "_raw_items": [],
        }

    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)
    response = await agent_router.get_agent_job(job_id)

    assert response.status == "completed"
    assert response.allowed_actions == ["inspect_validation"]
    assert "export_preview" not in response.links
    task_state.tasks.pop(job_id, None)


@pytest.mark.asyncio
async def test_legacy_translation_validation_has_no_agent_actions(monkeypatch):
    job_id = "legacy-translation-validation-without-agent-record"
    task_state.create_task(
        job_id,
        status="completed",
        fields={"project_id": "project-legacy"},
    )

    async def fake_validation(_project_id, include_items=False):
        return {
            "summary": AgentValidationSummary(available=True),
            "items": [],
            "_raw_items": [],
        }

    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)
    response = await agent_router.get_agent_job_validation(job_id)

    assert response["allowed_actions"] == []
    task_state.tasks.pop(job_id, None)


def test_project_import_path_rejects_home_directory():
    with pytest.raises(HTTPException) as exc_info:
        agent_router._validate_agent_import_path(str(Path.home()))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "import_path_not_allowed"


def test_project_import_path_reports_permission_denied(monkeypatch):
    def deny(_folder_path):
        raise PermissionError("denied")

    monkeypatch.setattr(agent_router, "inspect_mod_folder", deny)

    with pytest.raises(HTTPException) as exc_info:
        agent_router._validate_agent_import_path("C:/restricted/mod")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "import_path_permission_denied"


@pytest.mark.asyncio
async def test_project_import_is_approval_gated(
    tmp_path,
    monkeypatch,
    isolated_registry,
):
    monkeypatch.setenv("REMIS_AGENT_IMPORT_ROOTS", str(tmp_path))
    mod_root = tmp_path / "fixture-mod"
    loc_root = mod_root / "localization" / "english"
    loc_root.mkdir(parents=True)
    (loc_root / "fixture_l_english.yml").write_text(
        "l_english:\n fixture_key:0 \"Fixture\"\n",
        encoding="utf-8",
    )

    plan = await agent_router.plan_agent_project(
        AgentProjectPlanRequest(
            name="Fixture",
            folder_path=str(mod_root),
            game_id="victoria3",
            source_language="en",
            import_mode="reference",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.create_agent_project(
            AgentProjectCreateRequest(plan_id=plan.plan_id, approved=False)
        )

    assert plan.risk["modifies_source_folder"] is False
    assert exc_info.value.detail["code"] == "approval_required"


@pytest.mark.asyncio
async def test_repair_requires_approval_before_loading_issues(isolated_registry):
    with pytest.raises(HTTPException) as exc_info:
        await agent_router.repair_agent_job(
            "job-1",
            AgentRepairRequest(approved=False),
            BackgroundTasks(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "approval_required"


def test_agent_repair_status_and_actions_preserve_workshop_governance():
    validation = AgentValidationSummary(available=True)

    assert agent_router._normalize_status("partial_failed") == "partial_failed"
    assert agent_router._normalize_status("interrupted") == "interrupted"
    assert agent_router._job_allowed_actions(
        "completed",
        validation,
        ["reports/repair.json"],
        kind="repair",
    ) == ["inspect_validation"]


@pytest.mark.asyncio
async def test_approved_agent_repair_forwards_governed_workshop_contract(
    isolated_registry,
    monkeypatch,
):
    task_state.tasks.clear()
    plan = isolated_registry.create_plan(
        project_id="project-1",
        execution_args={
            "project_id": "project-1",
            "api_provider": "lm_studio",
            "model": "local-model",
        },
        dry_run=False,
        summary="Repair fixture",
    )
    isolated_registry.consume_plan(plan["plan_id"], approved=True)
    isolated_registry.record_job(
        job_id="job-parent",
        project_id="project-1",
        plan_id=plan["plan_id"],
        kind="translation",
        execution_args=plan["execution_args"],
    )

    async def fake_validation(_project_id, include_items=False):
        return {
            "summary": AgentValidationSummary(),
            "items": [],
            "_raw_items": [
                {
                    "file_name": "events.yml",
                    "key": "entry",
                    "status": "detected",
                },
                {
                    "file_name": "events.yml",
                    "key": "invalid key",
                    "error_code": "validation_invalid_key_format",
                    "status": "detected",
                },
            ],
        }

    captured = {}

    async def fake_start_fix_run(request, _background_tasks):
        captured["request"] = request
        task_state.create_task(
            "repair-child",
            status="partial_failed",
            fields={
                "kind": "agent_workshop",
                "project_id": "project-1",
                "result": {
                    "types": ["workshop_repairs", "repair_reports"],
                    "output_paths": ["reports/repair-child.json"],
                    "summary": "One repair still needs review.",
                },
                "checkpoint": {
                    "available": False,
                    "resume_supported": False,
                },
            },
        )

        class Response:
            task_id = "repair-child"

        return Response()

    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)
    monkeypatch.setattr(agent_router, "start_fix_run", fake_start_fix_run)

    response = await agent_router.repair_agent_job(
        "job-parent",
        AgentRepairRequest(approved=True),
        BackgroundTasks(),
    )

    forwarded = captured["request"]
    assert forwarded.approval.approved is True
    assert forwarded.approval.issue_count == 1
    assert [issue["key"] for issue in forwarded.issues] == ["entry"]
    assert forwarded.created_by.type == "remis_agent"
    assert forwarded.idempotency_key.startswith("agent-repair:")
    assert response.job_id == "repair-child"
    assert response.status == "partial_failed"
    assert response.parent_task_id == "job-parent"
    assert response.output_paths == ["reports/repair-child.json"]
    assert response.result.summary == "One repair still needs review."
    assert response.workflow_context["source_task_id"] == "job-parent"
    assert response.recovery["checkpoint_resume_supported"] is False
    assert response.allowed_actions == ["retry"]
    assert "export_preview" not in response.links
    assert task_state.tasks["repair-child"]["parent_task_id"] == "job-parent"


@pytest.mark.asyncio
async def test_agent_repair_stops_when_only_manual_review_items_remain(
    isolated_registry,
    monkeypatch,
):
    plan = isolated_registry.create_plan(
        project_id="project-1",
        execution_args={
            "project_id": "project-1",
            "api_provider": "lm_studio",
            "model": "local-model",
        },
        dry_run=False,
        summary="Manual review fixture",
    )
    isolated_registry.consume_plan(plan["plan_id"], approved=True)
    isolated_registry.record_job(
        job_id="job-manual-only",
        project_id="project-1",
        plan_id=plan["plan_id"],
        kind="translation",
        execution_args=plan["execution_args"],
    )

    async def fake_validation(_project_id, include_items=False):
        return {
            "summary": AgentValidationSummary(
                human_review_items=1,
                total=1,
                available=True,
            ),
            "items": [],
            "_raw_items": [{
                "file_name": "events.yml",
                "key": "invalid key",
                "error_code": "validation_invalid_key_format",
                "status": "detected",
            }],
        }

    start_fix_run = AsyncMock()
    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)
    monkeypatch.setattr(agent_router, "start_fix_run", start_fix_run)

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.repair_agent_job(
            "job-manual-only",
            AgentRepairRequest(approved=True),
            BackgroundTasks(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "no_repairable_items"
    start_fix_run.assert_not_awaited()


def test_export_candidate_rejects_path_traversal(tmp_path, monkeypatch):
    destination = tmp_path / "translations"
    destination.mkdir()
    output = destination / "zh-CN-demo"
    output.mkdir()
    monkeypatch.setattr(agent_router, "DEST_DIR", str(destination))
    task = {"output_dirs": [str(output)]}

    with pytest.raises(HTTPException) as exc_info:
        agent_router._export_candidate(
            task,
            {"project_id": "project-1"},
            "../outside",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "invalid_output_folder"


def test_export_candidate_uses_persisted_snapshot(tmp_path, monkeypatch):
    destination = tmp_path / "translations"
    output = destination / "zh-CN-demo"
    output.mkdir(parents=True)
    monkeypatch.setattr(agent_router, "DEST_DIR", str(destination))

    folder_name, source_path = agent_router._export_candidate(
        {},
        {
            "project_id": "project-1",
            "last_snapshot": {"output_dirs": [str(output)]},
        },
        None,
    )

    assert folder_name == "zh-CN-demo"
    assert source_path == output.resolve()


def test_agent_export_rejects_target_outside_detected_mod_root(
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "translations"
    (destination / "zh-CN-demo").mkdir(parents=True)
    mod_root = tmp_path / "Paradox" / "mod"
    mod_root.mkdir(parents=True)
    monkeypatch.setattr(
        agent_router.deploy_manager,
        "DEST_DIR",
        str(destination),
    )
    monkeypatch.setattr(
        agent_router.deploy_manager.mod_deployer,
        "get_paradox_mod_dir",
        lambda _game_id: mod_root,
    )

    with pytest.raises(HTTPException) as exc_info:
        agent_router._validate_deploy_target(
            "victoria3",
            "zh-CN-demo",
            str(tmp_path / "outside" / "zh-CN-demo"),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "export_path_not_allowed"


def test_agent_registry_recovers_non_secret_job_metadata(tmp_path):
    path = tmp_path / "registry.json"
    registry = AgentRegistry(str(path))
    plan = registry.create_plan(
        project_id="project-1",
        execution_args={
            "project_id": "project-1",
            "api_provider": "lm_studio",
            "model": "local-model",
            "use_resume": True,
            "api_key": "must-not-persist",
            "nested": {"authorization_token": "must-not-persist"},
        },
        dry_run=False,
        summary="Plan",
    )
    registry.consume_plan(plan["plan_id"], approved=True)
    registry.record_job(
        job_id="job-1",
        project_id="project-1",
        plan_id=plan["plan_id"],
        kind="translation",
        execution_args=plan["execution_args"],
    )
    registry.update_snapshot(
        "job-1",
        {"status": "running", "progress": {"percent": 50}},
    )

    reloaded = AgentRegistry(str(path))
    job = reloaded.get_job("job-1")

    assert job["last_snapshot"]["status"] == "running"
    assert job["execution_args"]["model"] == "local-model"
    assert "api_key" not in path.read_text(encoding="utf-8")
    assert "must-not-persist" not in path.read_text(encoding="utf-8")


def test_agent_registry_permission_error_during_exists_degrades_to_empty(
    tmp_path,
    monkeypatch,
):
    def deny_exists(_path):
        raise PermissionError("registry parent is inaccessible")

    monkeypatch.setattr(Path, "exists", deny_exists)

    registry = AgentRegistry(str(tmp_path / "registry.json"))

    assert registry.list_jobs() == []


@pytest.mark.asyncio
async def test_terminal_agent_snapshot_persists_without_polling(
    isolated_registry,
    monkeypatch,
):
    job_id = "job-terminal-without-poll"
    isolated_registry.record_job(
        job_id=job_id,
        project_id="project-1",
        plan_id="plan-1",
        kind="translation",
        execution_args={"use_resume": True},
    )
    task_state.create_task(job_id, status="running")
    task_state.update_task(
        job_id,
        status="completed",
        progress={"current": 3, "total": 3, "percent": 100},
        fields={
            "project_id": "project-1",
            "agent_job_kind": "translation",
            "output_dirs": ["C:/output"],
        },
    )

    persisted = isolated_registry.get_job(job_id)["last_snapshot"]
    assert persisted["status"] == "completed"
    assert persisted["progress"]["percent"] == 100
    assert persisted["output_dirs"] == ["C:/output"]
    task_state.tasks.pop(job_id, None)

    async def fake_validation(project_id, include_items=False):
        return {
            "summary": agent_router.AgentValidationSummary(),
            "items": [],
            "_raw_items": [],
        }

    monkeypatch.setattr(agent_router, "_validation_payload", fake_validation)
    recovered = await agent_router.get_agent_job(job_id)
    assert recovered.status == "completed"
    assert recovered.recovery["source"] == "persisted_snapshot"


def test_openapi_exposes_agent_contract():
    from scripts.web_server import app

    schema = app.openapi()

    assert "/api/agent/capabilities" in schema["paths"]
    assert "/api/agent/preflight" in schema["paths"]
    assert "/api/agent/jobs/plan" in schema["paths"]
    assert "/api/agent/jobs/{job_id}/approve-export" in schema["paths"]
    assert "AgentJobResponse" in schema["components"]["schemas"]
    job_properties = schema["components"]["schemas"]["AgentJobResponse"]["properties"]
    assert "parent_task_id" in job_properties
    assert "result" in job_properties
    assert "workflow_context" in job_properties
    plan_properties = schema["components"]["schemas"]["AgentPlanResponse"]["properties"]
    assert "context_readiness" in plan_properties


def test_agent_api_cors_allows_localhost_and_rejects_remote_origins():
    from scripts.web_server import app

    client = TestClient(app)
    headers = {
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    }
    local = client.options(
        "/api/agent/capabilities",
        headers={**headers, "Origin": "http://127.0.0.1:5173"},
    )
    remote = client.options(
        "/api/agent/capabilities",
        headers={**headers, "Origin": "https://example.com"},
    )

    assert local.status_code == 200
    assert local.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in remote.headers
