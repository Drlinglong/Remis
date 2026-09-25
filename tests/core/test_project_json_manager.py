"""Project metadata stays in the explicitly selected project directory."""

from pathlib import Path

import pytest

from scripts.core.project_json_manager import ProjectJsonManager


def test_sidecar_remains_usable_in_an_external_selected_project(tmp_path):
    root = tmp_path / "selected-mod"
    root.mkdir()
    manager = ProjectJsonManager(str(root))
    manager._save_json({"config": {}, "name": "中文项目"})
    assert manager._load_json()["name"] == "中文项目"
    assert Path(manager.json_path).parent == root


@pytest.mark.parametrize("redirect_kind", ["link", "resolved_parent"])
def test_sidecar_rejects_redirection_before_read_or_write(tmp_path, monkeypatch, redirect_kind):
    root = tmp_path / "selected-mod"
    root.mkdir()
    manager = ProjectJsonManager(str(root))
    sidecar = Path(manager.json_path)
    before = sidecar.read_bytes()
    outside = tmp_path / "outside.json"
    outside.write_text('{"private": true}', encoding="utf-8")
    original_resolve = Path.resolve
    original_is_symlink = Path.is_symlink
    if redirect_kind == "link":
        monkeypatch.setattr(Path, "is_symlink", lambda p: p == sidecar or original_is_symlink(p))
    else:
        monkeypatch.setattr(
            Path, "resolve",
            lambda p, *a, **kw: outside if p == sidecar else original_resolve(p, *a, **kw),
        )
    with pytest.raises(ValueError, match="sidecar"):
        ProjectJsonManager(str(root))
    assert manager._load_json() == {}
    with pytest.raises(ValueError, match="sidecar"):
        manager._save_json({"changed": True})
    assert sidecar.read_bytes() == before
    assert outside.read_text(encoding="utf-8") == '{"private": true}'
