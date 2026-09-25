"""Persisted game versions must govern project support and resource previews."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.core.services import game_support_service
from scripts.routers import game_support


def test_project_support_uses_persisted_version_unless_overridden(monkeypatch):
    project = {
        "game_id": "rimworld", "source_path": "C:/mods/example",
        "source_language": "en", "game_version": "1.6.4512",
    }
    manager = SimpleNamespace(get_project=AsyncMock(return_value=project))
    from scripts.shared import services as shared_services
    monkeypatch.setattr(shared_services, "project_manager", manager)
    captured = []

    def inspect(game_id, source_path, source_language, game_version=None):
        captured.append(game_version)
        return {"game_id": game_id, "requested_game_version": game_version}

    monkeypatch.setattr(game_support_service, "inspect_game_support", inspect)

    async def exercise():
        default = await game_support_service.inspect_project_game_support("project-1")
        override = await game_support_service.inspect_project_game_support("project-1", "1.5.9")
        return default, override

    import asyncio
    default, override = asyncio.run(exercise())
    assert captured == ["1.6.4512", "1.5.9"]
    assert default["requested_game_version"] == "1.6.4512"
    assert override["requested_game_version"] == "1.5.9"


def test_gui_support_and_resource_preview_use_project_version(monkeypatch, tmp_path):
    source = tmp_path / "source.xml"
    source.write_text("<root />", encoding="utf-8")
    project = {
        "project_id": "project-1", "game_id": "rimworld",
        "source_path": str(tmp_path), "source_language": "en",
        "game_version": "1.6.4512",
    }
    manager = SimpleNamespace(
        get_project=AsyncMock(return_value=project),
        get_project_files=AsyncMock(return_value=[{
            "file_id": "source-1", "file_path": str(source), "file_type": "source",
        }]),
    )
    monkeypatch.setattr(game_support, "project_manager", manager)
    support_versions = []
    monkeypatch.setattr(
        game_support, "inspect_game_support",
        lambda game_id, path, language, version=None: support_versions.append(version) or {"requested_game_version": version},
    )
    preview_versions = []

    class Adapter:
        def discover(self, root, source_language, game_version=None):
            preview_versions.append(game_version)
            return SimpleNamespace(resources=[SimpleNamespace(path=source)])

    monkeypatch.setattr(game_support, "resource_adapter", lambda _game_id: Adapter())
    app = FastAPI()
    app.include_router(game_support.router)
    client = TestClient(app)

    default = client.get("/api/projects/project-1/game-support")
    override = client.get("/api/projects/project-1/game-support?game_version=1.5.9")
    preview = client.get("/api/projects/project-1/game-resources/source-1/preview")

    assert default.json()["requested_game_version"] == "1.6.4512"
    assert override.json()["requested_game_version"] == "1.5.9"
    assert preview.status_code == 200
    assert support_versions == ["1.6.4512", "1.5.9"]
    assert preview_versions == ["1.6.4512"]


def test_proofreading_source_binding_uses_project_version(tmp_path):
    from scripts.core.game_adapters import proofreading

    source = tmp_path / "source" / "Languages" / "English" / "Keyed" / "UI.xml"
    target = tmp_path / "output" / "French" / "Keyed" / "UI.xml"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    target.write_text("target", encoding="utf-8")
    seen = []

    class Adapter:
        def parse(self, path, metadata=None):
            value = "Translated" if Path(path) == target else "Hello"
            return SimpleNamespace(entries=[SimpleNamespace(key="Greeting", value=value)])

        def discover(self, root, source_language, game_version=None):
            seen.append(game_version)
            return SimpleNamespace(resources=[SimpleNamespace(path=source, metadata={})])

        def language_folder(self, language):
            return "French" if language["code"] == "fr" else f"Other-{language['code']}"

    _, language, values = proofreading._binding(
        {"source_path": str(source.parents[3]), "source_language": "en", "game_version": "1.6.4512"},
        target,
        Adapter(),
    )

    assert seen == ["1.6.4512"]
    assert language == "fr"
    assert values == {"Greeting": "Hello"}
