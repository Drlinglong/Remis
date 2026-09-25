"""Approval, ownership, snapshot and GUI/Agent route contract checks."""
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.agent_service import AgentRegistry
from scripts.core.services import translation_package_workflow as workflow
from scripts.routers.translation_packages import router


@pytest.fixture
def package_api(tmp_path, monkeypatch):
    real_inspect = workflow.mars.inspect_package_inputs
    real_build = workflow.mars.build_package
    source = tmp_path / "source"
    output = tmp_path / "zh-CN-example"
    source.mkdir()
    output.mkdir()
    (source / "ModTexts.csv").write_text("source", encoding="utf-8")
    (output / "ModTexts.csv").write_text("translation", encoding="utf-8")
    projects = {key: {"project_id": key, "game_id": "surviving_mars", "source_path": str(source)}
                for key in ("project-a", "project-b")}
    sidecar = {"config": {"translation_dirs": [str(output)]}}
    manager = SimpleNamespace(get_project=AsyncMock(side_effect=lambda key: deepcopy(projects.get(key))),
                              _read_project_sidecar=Mock(side_effect=lambda _: deepcopy(sidecar)))
    monkeypatch.setattr(workflow, "project_manager", manager)
    monkeypatch.setattr(workflow, "APP_DATA_DIR", str(tmp_path / "runtime"))
    registry = AgentRegistry(str(tmp_path / "registry.json"))
    monkeypatch.setattr(workflow, "agent_registry", registry)
    monkeypatch.setattr(workflow.mars, "read_source_metadata", lambda _: {"id": "original", "title": "Example"})

    def inspect(source_root, translation_root, language_code, **kwargs):
        fingerprint = hashlib.sha256((Path(translation_root) / "ModTexts.csv").read_bytes()).hexdigest()
        return {"fingerprint": fingerprint, "warnings": [], "installation_steps": ["Enable both Mods."],
                "package": {"mod_id": "remisExample", "title": "Example Chinese", "language": "Schinese",
                            "source_mod_id": "original", "files": [{"path": "metadata.lua", "size_bytes": 12}],
                            "total_size_bytes": 12}}

    def build(source_root, translation_root, language_code, destination, **kwargs):
        assert kwargs["expected_fingerprint"] == inspect(source_root, translation_root, language_code)["fingerprint"]
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "metadata.lua").write_text("safe fixture", encoding="utf-8")
        return {"package_path": str(destination), "files": [{"path": "metadata.lua", "size_bytes": 12}],
                "size_bytes": 12, "installation_steps": ["Enable both Mods."]}

    monkeypatch.setattr(workflow.mars, "inspect_package_inputs", inspect)
    build_mock = Mock(side_effect=build)
    monkeypatch.setattr(workflow.mars, "build_package", build_mock)
    app = FastAPI()
    app.include_router(router)
    return SimpleNamespace(client=TestClient(app), output=output, source=source, projects=projects,
                           sidecar=sidecar, registry=registry, build=build_mock, root=tmp_path,
                           real_inspect=real_inspect, real_build=real_build)


def _plan(api, prefix="/api/agent", **overrides):
    return api.client.post(prefix + "/projects/project-a/translation-package/plan", json={
        "output_folder_name": api.output.name, "target_language": "zh-CN", **overrides,
    })


@pytest.mark.parametrize("prefix", ["/api", "/api/agent"])
def test_options_and_preview_are_read_only_and_both_routes_share_contract(package_api, prefix):
    api = package_api
    options = api.client.get(prefix + "/projects/project-a/translation-package/options")
    assert options.status_code == 200
    assert options.json()["source_mod"] == {"id": "original", "title": "Example"}
    assert options.json()["translation_outputs"][0]["output_folder_name"] == api.output.name
    result = _plan(api, prefix)
    assert result.status_code == 200
    assert result.json()["risk"]["may_use_paid_api"] is False
    assert result.json()["requires_approval"] is True
    api.build.assert_not_called()
    assert not (api.root / "runtime").exists()


