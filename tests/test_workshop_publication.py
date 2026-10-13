"""Approval, immutable inputs, atomic admission and uncertain remote outcomes."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.steam_workshop_repository import SteamWorkshopRepository
from scripts.core.repositories.workshop_publication_repository import WorkshopPublicationRepository
from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.services.workshop_publication_inputs import WorkshopPublicationInputs, package_files
from scripts.core.services.workshop_publication_service import WorkshopPublicationService
from scripts.schemas.workshop_publication import PublicationError, PublicationPlanRequest
from tests.test_steam_workshop_assets import _png


class FakeSteam:
    def __init__(self):
        self.calls = []
        self.ready = True
        self.result = {"status": "succeeded", "eresult": 1, "published_file_id": "12345", "code": "steam_submit_confirmed"}
        self.crash = False

    def availability(self):
        return {"ready": self.ready, "code": "fake"}

    def probe(self, app_id, work_dir, published_file_id=None):
        return {"ready": self.ready, "code": "fake", "steam_id": "76561198000000000"}

    def publish(self, payload, directory, on_event):
        self.calls.append(payload)
        on_event({"type": "remote_started", "operation": "create"})
        on_event({"type": "created", "published_file_id": "12345"})
        on_event({"type": "progress", "bytes_done": 10, "bytes_total": 10})
        if self.crash:
            raise RuntimeError("native worker crashed")
        return self.result


@pytest.fixture
def publication(tmp_path):
    db = tmp_path / "remis.sqlite"
    migrate_main_database(str(db))
    source = tmp_path / "source"
    output = tmp_path / "translation"
    source.mkdir()
    output.mkdir()
    (source / "original_l_english.yml").write_text('l_english:\n K:0 "Hello $NAME$"\n', encoding="utf-8-sig")
    (output / "translated_l_simp_chinese.yml").write_text('l_simp_chinese:\n K:0 "你好 $NAME$"\n', encoding="utf-8-sig")
    (source / ".remis_project.json").write_text(json.dumps({"config": {"translation_dirs": [str(output)]}}), encoding="utf-8")
    project = {"project_id": "project-1", "source_path": str(source), "status": "active", "game_id": "victoria3"}
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO projects(project_id,name,game_id,source_path,source_language,status) VALUES ('project-1','P','victoria3',?,'en','active')", (str(source),))
    assets = SteamWorkshopService(SteamWorkshopRepository(str(db)), tmp_path / "assets")
    workspace = assets.create_workspace({"name": "Publication", "project_id": "project-1", "workshop_item_id": "99999"})
    workspace_id = workspace["workspace_id"]
    description = assets.create_description_version(workspace_id, {"bbcode": "[b]翻译包[/b]", "language": "zh", "source": "manual"})
    cover = assets.create_cover_version(workspace_id, {"png_base64": base64.b64encode(_png()).decode(), "canvas": {}, "source": "manual"})
    assets.select_version(workspace_id, "description", description["version_id"])
    assets.select_version(workspace_id, "cover", cover["version_id"])
    steam = FakeSteam()
    service = WorkshopPublicationService(WorkshopPublicationRepository(db), WorkshopPublicationInputs(assets), steam, tmp_path / "publication")
    request = PublicationPlanRequest(output_folder_name=output.name, app_id=529340, title="Translation").model_dump()
    return service, workspace_id, project, request, output, steam


def preview(context):
    service, workspace, project, request, *_ = context
    return service.plan(workspace, project, request)


def approve(context, plan, approved=True):
    service, workspace, project, *_ = context
    return service.approve(workspace, plan["plan_id"], project, approved, plan["fingerprint"])


def test_preview_never_uploads_and_does_not_inherit_original_mod_id(publication):
    plan = preview(publication)
    assert plan["status"] == "preview"
    assert plan["target"]["published_file_id"] is None
    assert plan["target"]["visibility"] == "private"
    assert plan["validation"]["entry_count"] == 1
    assert plan["validation"]["runtime_verified"] is False
    assert publication[-1].calls == []


def test_explicit_approval_and_exact_identity_are_required(publication):
    plan = preview(publication)
    with pytest.raises(PublicationError, match="Explicit approval"):
        approve(publication, plan, False)
    service, workspace, project, *_ = publication
    with pytest.raises(PublicationError, match="fingerprint"):
        service.approve(workspace, plan["plan_id"], project, True, "0" * 64)
    assert publication[-1].calls == []


@pytest.mark.parametrize("mutation", ["content", "added_file", "source", "selection", "diagnostic"])
def test_input_changes_invalidate_approval(publication, mutation):
    plan = preview(publication)
    service, workspace, project, request, output, _ = publication
    if mutation == "content":
        (output / "translated_l_simp_chinese.yml").write_text('l_simp_chinese:\n K:0 "再见 $NAME$"\n', encoding="utf-8-sig")
    elif mutation == "added_file":
        (output / "new.txt").write_text("added", encoding="utf-8")
    elif mutation == "source":
        (Path(project["source_path"]) / "original_l_english.yml").write_text('l_english:\n K:0 "Goodbye $NAME$"\n', encoding="utf-8-sig")
    elif mutation == "diagnostic":
        (output / "workshop_issues.json").write_text('{"issues": []}', encoding="utf-8")
    else:
        description = service.inputs.workshop.create_description_version(workspace, {"bbcode": "New description", "language": "en", "source": "manual"})
        service.inputs.workshop.select_version(workspace, "description", description["version_id"])
    with pytest.raises(PublicationError, match="changed"):
        approve(publication, plan)


def test_same_plan_is_admitted_once_across_database_connections(publication):
    plan = preview(publication)
    service = publication[0]
    def claim(_):
        return WorkshopPublicationRepository(service.repository.db_path).claim(plan["plan_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(claim, range(4))) == [False, False, False, True]


def test_global_active_publication_lock(publication):
    first, second = preview(publication), preview(publication)
    approve(publication, first)
    with pytest.raises(PublicationError, match="active"):
        approve(publication, second)


def test_immutable_snapshot_and_repeated_submit(publication):
    service, _, _, _, output, steam = publication
    plan = preview(publication)
    result, claimed = approve(publication, plan)
    assert result["status"] == "running" and claimed
    assert approve(publication, plan)[1] is False
    service.run(plan["plan_id"])
    final = service.public(service.repository.get(plan["plan_id"]))
    assert final["status"] == "succeeded"
    assert final["result"]["workshop_url"].endswith("12345")
    assert Path(steam.calls[0]["content_path"]) != output
    assert package_files(Path(steam.calls[0]["content_path"])) == package_files(output)
    assert approve(publication, plan)[1] is False
    assert len(steam.calls) == 1


def test_change_between_approval_and_execution_never_reaches_steam(publication):
    plan = preview(publication)
    approve(publication, plan)
    (publication[4] / "later.txt").write_text("changed", encoding="utf-8")
    publication[0].run(plan["plan_id"])
    assert publication[0].repository.get(plan["plan_id"])["status"] == "failed"
    assert publication[-1].calls == []


@pytest.mark.parametrize("case", ["crash", "false_success", "legal"])
def test_uncertain_or_legal_outcome_is_not_success_or_retried(publication, case):
    service, *_, steam = publication
    plan = preview(publication)
    approve(publication, plan)
    if case == "crash":
        steam.crash = True
    elif case == "false_success":
        steam.result["eresult"] = 2
    else:
        steam.result.update(status="legal_agreement_required", legal_agreement_required=True)
    service.run(plan["plan_id"])
    status = service.repository.get(plan["plan_id"])["status"]
    assert status == ("legal_agreement_required" if case == "legal" else "unknown")
    assert approve(publication, plan)[1] is False
    with pytest.raises(PublicationError, match="Verify"):
        approve(publication, preview(publication))
    assert len(steam.calls) == 1


def test_restart_keeps_unknown_and_never_replays(publication):
    plan = preview(publication)
    approve(publication, plan)
    service = publication[0]
    WorkshopPublicationRepository(service.repository.db_path).recover_interrupted()
    assert service.repository.get(plan["plan_id"])["status"] == "unknown"
    service.run(plan["plan_id"])
    assert publication[-1].calls == []


@pytest.mark.parametrize("name,content", [(".env", "secret"), ("workshop_issues.json", "not JSON"), (".remis_errors.json", "[{\"status\":\"detected\"}]")])
def test_private_or_invalid_diagnostics_block_preview(publication, name, content):
    (publication[4] / name).write_text(content, encoding="utf-8")
    with pytest.raises(PublicationError):
        preview(publication)
    assert publication[-1].calls == []


def test_missing_protected_tokens_block_preview(publication):
    (publication[4] / "translated_l_simp_chinese.yml").write_text('l_simp_chinese:\n K:0 "你好"\n', encoding="utf-8-sig")
    with pytest.raises(PublicationError, match="validation"):
        preview(publication)


def test_runtime_not_ready_still_allows_review_but_blocks_submit(publication):
    publication[-1].ready = False
    plan = preview(publication)
    assert plan["allowed_actions"] == []
    with pytest.raises(PublicationError, match="Steam SDK"):
        approve(publication, plan)


def test_http_workflow_and_cross_workspace_isolation(publication, monkeypatch):
    from scripts.routers import workshop_publication as router
    service, workspace, project, request, _, steam = publication
    monkeypatch.setattr(router, "service", service)
    async def get_project(workspace_id):
        return project
    monkeypatch.setattr(router, "_project", get_project)
    app = FastAPI()
    app.include_router(router.router)
    base = f"/api/steam-workshop/workspaces/{workspace}/publication"
    with TestClient(app) as client:
        response = client.post(f"{base}/plans", json=request)
        assert response.status_code == 201, response.text
        plan = response.json()
        wrong = client.get(f"/api/steam-workshop/workspaces/wrong/publication/plans/{plan['plan_id']}")
        assert wrong.status_code == 404
        invalid = client.post(f"{base}/plans/{plan['plan_id']}/submit", json={"approved": "true", "fingerprint": plan["fingerprint"]})
        assert invalid.status_code == 422
        response = client.post(f"{base}/plans/{plan['plan_id']}/submit", json={"approved": True, "fingerprint": plan["fingerprint"]})
        assert response.status_code == 202, response.text
        assert response.json()["status"] == "running"
        assert client.get(f"{base}/plans/{plan['plan_id']}").json()["status"] == "succeeded"
        client.post(f"{base}/plans/{plan['plan_id']}/submit", json={"approved": True, "fingerprint": plan["fingerprint"]})
    assert len(steam.calls) == 1


def test_task_center_reflects_remote_unknown_without_claiming_completion(publication):
    from scripts.core.repositories.task_repository import TaskRepository
    from scripts.core.services.workshop_publication_task_projection import WorkshopPublicationTaskProjection
    from scripts.shared import task_state
    service, *_, steam = publication
    previous_tasks = dict(task_state.tasks)
    previous_repository = task_state.get_repository()
    task_state.tasks.clear()
    task_state.configure_repository(TaskRepository(service.repository.db_path))
    try:
        service.projection = WorkshopPublicationTaskProjection()
        plan = preview(publication)
        admitted, _ = approve(publication, plan)
        steam.crash = True
        service.run(plan["plan_id"])
        task = task_state.get_repository().get_task(admitted["task_id"])
        assert task["status"] == "failed"
        assert task["result"]["metadata"]["publication_status"] == "unknown"
    finally:
        task_state.configure_repository(previous_repository)
        task_state.tasks.clear()
        task_state.tasks.update(previous_tasks)


def test_restart_preserves_known_created_item_id(publication):
    plan = preview(publication)
    approve(publication, plan)
    service = publication[0]
    service.repository.progress(plan["plan_id"], {"type": "created", "published_file_id": "12345"})
    service.recover()
    record = service.repository.get(plan["plan_id"])
    assert record["result"]["published_file_id"] == "12345"
    assert record["result"]["workshop_url"].endswith("12345")


def test_execution_lease_is_acquired_once(publication):
    plan = preview(publication)
    approve(publication, plan)
    repository = publication[0].repository
    assert repository.begin_execution(plan["plan_id"]) is True
    assert repository.begin_execution(plan["plan_id"]) is False


def test_task_storage_failure_blocks_native_execution(publication):
    service = publication[0]
    class BrokenProjection:
        def project(self, _record):
            raise RuntimeError("disk full")
    service.projection = BrokenProjection()
    plan = preview(publication)
    with pytest.raises(PublicationError, match="Task storage"):
        approve(publication, plan)
    assert service.repository.get(plan["plan_id"])["status"] == "failed"
    assert publication[-1].calls == []


def test_manual_verification_requires_confirmation_and_does_not_claim_upload(publication):
    service = publication[0]
    plan = preview(publication)
    approve(publication, plan)
    service.recover()
    workspace = publication[1]
    request = {"verified": False, "resolution": "item_present", "published_file_id": "12345"}
    with pytest.raises(PublicationError, match="Confirm"):
        service.verify_remote(workspace, plan["plan_id"], request)
    resolved = service.verify_remote(workspace, plan["plan_id"], {**request, "verified": True})
    assert resolved["status"] == "resolved"
    assert resolved["result"]["verification_source"] == "user"
    assert resolved["result"]["manual_resolution"] == "item_present"
    assert publication[-1].calls == []
    assert approve(publication, plan)[1] is False


def test_recovered_present_item_requires_update_of_same_target(publication):
    service, workspace, project, request, *_ = publication
    plan = preview(publication)
    approve(publication, plan)
    service.recover()
    service.verify_remote(workspace, plan["plan_id"], {"verified": True, "resolution": "item_present", "published_file_id": "12345"})
    with pytest.raises(PublicationError, match="update preview"):
        approve(publication, preview(publication))
    update = service.plan(workspace, project, {**request, "mode": "update", "published_file_id": "12345"})
    assert approve(publication, update)[1] is True


def test_verified_absence_allows_fresh_create_but_never_replays_old_plan(publication):
    service = publication[0]
    plan = preview(publication)
    approve(publication, plan)
    service.recover()
    service.verify_remote(publication[1], plan["plan_id"], {"verified": True, "resolution": "item_absent", "published_file_id": None})
    assert approve(publication, plan)[1] is False
    assert approve(publication, preview(publication))[1] is True


def test_known_remote_id_cannot_be_replaced_during_verification(publication):
    service = publication[0]
    plan = preview(publication)
    approve(publication, plan)
    service.repository.progress(plan["plan_id"], {"type": "created", "published_file_id": "12345"})
    service.recover()
    with pytest.raises(PublicationError, match="already returned"):
        service.verify_remote(publication[1], plan["plan_id"], {"verified": True, "resolution": "item_present", "published_file_id": "99999"})
