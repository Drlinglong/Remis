from __future__ import annotations

import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.game_adapters.workflow_bridge import MANIFEST
from scripts.core.services.agent_game_output_service import (
    AgentGameOutputError,
    approve_game_output,
    filter_game_actions,
    guard_deployment,
    preview_game_output,
)


def _manifest(root: Path, game_id: str = "project_zomboid", *, exists: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)
    metadata = (root / "About/About.xml" if game_id == "rimworld"
                else root / "common/mod.info")
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text("<ModMetaData/>" if game_id == "rimworld" else "id=fixture.mod\n",
                        encoding="utf-8")
    resource = "CH/media/lua/shared/Translate/CH/UI.json"
    (root / resource).parent.mkdir(parents=True, exist_ok=True)
    if exists:
        (root / resource).write_text('{"UI_Test":"翻译"}\n', encoding="utf-8")
    (root / MANIFEST).write_text(json.dumps({
        "schema_version": 1,
        "game_id": game_id,
        "source_mod_id": "fixture.mod",
        "files": {resource: {"language": "zh-CN", "source_path": "media/UI.json"}},
    }), encoding="utf-8")


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
def test_structured_preview_lists_only_existing_manifest_resources(tmp_path: Path, game_id: str):
    destination = tmp_path / "dest"
    output = destination / "job-output"
    _manifest(output, game_id)

    result = preview_game_output(
        {"game_id": game_id}, [output], destination_root=destination,
    )

    assert result["ready"] is True
    assert result["export_mode"] == "manual_install"
    assert result["runtime_verified"] is False
    assert result["validation_scope"] == "artifact_presence_only"
    assert result["target_path"] is None
    assert result["requires_approval"] is False
    assert result["allowed_actions"] == ["inspect_local_output"]
    assert result["packages"] == [{
        "package_root": str(output.resolve()),
        "language": "zh-CN",
        "source_mod_id": "fixture.mod",
        "resources": ["CH/media/lua/shared/Translate/CH/UI.json"],
        "runtime_verified": False,
        "export_mode": "manual_install",
        "target_path": None,
        "requires_approval": False,
    }]


def test_structured_preview_does_not_claim_ready_without_manifest_resource(tmp_path: Path):
    destination = tmp_path / "dest"
    output = destination / "job-output"
    _manifest(output, exists=False)

    result = preview_game_output(
        {"game_id": "project_zomboid"}, [output], destination_root=destination,
    )

    assert result["ready"] is False
    assert result["packages"] == []
    assert result["allowed_actions"] == []
    assert result["diagnostics"][0]["code"] == "local_package_manifest_missing"


@pytest.mark.parametrize("manifest_json", ["null", "[]", "42", '"manifest"'])
def test_structured_preview_ignores_non_object_manifest_roots(tmp_path: Path, manifest_json: str):
    destination = tmp_path / "dest"
    output = destination / "job-output"
    _manifest(output)
    (output / MANIFEST).write_text(manifest_json, encoding="utf-8")

    result = preview_game_output(
        {"game_id": "project_zomboid"}, [output], destination_root=destination,
    )

    assert result["ready"] is False
    assert result["packages"] == []


def test_reparse_detection_uses_windows_lstat_attribute_for_python_310_junctions(monkeypatch, tmp_path: Path):
    from scripts.core.services import agent_game_output_service as service

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not reparse_flag:
        pytest.skip("Windows reparse-point file attributes are unavailable")
    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
    monkeypatch.setattr(Path, "lstat", lambda _path: SimpleNamespace(
        st_mode=stat.S_IFDIR, st_file_attributes=reparse_flag,
    ))

    assert service._is_reparse(tmp_path / "junction") is True


def test_structured_preview_rejects_mismatched_game_and_unsafe_paths(tmp_path: Path):
    destination = tmp_path / "dest"
    output = destination / "output"
    _manifest(output, "rimworld")

    mismatch = preview_game_output(
        {"game_id": "project_zomboid"}, [output], destination_root=destination,
    )
    escaped = preview_game_output(
        {"game_id": "project_zomboid"}, [tmp_path / "outside"], destination_root=destination,
    )

    assert mismatch["ready"] is False
    assert escaped["ready"] is False


def test_one_missing_manifest_resource_blocks_the_whole_package(tmp_path: Path):
    destination = tmp_path / "dest"
    output = destination / "output"
    _manifest(output)
    manifest_path = output / MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["files"]["missing/other.json"] = {"language": "fr"}
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    result = preview_game_output(
        {"game_id": "project_zomboid"}, [output], destination_root=destination,
    )

    assert result["ready"] is False
    assert result["packages"] == []


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
def test_structured_preview_requires_game_metadata_file(tmp_path: Path, game_id: str):
    destination = tmp_path / "dest"
    output = destination / "output"
    _manifest(output, game_id)
    metadata = output / ("About/About.xml" if game_id == "rimworld" else "common/mod.info")
    metadata.unlink()

    result = preview_game_output(
        {"game_id": game_id}, [output], destination_root=destination,
    )

    assert result["ready"] is False
    assert result["packages"] == []


def test_surviving_mars_preview_lists_csv_as_local_files_only(tmp_path: Path):
    destination = tmp_path / "dest"
    output = destination / "mars-job"
    csv_file = output / "translations" / "CHS.csv"
    csv_file.parent.mkdir(parents=True)
    csv_file.write_text("key,value\n", encoding="utf-8")
    (output / "unrelated.yml").write_text("l_english:\n", encoding="utf-8")

    result = preview_game_output(
        {"game_id": "surviving_mars"}, [output], destination_root=destination,
    )

    assert result == {
        "game_id": "surviving_mars",
        "export_mode": "local_files",
        "local_files": [str(csv_file.resolve())],
        "ready": True,
        "runtime_verified": False,
        "validation_scope": "artifact_presence_only",
        "target_path": None,
        "requires_approval": False,
        "allowed_actions": ["inspect_local_output"],
    }


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld", "surviving_mars"])
def test_deployment_guard_rejects_game_override_and_manual_game_deployment(game_id: str):
    with pytest.raises(AgentGameOutputError) as mismatch:
        guard_deployment(game_id, "victoria3")
    assert (mismatch.value.code, mismatch.value.status_code) == ("game_id_mismatch", 400)

    with pytest.raises(AgentGameOutputError) as unsupported:
        approve_game_output({"game_id": game_id}, game_id)
    assert (unsupported.value.code, unsupported.value.status_code) == (
        "unsupported_game_deployment", 409,
    )


def test_game_actions_keep_review_repair_and_only_offer_existing_local_output():
    assert filter_game_actions(
        "rimworld", ["approve_export", "repair", "manual_review"], has_output=True,
    ) == ["repair", "manual_review", "inspect_local_output"]
    assert filter_game_actions(
        "project_zomboid", ["approve_export", "repair"], has_output=False,
    ) == ["repair"]
    assert filter_game_actions(
        "victoria3", ["approve_export", "repair"], has_output=True,
    ) == ["approve_export", "repair"]