def test_approval_required_then_single_use_export_succeeds(package_api):
    api = package_api
    plan = _plan(api).json()
    url = "/api/agent/projects/project-a/translation-package"
    rejected = api.client.post(url, json={"plan_id": plan["plan_id"]})
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "approval_required"
    api.build.assert_not_called()
    result = api.client.post(url, json={"plan_id": plan["plan_id"], "approved": True})
    assert result.status_code == 200
    assert Path(result.json()["package_path"]).is_relative_to(api.root / "runtime" / "translation_packages")
    assert result.json()["runtime_verified"] is False
    repeated = api.client.post(url, json={"plan_id": plan["plan_id"], "approved": True})
    assert repeated.status_code == 409
    api.build.assert_called_once()


@pytest.mark.parametrize("name", ["../foreign", "unknown", "..", "folder/child"])
def test_unassociated_or_traversal_output_is_rejected(package_api, name):
    response = _plan(package_api, output_folder_name=name)
    assert response.status_code in {400, 409}
    package_api.build.assert_not_called()


def test_changed_translation_requires_new_preview(package_api):
    api = package_api
    plan = _plan(api).json()
    (api.output / "ModTexts.csv").write_text("modified after preview", encoding="utf-8")
    result = api.client.post("/api/projects/project-a/translation-package", json={"plan_id": plan["plan_id"], "approved": True})
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "stale_plan"
    api.build.assert_not_called()


def test_cross_project_plan_cannot_generate_files(package_api):
    api = package_api
    plan = _plan(api).json()
    result = api.client.post("/api/agent/projects/project-b/translation-package", json={"plan_id": plan["plan_id"], "approved": True})
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "invalid_plan"
    api.build.assert_not_called()


def test_translation_plan_cannot_be_used_as_package_plan(package_api):
    api = package_api
    plan = api.registry.create_plan(project_id="project-a", execution_args={}, dry_run=False, summary="not an export")
    result = api.client.post("/api/agent/projects/project-a/translation-package", json={"plan_id": plan["plan_id"], "approved": True})
    assert result.status_code == 409
    api.build.assert_not_called()


def test_other_games_and_wrong_language_cannot_use_mars_export(package_api):
    api = package_api
    assert _plan(api, target_language="fr").status_code == 422
    api.projects["project-a"]["game_id"] = "rimworld"
    assert _plan(api).status_code == 409
    api.build.assert_not_called()


def test_removed_output_association_invalidates_approved_plan(package_api):
    api = package_api
    plan = _plan(api).json()
    api.sidecar["config"]["translation_dirs"] = []
    result = api.client.post("/api/projects/project-a/translation-package", json={"plan_id": plan["plan_id"], "approved": True})
    assert result.status_code == 409
    api.build.assert_not_called()


def test_real_builder_through_agent_api_preserves_inputs_and_registers_mounted_csv(package_api, monkeypatch):
    api = package_api
    monkeypatch.setattr(workflow.mars, "inspect_package_inputs", api.real_inspect)
    monkeypatch.setattr(workflow.mars, "build_package", api.real_build)
    (api.source / "metadata.lua").write_text(
        "return PlaceObj('ModDef', {'id', 'original', 'title', 'Example'})", encoding="utf-8")
    header = "sep=,\nID,Text,Translation,VoiceActor,Context\n"
    source_csv = header + "100,<em>Ore</em>,,,resource\n"
    translated_csv = header + "100,<em>Ore</em>,<em>矿石</em>,,resource\n"
    (api.source / "ModTexts.csv").write_text(source_csv, encoding="utf-8")
    (api.output / "ModTexts.csv").write_text(translated_csv, encoding="utf-8")
    response = _plan(api)
    assert response.status_code == 200, response.text
    plan = response.json()
    response = api.client.post("/api/agent/projects/project-a/translation-package", json={
        "plan_id": plan["plan_id"], "approved": True,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    destination = Path(result["package_path"])
    relative_csv = "Localization/Schinese/ModTexts.csv"
    mounted_csv = f"Mod/{plan['package']['mod_id']}/{relative_csv}"
    assert sorted(item["path"] for item in result["files"]) == [relative_csv, "items.lua", "metadata.lua"]
    assert mounted_csv in (destination / "metadata.lua").read_text(encoding="utf-8")
    assert mounted_csv in (destination / "items.lua").read_text(encoding="utf-8")
    assert "<em>矿石</em>" in (destination / relative_csv).read_text(encoding="utf-8")
    assert (api.source / "ModTexts.csv").read_text(encoding="utf-8") == source_csv
    assert (api.output / "ModTexts.csv").read_text(encoding="utf-8") == translated_csv
