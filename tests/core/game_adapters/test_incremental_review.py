"""Offline incremental/review coverage through the real structured adapters."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.archive_manager import ArchiveManager
from scripts.core.game_adapters import workflow_bridge
from scripts.core.game_adapters.output_records import output_record
from scripts.core.services.incremental_build_service import IncrementalBuildService
from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService


SOURCE = {"code": "en", "key": "l_english"}
TARGET = {"code": "zh-CN", "key": "l_simp_chinese"}
PROFILE = {
    "project_zomboid": {"id": "project_zomboid", "game_version": "42.15.0"},
    "rimworld": {"id": "rimworld", "game_version": "1.6"},
}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _make_mod(root: Path, game: str, payload: str, name: str = "UI") -> Path:
    if game == "project_zomboid":
        _write(root / "common/mod.info", "id=incremental.fixture\nname=Incremental Fixture\n")
        return _write(root / f"common/media/lua/shared/Translate/EN/{name}.json", payload)
    _write(root / "About/About.xml", "<ModMetaData><packageId>incremental.fixture</packageId><supportedVersions><li>1.6</li></supportedVersions></ModMetaData>")
    return _write(root / f"Languages/English/Keyed/{name}.xml", f"<LanguageData>{payload}</LanguageData>")


def _archive(manager: ArchiveManager, project_id: str, files: list[dict], translations: dict[str, list[str]]) -> None:
    mod_id = manager.get_or_create_mod_entry("Incremental Fixture", project_id)
    archive_files = [{
        "filename": item["filename"], "file_path": item["file_path"],
        "texts_to_translate": item["texts_to_translate"],
        "key_map": item["key_map"],
    } for item in files]
    version = manager.create_source_version(mod_id, archive_files)
    manager.archive_translated_results(version, translations, archive_files, "zh-CN")


def _snapshot(root: Path, game: str, profile: dict | None = None) -> list[dict]:
    return IncrementalSnapshotService().build_snapshot(
        str(root), SOURCE, game_profile=profile or PROFILE[game]
    )


def _prepare(files: list[dict], history: list[dict], root: Path, game: str):
    diff = IncrementalDiffService()
    return IncrementalPreparationService().prepare_language_update(
        current_files_data=files,
        history_index=diff.build_history_index(history),
        diff_service=diff,
        target_lang_info=TARGET,
        source_lang_info=SOURCE,
        game_profile=PROFILE[game],
        mod_context="", selected_provider="mock", source_path=str(root),
        base_output_dir=root.parent / "output", total_targets=1,
    )


@pytest.fixture
def archive(tmp_path, monkeypatch):
    import scripts.core.archive_manager as module
    monkeypatch.setattr(module, "MODS_CACHE_DB_PATH", str(tmp_path / "archive.sqlite"))
    manager = ArchiveManager()
    manager.initialize_database()
    yield manager
    manager.close()


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
def test_incremental_version_change_and_unique_move_reuse_history(tmp_path, archive, game):
    root = tmp_path / "source"
    if game == "project_zomboid":
        first = _make_mod(root, game, '{"Greeting":"Hello"}')
    else:
        first = _make_mod(root, game, "<Greeting>Hello</Greeting>")
    initial = _snapshot(root, game)
    file_data = initial[0]
    _archive(archive, f"{game}-project", initial, {file_data["file_path"]: ["你好"]})
    history = archive.get_entries(project_id=f"{game}-project", language="zh-CN")

    # A game-version metadata change has no bearing on source identity or text.
    changed_profile = {**PROFILE[game], "game_version": "42.16.0" if game == "project_zomboid" else "1.6.1"}
    same = _snapshot(root, game, changed_profile)
    result = _prepare(same, history, root, game)
    assert result["summary"] == {"total": 1, "new": 0, "changed": 0, "unchanged": 1}
    assert result["file_tasks_for_ai"] == []

    moved = first.parent / "nested" / first.name
    moved.parent.mkdir()
    first.replace(moved)
    after_move = _snapshot(root, game, changed_profile)
    result = _prepare(after_move, history, root, game)
    assert result["summary"]["unchanged"] == 1
    assert result["processing_records"][0]["full_file_entries"][0]["translation"] == "你好"
    assert result["file_tasks_for_ai"] == []


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
def test_source_change_keeps_human_translation_and_builds_pending_review(tmp_path, archive, game):
    root = tmp_path / "source"
    source = _make_mod(root, game, '{"Greeting":"Hello"}' if game == "project_zomboid"
                       else "<Greeting>Hello</Greeting>")
    initial = _snapshot(root, game)
    file_data = initial[0]
    project_id = f"{game}-review"
    _archive(archive, project_id, initial, {file_data["file_path"]: ["人工译文"]})
    source.write_bytes((('{"Greeting":"Hello again"}' if game == "project_zomboid"
                         else "<LanguageData><Greeting>Hello again</Greeting></LanguageData>")).encode("utf-8"))
    current = _snapshot(root, game)
    history = archive.get_entries(project_id=project_id, language="zh-CN")
    result = _prepare(current, history, root, game)
    entry = result["processing_records"][0]["full_file_entries"][0]
    assert entry["translation"] == "人工译文"
    assert entry["resolution"] == "review"
    assert result["file_tasks_for_ai"] == []

    built = IncrementalBuildService().build_language_output(
        processing_records=result["processing_records"], translated_results={},
        source_path=str(root), lang_output_dir=tmp_path / "output", source_lang_info=SOURCE,
        target_lang_info=TARGET, game_profile=PROFILE[game],
    )
    output = Path(built["written_files"][0])
    _, record = output_record(output)
    assert record["entries"][0]["needs_review"] is True

    # The manifest is consumed by the next incremental preparation. Pending review
    # remains visible and still bypasses model submission.
    sidecar = {"config": {"translation_dirs": [str(tmp_path / "output")]}}
    _write(root / ".remis_project.json", json.dumps(sidecar))
    rerun = _prepare(_snapshot(root, game), history, root, game)
    assert rerun["processing_records"][0]["full_file_entries"][0]["resolution"] == "review"
    assert rerun["file_tasks_for_ai"] == []


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
def test_same_filename_in_distinct_directories_keeps_archive_translations_separate(tmp_path, archive, game):
    root = tmp_path / "source"
    if game == "project_zomboid":
        _write(root / "common/mod.info", "id=incremental.fixture\nname=Incremental Fixture\n")
        _write(root / "common/media/lua/shared/Translate/EN/UI.json", '{"First":"One"}')
        _write(root / "common/media/lua/shared/Translate/EN/nested/UI.json", '{"Second":"Two"}')
        translations = ["第一"]
        second_translation = "第二"
    else:
        _write(root / "About/About.xml", "<ModMetaData><packageId>incremental.fixture</packageId></ModMetaData>")
        _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><First>One</First></LanguageData>")
        _write(root / "Languages/English/Keyed/nested/UI.xml", "<LanguageData><Second>Two</Second></LanguageData>")
        translations = ["第一"]
        second_translation = "第二"
    files = _snapshot(root, game)
    assert len(files) == 2
    files.sort(key=lambda item: item["file_path"])
    paths = [item["file_path"] for item in files]
    _archive(archive, f"{game}-same-name", files,
             {paths[0]: translations, paths[1]: [second_translation]})
    history = archive.get_entries(project_id=f"{game}-same-name", language="zh-CN")
    result = _prepare(files, history, root, game)
    records = result["processing_records"]
    assert [record["full_file_entries"][0]["translation"] for record in records] == ["第一", "第二"]
    assert result["file_tasks_for_ai"] == []


def test_rimworld_api_language_code_discovers_keyed_and_defs_resources(tmp_path):
    from scripts.app_settings import LANGUAGES

    root = tmp_path / "rimworld-source"
    _write(root / "About/About.xml", "<ModMetaData><packageId>incremental.fixture</packageId></ModMetaData>")
    _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><Greeting>Hello</Greeting></LanguageData>")
    _write(root / "Defs/ThingDefs/Items.xml", "<Defs><ThingDef><defName>Crystal</defName><label>crystal</label></ThingDef></Defs>")
    actual_english = next(item for item in LANGUAGES.values() if item["code"] == "en")
    for language in (actual_english, {"code": "en"}):
        found = workflow_bridge.discover_files(root, PROFILE["rimworld"], language)
        assert len(found) == 2
        assert {item["adapter_metadata"]["kind"] for item in found} == {"keyed", "defs"}


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
@pytest.mark.asyncio
async def test_proofread_save_updates_archive_acknowledges_and_rolls_back_failure(tmp_path, archive, game, monkeypatch):
    root = tmp_path / "source"
    source = _make_mod(root, game, '{"Greeting":"Hello"}' if game == "project_zomboid"
                       else "<Greeting>Hello</Greeting>")
    snapshot = _snapshot(root, game)
    item = snapshot[0]
    project_id = f"{game}-proofread"
    _archive(archive, project_id, snapshot, {item["file_path"]: ["机器翻译"]})
    source.write_bytes((('{"Greeting":"Hello again"}' if game == "project_zomboid"
                         else "<LanguageData><Greeting>Hello again</Greeting></LanguageData>")).encode("utf-8"))
    history = archive.get_entries(project_id=project_id, language="zh-CN")
    review = _prepare(_snapshot(root, game), history, root, game)
    assert review["processing_records"][0]["full_file_entries"][0]["resolution"] == "review"
    built = IncrementalBuildService().build_language_output(
        processing_records=review["processing_records"],
        translated_results={}, source_path=str(root), lang_output_dir=tmp_path / "out",
        source_lang_info=SOURCE, target_lang_info=TARGET, game_profile=PROFILE[game],
    )
    target = Path(built["written_files"][0])
    _, before = output_record(target)
    source_rel = item["file_path"]
    project = {"project_id": project_id, "name": "Incremental Fixture", "game_id": game,
               "source_language": "en", "source_path": str(root)}
    service = SimpleNamespace(archive_manager=archive,
                              project_manager=SimpleNamespace(update_file_status_with_kanban_sync=_async_noop))
    bridge = __import__("scripts.core.game_adapters.proofreading", fromlist=["save_proofread_data"])
    translated_key = item["parsed_entries"][0][0]
    await bridge.save_proofread_data(service, project, str(target), "file", [
        {"key": translated_key, "translation": "校对后"}
    ])
    _, after = output_record(target)
    assert after["entries"][0]["needs_review"] is False
    assert archive.get_entries(project_id=project_id, file_path=source_rel, language="zh-CN")[0]["translation"] == "校对后"

    original = target.read_bytes()
    original_update = archive.update_translations
    def fail_update(*args, **kwargs):
        raise RuntimeError("archive write failed")
    monkeypatch.setattr(archive, "update_translations", fail_update)
    with pytest.raises(RuntimeError, match="archive write failed"):
        await bridge.save_proofread_data(service, project, str(target), "file", [
            {"key": translated_key, "translation": "must roll back"}
        ])
    assert target.read_bytes() == original
    monkeypatch.setattr(archive, "update_translations", original_update)


async def _async_noop(*args, **kwargs):
    return None
