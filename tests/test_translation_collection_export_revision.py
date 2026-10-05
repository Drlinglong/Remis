"""Export receipts must atomically attach to the approved collection revision."""
from unittest.mock import AsyncMock

import pytest

from scripts.core.agent_service import AgentRegistry
from scripts.core.translation_collections import packaging, service
from scripts.core.translation_collections.repository import CollectionConflict, CollectionRepository


def _draft():
    return {"title": "Original collection", "game_id": "surviving_mars", "description": "",
            "target_languages": ["zh-CN"], "members": []}


def _change_from_other_client(repository, collection, change):
    if change == "edit":
        return repository.replace(collection["collection_id"], collection["revision"],
                                  {"title": "Changed by another client"})
    repository.delete(collection["collection_id"], collection["revision"])
    return None


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_stale_export_receipt_rolls_back_without_changing_current_document(tmp_path, change):
    repository = CollectionRepository(str(tmp_path / "collections.sqlite"))
    other_client = CollectionRepository(repository.db_path)
    approved = repository.create(_draft())
    current = _change_from_other_client(other_client, approved, change)
    result = {"package_path": str(tmp_path / "package"), "mode": "mars_text_mod", "members": []}

    with pytest.raises(CollectionConflict, match="changed or was removed during export"):
        repository.record_export(approved, "plan_" + "a" * 32, result)

    assert repository.get(approved["collection_id"]) == current
    assert other_client.get(approved["collection_id"]) == current
    assert repository.history(approved["collection_id"]) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["edit", "delete"])
async def test_service_receipt_conflict_removes_new_package_and_releases_plan(tmp_path, monkeypatch, change):
    repository = CollectionRepository(str(tmp_path / "collections.sqlite"))
    other_client = CollectionRepository(repository.db_path)
    registry = AgentRegistry(str(tmp_path / "agent.json"))
    monkeypatch.setattr(service, "repository", repository)
    monkeypatch.setattr(service, "agent_registry", registry)
    monkeypatch.setattr(service, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "_locks", {})
    monkeypatch.setattr(packaging, "inspect_collection", AsyncMock(return_value={
        "can_export": True, "fingerprint": "preview", "members": [],
    }))
    collection = repository.create(_draft())
    current_documents, built_destinations = [], []
    retained = tmp_path / "older-package" / "keep.txt"
    retained.parent.mkdir()
    retained.write_text("keep", encoding="utf-8")

    async def build(approved, destination, _fingerprint):
        destination.mkdir(parents=True)
        (destination / "translated.txt").write_text("translated", encoding="utf-8")
        built_destinations.append(destination)
        current_documents.append(_change_from_other_client(other_client, approved, change))
        return {"package_path": str(destination), "mode": "mars_text_mod", "members": []}

    monkeypatch.setattr(packaging, "build_collection", build)
    plan = await service.plan_export(collection["collection_id"])
    with pytest.raises(CollectionConflict, match="changed or was removed during export"):
        await service.export_collection(collection["collection_id"], plan["plan_id"], approved=True)

    assert len(built_destinations) == 1
    assert not built_destinations[0].exists()
    assert retained.read_text(encoding="utf-8") == "keep"
    assert repository.get(collection["collection_id"]) == current_documents[0]
    assert repository.history(collection["collection_id"]) == []
    # Public consumption succeeds only if the failed export released its plan.
    assert registry.consume_plan(plan["plan_id"], approved=True)["plan_id"] == plan["plan_id"]
