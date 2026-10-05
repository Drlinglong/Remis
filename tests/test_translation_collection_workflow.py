"""Collection persistence, API parity and approval/revision boundary regressions."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.agent_service import AgentRegistry
from scripts.core.translation_collections import service, sources, packaging
from scripts.core.translation_collections.repository import CollectionRepository, CollectionConflict
from scripts.routers.translation_collections import router


def draft(**changes):
    return {"title": "测试合集", "game_id": "surviving_mars", "description": "中文与多语言",
            "target_languages": ["zh-CN"], "members": [], **changes}


@pytest.fixture
def repo(tmp_path):
    return CollectionRepository(str(tmp_path / "collections.sqlite"))


def test_persist_identity_unicode_and_compare_and_swap(repo):
    collection = repo.create(draft())
    identity = collection["collection_id"]
    reloaded = CollectionRepository(repo.db_path).get(identity)
    assert reloaded == collection
    updated = repo.replace(identity, 1, {"title": "新版", "steam_id": "3807689989"})
    assert updated["mod_id"] == collection["mod_id"]
    with pytest.raises(CollectionConflict):
        repo.replace(identity, 1, {"title": "旧页面"})
    assert repo.get(identity)["title"] == "新版"
    assert repo.get(identity)["steam_id"] == "3807689989"


def test_concurrent_edits_have_one_winner(repo):
    collection = repo.create(draft())
    def save(title):
        try:
            repo.replace(collection["collection_id"], 1, {"title": title})
            return True
        except CollectionConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["first", "second"]))
    assert sum(results) == 1
    assert repo.get(collection["collection_id"])["revision"] == 2


def test_history_retains_snapshot_and_delete_never_touches_package(repo, tmp_path):
    collection = repo.create(draft())
    package = tmp_path / "export"
    package.mkdir()
    result = {"package_path": str(package), "mode": "mars_text_mod", "members": []}
    repo.record_export(collection, "plan_123", result)
    updated = repo.replace(collection["collection_id"], 1, {"title": "new"})
    assert updated["last_export"]["plan_id"] == "plan_123"
    assert repo.history(collection["collection_id"])[0]["snapshot"]["title"] == "测试合集"
    repo.delete(collection["collection_id"], 2)
    assert package.is_dir()
    assert repo.history(collection["collection_id"])


@pytest.fixture
def client(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(service, "repository", repo)
    monkeypatch.setattr(service, "_locks", {})
    monkeypatch.setattr(service, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "agent_registry", AgentRegistry(str(tmp_path / "agent.json")))
    monkeypatch.setattr(sources, "validate_members", AsyncMock())
    monkeypatch.setattr(sources, "reject_source_publication", AsyncMock())
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


def test_api_parity_rejects_identity_injection_and_stale_update(client):
    assert client.post("/api/agent/translation-collections", json=draft(mod_id="author")).status_code == 422
    created = client.post("/api/translation-collections", json=draft()).json()
    path = "/api/agent/translation-collections/" + created["collection_id"]
    assert client.get(path).json() == created
    fields = draft(title="renamed")
    del fields["game_id"]
    fields["expected_revision"] = 1
    assert client.put(path, json=fields).status_code == 200
    assert client.put(path, json=fields).status_code == 409
    assert client.get("/api/translation-collections").json()["collections"][0]["title"] == "renamed"


def test_publication_is_explicit_and_retained_on_member_edits(client):
    created = client.post("/api/translation-collections", json=draft()).json()
    path = "/api/translation-collections/" + created["collection_id"]
    binding = {"expected_revision": 1, "steam_id": "3807689989"}
    assert client.put(path + "/publication", json=binding).status_code == 409
    binding["approved"] = True
    assert client.put(path + "/publication", json={**binding, "steam_id": "18446744073709551616"}).status_code == 422
    saved = client.put(path + "/publication", json=binding).json()
    fields = {key: saved[key] for key in ("title", "description", "target_languages", "members")}
    fields.update(title="new members later", expected_revision=2)
    updated = client.put(path, json=fields).json()
    assert updated["steam_id"] == binding["steam_id"]
    assert updated["mod_id"] == created["mod_id"]


def preview(**changes):
    return {"can_export": True, "fingerprint": "abc", "members": [], "diagnostics": [],
            "mode": "mars_text_mod", "file_count": 4, "entry_count": 2, **changes}


def test_export_approval_stale_revision_and_replay(client, monkeypatch, tmp_path):
    monkeypatch.setattr(packaging, "inspect_collection", AsyncMock(return_value=preview()))
    build = AsyncMock(return_value={"package_path": str(tmp_path / "out"), "mode": "mars_text_mod", "members": []})
    monkeypatch.setattr(packaging, "build_collection", build)
    created = client.post("/api/translation-collections", json=draft()).json()
    path = "/api/translation-collections/" + created["collection_id"]
    plan = client.post(path + "/plan", json={}).json()
    args = {"plan_id": plan["plan_id"]}
    assert client.post(path + "/export", json=args).status_code == 409
    assert build.await_count == 0
    result = client.post(path + "/export", json={**args, "approved": True})
    assert result.status_code == 200, result.text
    assert client.post(path + "/export", json={**args, "approved": True}).status_code == 409
    assert len(client.get(path + "/history").json()["exports"]) == 1
    plan2 = client.post(path + "/plan", json={}).json()
    fields = {key: created[key] for key in ("title", "description", "target_languages", "members")}
    client.put(path, json={**fields, "title": "changed", "expected_revision": 1})
    assert client.post(path + "/export", json={"plan_id": plan2["plan_id"], "approved": True}).status_code == 409
    assert build.await_count == 1


def test_blocked_preview_has_no_approvable_plan(client, monkeypatch):
    monkeypatch.setattr(packaging, "inspect_collection", AsyncMock(return_value=preview(can_export=False)))
    collection = client.post("/api/translation-collections", json=draft()).json()
    result = client.post(f"/api/translation-collections/{collection['collection_id']}/plan").json()
    assert result["plan_id"] is None
    assert "approve_collection_export" not in result["allowed_actions"]


@pytest.mark.asyncio
async def test_member_game_language_and_project_ownership_are_validated(monkeypatch):
    monkeypatch.setattr(sources, "GAME_PROFILES_BY_ID", {"surviving_mars": {}})
    monkeypatch.setattr(sources, "project_by_id", AsyncMock(return_value={"game_id": "rimworld"}))
    with pytest.raises(ValueError, match="same|belong"):
        await sources.validate_members("surviving_mars", draft(members=[{"project_id": "p", "outputs": []}]))
    with pytest.raises(ValueError, match="languages"):
        await sources.validate_members("surviving_mars", draft(target_languages=["ja"]))


def test_contract_rejects_duplicate_members_and_output_languages(client):
    member = {"project_id": "p", "outputs": []}
    assert client.post("/api/translation-collections", json=draft(members=[member, member])).status_code == 422
    output = {"language_code": "zh-CN", "output_folder_name": "zh-CN-one"}
    assert client.post("/api/translation-collections", json=draft(members=[{**member, "outputs": [output, output]}])).status_code == 422


@pytest.mark.asyncio
async def test_receipt_failure_rolls_back_only_new_output_then_can_retry(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(service, "repository", repo)
    monkeypatch.setattr(service, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "_locks", {})
    monkeypatch.setattr(service, "agent_registry", AgentRegistry(str(tmp_path / "agent.json")))
    monkeypatch.setattr(packaging, "inspect_collection", AsyncMock(return_value=preview()))
    async def build(collection, destination, fingerprint):
        destination.mkdir(parents=True)
        (destination / "translated.txt").write_text("内容", encoding="utf-8")
        return {"package_path": str(destination), "mode": "mars_text_mod", "members": []}
    monkeypatch.setattr(packaging, "build_collection", build)
    collection = repo.create(draft())
    plan = await service.plan_export(collection["collection_id"])
    original_record = repo.record_export
    def fail(*args):
        raise OSError("simulated database commit failure")
    monkeypatch.setattr(repo, "record_export", fail)
    with pytest.raises(OSError, match="database"):
        await service.export_collection(collection["collection_id"], plan["plan_id"], True)
    assert not list((tmp_path / "translation_collections").rglob("translated.txt"))
    monkeypatch.setattr(repo, "record_export", original_record)
    result = await service.export_collection(collection["collection_id"], plan["plan_id"], True)
    assert result["package_path"]
    assert len(repo.history(collection["collection_id"])) == 1
