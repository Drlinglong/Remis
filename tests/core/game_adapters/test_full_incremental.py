"""Full offline run_incremental_update coverage for structured game adapters."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.archive_manager import ArchiveManager
from scripts.core.game_adapters.output_records import output_files, output_record
from scripts.core.services.incremental_archive_service import IncrementalArchiveService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.workflows import update_translate


SOURCE = {"code": "en", "key": "l_english"}
TARGET = {"code": "zh-CN", "key": "l_simp_chinese"}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _fixture(root: Path, game: str) -> tuple[Path, dict[str, str]]:
    if game == "project_zomboid":
        _write(root / "common/mod.info", "id=full.incremental\nname=Full Incremental\n")
        _write(root / "common/media/lua/shared/Translate/EN/UI.json", '{"Greeting":"Hello %1"}')
        _write(root / "common/media/lua/shared/Translate/EN/nested/UI.json", '{"Other":"Other"}')
        _write(root / "common/Lua/DoNotCopy.lua", "return 'not localization data'")
        _write(root / "common/Textures/DoNotCopy.txt", "asset marker")
        _write(root / "common/Assemblies/DoNotCopy.dll", "fake fixture bytes")
        return root / "common/media/lua/shared/Translate/EN/UI.json", {
            "UI::Greeting": "你好 %1", "UI::Other": "其他",
        }

    _write(root / "About/About.xml", "<ModMetaData><packageId>full.incremental</packageId><supportedVersions><li>1.6</li></supportedVersions></ModMetaData>")
    source = _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><Greeting>Hello {0}</Greeting></LanguageData>")
    _write(root / "Defs/ThingDefs/Shared.xml", "<Defs><ThingDef><defName>Crystal</defName><label>crystal</label></ThingDef></Defs>")
    _write(root / "Defs/RecipeDefs/Shared.xml", "<Defs><RecipeDef><defName>MakeCrystal</defName><jobString>Craft crystal</jobString></RecipeDef></Defs>")
    _write(root / "Assemblies/DoNotCopy.dll", "fake fixture bytes")
    _write(root / "Textures/DoNotCopy.txt", "asset marker")
    _write(root / "Source.lua", "return 'not localization data'")
    return source, {
        "Greeting": "你好 {0}",
        "ThingDef::Crystal.label": "晶体",
        "RecipeDef::MakeCrystal.jobString": "制作晶体",
    }


def _seed_archive(manager: ArchiveManager, project_id: str, project_name: str,
                  files: list[dict], values: dict[str, str]) -> None:
    archive_files = [{
        "filename": item["filename"], "file_path": item["file_path"],
        "texts_to_translate": item["texts_to_translate"],
        "key_map": item["key_map"],
    } for item in files]
    mod_id = manager.get_or_create_mod_entry(project_name, project_id)
    version = manager.create_source_version(mod_id, archive_files)
    per_file: dict[str, list[str]] = {}
    for item in archive_files:
        keys = [item["key_map"][index]["key_part"] for index in range(len(item["texts_to_translate"]))]
        per_file[item["file_path"]] = [values[key] for key in keys]
    manager.archive_translated_results(version, per_file, archive_files, "zh-CN")


def _entry_values(manager: ArchiveManager, project_id: str) -> dict[str, tuple[str, str]]:
    return {row["key"]: (row["original"], row["translation"])
            for row in manager.get_entries(project_id=project_id, language="zh-CN")}


def _source_change(game: str, source: Path) -> None:
    if game == "project_zomboid":
        _write(source, '{"Greeting":"Hello again %1","Added":"Fresh %1"}')
    else:
        _write(source, "<LanguageData><Greeting>Hello again {0}</Greeting><Added>Fresh {0}</Added></LanguageData>")


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    import scripts.core.archive_manager as archive_module
    import scripts.core.services.incremental_package_service as package_module
    db_path = tmp_path / "archive.sqlite"
    monkeypatch.setattr(archive_module, "MODS_CACHE_DB_PATH", str(db_path))
    manager = ArchiveManager()
    manager.initialize_database()
    output_root = tmp_path / "generated"
    monkeypatch.setattr(update_translate, "DEST_DIR", str(output_root))
    monkeypatch.setattr(package_module, "DEST_DIR", str(output_root))
    monkeypatch.setattr(update_translate, "IncrementalArchiveService",
                        lambda: IncrementalArchiveService(am=manager))

    project = {"project_id": "full-incremental", "name": "Full Incremental",
               "game_id": "", "source_language": "en", "source_path": ""}
    pm = update_translate.project_manager
    monkeypatch.setattr(pm, "get_project", AsyncMock(side_effect=lambda _project_id: dict(project)))
    monkeypatch.setattr(pm, "log_history_event", AsyncMock())
    monkeypatch.setattr(pm, "add_translation_path", AsyncMock())
    yield manager, output_root, project
    manager.close()


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
@pytest.mark.asyncio
async def test_full_incremental_wrapper_preserves_review_and_emits_only_localization(
    tmp_path, monkeypatch, run_env, game
):
    manager, output_root, project = run_env
    root = tmp_path / "source"
    source_file, baseline = _fixture(root, game)
    project.update(game_id=game, source_path=str(root))
    profile = {"id": game, "game_version": "42.15.0" if game == "project_zomboid" else "1.6"}
    source_info = SOURCE
    snapshot = IncrementalSnapshotService().build_snapshot(
        str(root), source_info, game_profile=profile
    )
    _seed_archive(manager, project["project_id"], project["name"], snapshot, baseline)

    class MockProvider:
        provider_name = "offline-test"
        client = object()

        def __init__(self):
            self.inputs = []

        def translate_batch(self, batch):
            self.inputs.extend(batch.texts)
            batch.translated_texts = ["机译 " + text for text in batch.texts]
            return batch

    provider = MockProvider()
    monkeypatch.setattr("scripts.core.api_handler.get_handler", lambda *args, **kwargs: provider)
    _source_change(game, source_file)
    result = await update_translate.run_incremental_update(
        project_id=project["project_id"], target_lang_infos=[TARGET], source_lang_info=source_info,
        game_profile=profile, selected_provider="offline-test", model_name="offline-fixture",
        concurrency_limit=1, dry_run=False, custom_source_path=None, use_resume=False,
        embedded_workshop={"enabled": False}, reference_reuse={"enabled": False},
        translation_context_mode="none",
    )
    assert result["status"] == "success"
    assert result["summary"]["changed"] == 1
    assert result["summary"]["new"] == 1
    fresh_text = "Fresh %1" if game == "project_zomboid" else "Fresh {0}"
    assert fresh_text in provider.inputs
    assert not any(text.startswith("Hello again") for text in provider.inputs)
    first_output = Path(result["output_dirs"][0])
    generated = output_files(first_output, "zh-CN")
    assert generated
    all_output_files = [path for path in first_output.rglob("*") if path.is_file()]
    assert not any(path.suffix.lower() in {".dll", ".lua"} for path in all_output_files)
    assert not any("textures" in part.casefold() for path in all_output_files for part in path.parts)
    if game == "rimworld":
        assert any("DefInjected/ThingDef/" in path.replace("\\", "/") for path in generated)
        assert any("DefInjected/RecipeDef/" in path.replace("\\", "/") for path in generated)
        assert len([path for path in generated if "DefInjected" in path]) >= 2
    for path in generated:
        _, record = output_record(path)
        for entry in record["entries"]:
            if entry["key"] in {"UI::Greeting", "Greeting"}:
                assert entry["needs_review"] is True

    archived = _entry_values(manager, project["project_id"])
    changed_key = "UI::Greeting" if game == "project_zomboid" else "Greeting"
    added_key = "UI::Added" if game == "project_zomboid" else "Added"
    assert archived[changed_key] == ("Hello again %1" if game == "project_zomboid" else "Hello again {0}",
                                     baseline[changed_key])
    assert archived[added_key] == ("Fresh %1" if game == "project_zomboid" else "Fresh {0}",
                                   "机译 Fresh %1" if game == "project_zomboid" else "机译 Fresh {0}")
    if game == "project_zomboid":
        assert archived["UI::Other"] == ("Other", "其他")
    else:
        assert archived["ThingDef::Crystal.label"] == ("crystal", "晶体")
        assert archived["RecipeDef::MakeCrystal.jobString"] == ("Craft crystal", "制作晶体")

    sidecar = {"config": {"translation_dirs": [str(first_output)]}}
    _write(root / ".remis_project.json", json.dumps(sidecar))
    second = await update_translate.run_incremental_update(
        project_id=project["project_id"], target_lang_infos=[TARGET], source_lang_info=source_info,
        game_profile=profile, selected_provider="offline-test", model_name="offline-fixture",
        concurrency_limit=1, dry_run=False, custom_source_path=None, use_resume=False,
        embedded_workshop={"enabled": False}, reference_reuse={"enabled": False},
        translation_context_mode="none",
    )
    assert second["status"] == "success"
    assert second["summary"]["changed"] == 1
    assert provider.inputs == ["Fresh %1" if game == "project_zomboid" else "Fresh {0}"]
    second_output = Path(second["output_dirs"][0])
    second_files = output_files(second_output, "zh-CN")
    second_review = [entry for path in second_files
                     for entry in output_record(path)[1]["entries"]
                     if entry["key"] == changed_key]
    assert len(second_review) == 1 and second_review[0]["needs_review"] is True
