"""Incremental previews must not read linked resources outside the selected scope."""

import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.services.agent_incremental_preview_service import build_incremental_preview
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.incremental_source_paths import checked_source_path, source_root


def _symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"Creating filesystem symlinks is unavailable: {exc}")


def _reparse(monkeypatch, candidate: Path) -> None:
    original = Path.lstat

    def metadata(path):
        result = original(path)
        if path == candidate:
            return SimpleNamespace(st_mode=result.st_mode,
                                   st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return result

    monkeypatch.setattr(Path, "lstat", metadata)


def _table(path: Path) -> None:
    path.write_text("ID,Text,Translation,VoiceActor,Context\n1,Outside scope marker,,,\n", encoding="utf-8")


@pytest.mark.parametrize("game_id,filename", [("stellaris", "strings_l_english.yml"), ("surviving_mars", "ModTexts.csv")])
@pytest.mark.parametrize("outside", [False, True])
def test_snapshot_rejects_leaf_links_even_when_target_is_inside(tmp_path, game_id, filename, outside):
    from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
    root = tmp_path / "source"
    root.mkdir()
    target = (tmp_path if outside else root) / "ordinary.txt"
    target.write_text('OUTSIDE_SCOPE_MARKER:0 "Outside scope marker"\n', encoding="utf-8")
    _symlink(root / filename, target)

    with pytest.raises(ValueError, match="Linked incremental source resource"):
        IncrementalSnapshotService().build_snapshot(str(root), LANGUAGE_BY_CODE["en"],
                                                   game_profile=GAME_PROFILES_BY_ID[game_id])


def test_snapshot_rejects_windows_directory_reparse_before_descending(tmp_path, monkeypatch):
    root = tmp_path / "source"
    directory = root / "localisation"
    directory.mkdir(parents=True)
    _reparse(monkeypatch, directory)
    with pytest.raises(ValueError, match="Linked incremental source resource"):
        IncrementalSnapshotService().build_snapshot(str(root), {"name_en": "English"})


@pytest.mark.parametrize("game_id,filename", [("stellaris", "strings_l_english.yml"), ("surviving_mars", "ModTexts.csv")])
def test_snapshot_rejects_windows_leaf_reparse(tmp_path, monkeypatch, game_id, filename):
    from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
    resource = tmp_path / filename
    resource.write_text("This content must not be parsed", encoding="utf-8")
    _reparse(monkeypatch, resource)
    with pytest.raises(ValueError, match="Linked incremental source resource"):
        IncrementalSnapshotService().build_snapshot(str(tmp_path), LANGUAGE_BY_CODE["en"],
                                                   game_profile=GAME_PROFILES_BY_ID[game_id])


@pytest.mark.parametrize("game_id", ["rimworld", "project_zomboid"])
def test_adapter_tree_checked_before_discovery(tmp_path, monkeypatch, game_id):
    resource = tmp_path / "metadata.xml"
    resource.write_text("This content must not be parsed", encoding="utf-8")
    _reparse(monkeypatch, resource)

    def discover(*_args):
        pytest.fail("Adapters must not discover or parse an unchecked source tree")

    monkeypatch.setattr("scripts.core.game_adapters.workflow_bridge.build_snapshot", discover)
    with pytest.raises(ValueError, match="Linked incremental source resource"):
        IncrementalSnapshotService().build_snapshot(str(tmp_path), {"name_en": "English"},
                                                   game_profile={"id": game_id})


@pytest.mark.parametrize("name", [".remis_project.json", "mars_lua_manifest.json"])
@pytest.mark.asyncio
async def test_preview_rejects_reparse_manifests_before_read(tmp_path, monkeypatch, name):
    manifest = tmp_path / name
    manifest.write_text("{}", encoding="utf-8")
    _reparse(monkeypatch, manifest)
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path != manifest, "Redirected manifest content must never be read"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    manager = SimpleNamespace(get_project=_project)
    with pytest.raises(ValueError, match="Linked incremental source resource"):
        await build_incremental_preview("p1", tmp_path, ["zh-CN"], project_manager=manager)


async def _project(_project_id):
    return {"project_id": "p1", "game_id": "surviving_mars", "source_language": "en", "source_path": "old-source"}


def test_checked_path_rejects_lexical_and_resolved_escape(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    external = tmp_path / "external.csv"
    _table(external)
    with pytest.raises(ValueError, match="outside the selected root"):
        checked_source_path(root, external)
    with pytest.raises(ValueError, match="outside the selected root"):
        checked_source_path(root, root / ".." / "external.csv")


@pytest.mark.asyncio
async def test_preview_supports_new_root_outside_old_project(tmp_path, monkeypatch):
    root = tmp_path / "new-source"
    root.mkdir()
    _table(root / "ModTexts.csv")
    monkeypatch.setattr("scripts.core.services.agent_incremental_preview_service.IncrementalArchiveService",
                        lambda: SimpleNamespace(get_language_entries=lambda *_args: []))
    result = await build_incremental_preview("p1", root, ["zh-CN"], project_manager=SimpleNamespace(get_project=_project))
    assert result["source_path"] == str(root.resolve())
    assert result["summary"]["new"] == 1


def test_selected_root_alias_is_resolved_and_supported(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    _table(real / "ModTexts.csv")
    alias = tmp_path / "selected"
    _symlink(alias, real, directory=True)
    root = source_root(alias)
    assert root == real.resolve()
    assert checked_source_path(root, root / "ModTexts.csv").is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
@pytest.mark.parametrize("selected_root", [True, False])
def test_windows_junction_is_allowed_only_as_the_selected_root(tmp_path, selected_root):
    from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
    real = tmp_path / "real"
    real.mkdir()
    _table(real / "ModTexts.csv")
    junction = tmp_path / "junction"
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(real)],
                   check=True, capture_output=True)
    service = IncrementalSnapshotService()
    if selected_root:
        snapshot = service.build_snapshot(str(junction), LANGUAGE_BY_CODE["en"],
                                          game_profile=GAME_PROFILES_BY_ID["surviving_mars"])
        assert snapshot[0]["full_path"].parent == real.resolve()
    else:
        with pytest.raises(ValueError, match="Linked incremental source resource"):
            service.build_snapshot(str(tmp_path), LANGUAGE_BY_CODE["en"],
                                   game_profile=GAME_PROFILES_BY_ID["surviving_mars"])
