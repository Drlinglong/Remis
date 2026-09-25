"""Two-language package and archive integration for both structured games."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.archive_manager import ArchiveManager
from scripts.core.game_adapters.output_records import output_files, output_record
from scripts.core.services.incremental_archive_service import IncrementalArchiveService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.workflows import update_translate


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _fixture(root: Path, game: str) -> tuple[Path, dict[str, str], int]:
    if game == "project_zomboid":
        _write(root / "common/mod.info", "id=multi.integration\nname=Multi Integration\n")
        _write(root / "common/media/lua/shared/Translate/EN/UI.json", '{"Greeting":"Hello %1"}')
        _write(root / "common/media/lua/shared/Translate/EN/nested/More.json", '{"Detail":"More text"}')
        return root / "common/media/lua/shared/Translate/EN/UI.json", {
            "UI::Greeting": "fr:Hello %1", "More::Detail": "fr:More text",
        }, 2
    _write(root / "About/About.xml", "<ModMetaData><packageId>multi.integration</packageId><supportedVersions><li>1.6</li></supportedVersions></ModMetaData>")
    keyed = _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><Greeting>Hello {0}</Greeting></LanguageData>")
    _write(root / "Defs/ThingDefs/Shared.xml", "<Defs><ThingDef><defName>Crystal</defName><label>crystal</label></ThingDef></Defs>")
    _write(root / "Defs/RecipeDefs/Shared.xml", "<Defs><RecipeDef><defName>MakeCrystal</defName><jobString>Craft crystal</jobString></RecipeDef></Defs>")
    return keyed, {
        "Greeting": "fr:Hello {0}", "ThingDef::Crystal.label": "fr:crystal",
        "RecipeDef::MakeCrystal.jobString": "fr:Craft crystal",
    }, 3


def _language_values(root: Path, languages: list[str], game: str) -> dict[str, dict[str, str]]:
    from scripts.core.game_adapters.registry import resource_adapter

    adapter = resource_adapter(game)
    result = {}
    for language in languages:
        values = {}
        for path in output_files(root, language):
            values.update({entry.key: entry.value for entry in adapter.parse(Path(path)).entries})
        result[language] = values
    return result


def _package_ids(root: Path, game: str, language_codes: list[str]) -> dict[str, str]:
    values = {}
    for code in language_codes:
        resources = output_files(root, code)
        assert resources
        package_roots = {output_record(path)[0] for path in resources}
        assert len(package_roots) == 1
        package_root = next(iter(package_roots))
        if game == "rimworld":
            values[code] = ET.parse(package_root / "About/About.xml").getroot().findtext("packageId", "")
        else:
            values[code] = next((line.partition("=")[2] for line in (package_root / "common/mod.info").read_text(encoding="utf-8").splitlines()
                                 if line.startswith("id=")), "")
    return values


def _seed_archive(manager, project_id, project_name, files, values_by_key):
    archive_files = [{"filename": item["filename"], "file_path": item["file_path"],
                      "texts_to_translate": item["texts_to_translate"], "key_map": item["key_map"]}
                     for item in files]
    mod_id = manager.get_or_create_mod_entry(project_name, project_id)
    version = manager.create_source_version(mod_id, archive_files)
    translations = {}
    for item in archive_files:
        keys = [item["key_map"][index]["key_part"] for index in range(len(item["texts_to_translate"]))]
        translations[item["file_path"]] = [values_by_key[key] for key in keys]
    for language in ("fr", "zh-CN"):
        localized = {path: [value.replace("fr:", "fr:") if language == "fr" else value.replace("fr:", "zh:")
                            for value in values]
                     for path, values in translations.items()}
        manager.archive_translated_results(version, localized, archive_files, language)


@pytest.fixture
def integration(tmp_path, monkeypatch):
    import scripts.core.archive_manager as archive_module
    import scripts.core.services.incremental_package_service as incremental_package
    import scripts.core.services.initial_translation_workspace_service as initial_workspace
    import scripts.core.services.initial_translation_file_service as initial_file
    import scripts.core.services.initial_translation_postprocess_service as initial_postprocess
    import scripts.workflows.initial_translate as initial_translate
    from scripts.shared.services import project_manager

    monkeypatch.setattr(archive_module, "MODS_CACHE_DB_PATH", str(tmp_path / "archive.sqlite"))
    manager = ArchiveManager()
    manager.initialize_database()
    destination = tmp_path / "outputs"
    for module in (update_translate, incremental_package, initial_workspace, initial_file,
                   initial_postprocess, initial_translate):
        if hasattr(module, "DEST_DIR"):
            monkeypatch.setattr(module, "DEST_DIR", str(destination))
    monkeypatch.setattr(update_translate, "IncrementalArchiveService",
                        lambda: IncrementalArchiveService(am=manager))
    project = {"project_id": "multi-integration", "name": "Multi Integration",
               "game_id": "", "source_language": "en", "source_path": ""}
    monkeypatch.setattr(project_manager, "get_project", AsyncMock(side_effect=lambda _id: dict(project)))
    for name in ("add_translation_path", "refresh_project_files", "update_file_status_with_kanban_sync",
                 "log_history_event"):
        if hasattr(project_manager, name):
            monkeypatch.setattr(project_manager, name, AsyncMock())
    yield manager, destination, project
    manager.close()


class MultiLanguageMockProvider:
    provider_name = "offline-multilang"
    client = object()

    def __init__(self):
        self.languages = []

    def translate_batch(self, batch):
        language = batch.file_task.target_lang["code"]
        self.languages.append(language)
        prefix = "fr:" if language == "fr" else "zh:"
        batch.translated_texts = [prefix + text for text in batch.texts]
        return batch


@pytest.mark.parametrize("game", ["project_zomboid", "rimworld"])
@pytest.mark.parametrize("workflow", ["initial", "incremental"])
@pytest.mark.asyncio
async def test_multilang_keeps_each_game_package_and_archive_language_isolated(
    tmp_path, monkeypatch, integration, game, workflow
):
    from scripts import app_settings
    from scripts.core.archive_manager import archive_manager
    from scripts.core.services import initial_translation_workspace_service as workspace
    from scripts.core.services import initial_translation_file_service as file_service
    from scripts.core.services import initial_translation_postprocess_service as postprocess
    from scripts.workflows import initial_translate

    manager, destination, project = integration
    root = tmp_path / f"source-{game}-{workflow}"
    source_file, initial_values, expected_resources = _fixture(root, game)
    project.update(game_id=game, source_path=str(root))
    source_language = next(item for item in app_settings.LANGUAGES.values() if item["code"] == "en")
    targets = [next(item for item in app_settings.LANGUAGES.values() if item["code"] == code)
               for code in ("fr", "zh-CN")]
    profile = app_settings.GAME_PROFILES_BY_ID[game]
    profile = {**profile, "game_version": "42.15.0" if game == "project_zomboid" else "1.6"}
    provider = MultiLanguageMockProvider()

    if workflow == "initial":
        connection = manager.connection
        from scripts.core.archive_manager import archive_manager as global_archive
        monkeypatch.setattr(global_archive, "_conn", connection)
        monkeypatch.setattr(initial_translate, "create_translation_handler", lambda *args: provider)
        outcome = await asyncio.to_thread(
            initial_translate.run,
            "Multi Integration", source_language, targets, profile, "",
            selected_provider="offline-multilang", model_name="fixture", project_id=project["project_id"],
            use_glossary=False, override_path=str(root), translation_context_mode="none",
            concurrency_limit=1, rpm_limit=None, embedded_workshop={"enabled": False},
            reference_reuse={"enabled": False},
        )
        assert outcome.status == "completed"
        output_root = destination
    else:
        import scripts.core.services.incremental_translation_service as incremental_translation
        monkeypatch.setattr(incremental_translation, "handler_for_selection",
                            lambda *args, **kwargs: provider)
        monkeypatch.setattr(update_translate, "handler_for_selection",
                            lambda *args, **kwargs: provider)
        source_snapshot = IncrementalSnapshotService().build_snapshot(
            str(root), source_language, game_profile=profile
        )
        _seed_archive(manager, project["project_id"], project["name"], source_snapshot, initial_values)
        if game == "project_zomboid":
            _write(source_file, '{"Greeting":"Hello again %1","Added":"Fresh %1"}')
        else:
            _write(source_file, "<LanguageData><Greeting>Hello again {0}</Greeting><Added>Fresh {0}</Added></LanguageData>")
        result = await update_translate.run_incremental_update(
            project_id=project["project_id"], target_lang_infos=targets,
            source_lang_info=source_language, game_profile=profile,
            selected_provider="offline-multilang", model_name="fixture", concurrency_limit=1,
            dry_run=False, use_resume=False, embedded_workshop={"enabled": False},
            reference_reuse={"enabled": False}, translation_context_mode="none",
        )
        assert result["status"] == "success"
        output_root = Path(result["output_dirs"][0])

    assert set(provider.languages) == {"fr", "zh-CN"}
    expected_target_keys = {"fr": "fr:", "zh-CN": "zh:"}
    expected_count = expected_resources
    package_ids = _package_ids(output_root, game, ["fr", "zh-CN"])
    assert package_ids["fr"] and package_ids["zh-CN"]
    assert package_ids["fr"] != package_ids["zh-CN"]
    suffixes = {"fr": "fr" if game == "project_zomboid" else "French",
                "zh-CN": "ch" if game == "project_zomboid" else "ChineseSimplified"}
    assert all(package_ids[code].casefold().endswith(suffix.casefold())
               for code, suffix in suffixes.items())
    observed_by_language = {}
    for language, prefix in expected_target_keys.items():
        files = output_files(output_root, language)
        assert len(files) == expected_count
        records = [output_record(path)[1] for path in files]
        assert all(record["language"] == language for record in records)
        assert all(record["entries"] for record in records)
        observed = _language_values(output_root, [language], game)[language]
        assert observed and all(value.startswith(prefix) for value in observed.values())
        observed_by_language[language] = observed
    assert observed_by_language["fr"] != observed_by_language["zh-CN"]

    for language, prefix in expected_target_keys.items():
        archive_entries = manager.get_entries(
            project_id=project["project_id"] if workflow == "incremental" else None,
            mod_name=project["name"] if workflow == "initial" else None,
            language=language,
        )
        archived = {entry["key"]: entry["translation"] for entry in archive_entries}
        if workflow == "initial":
            assert len(archived) == expected_resources
            assert all(value.startswith(prefix) for value in archived.values())
        else:
            changed_key = "UI::Greeting" if game == "project_zomboid" else "Greeting"
            added_key = "UI::Added" if game == "project_zomboid" else "Added"
            assert archived[changed_key] == initial_values[changed_key].replace("fr:", prefix)
            assert archived[added_key].startswith(prefix)
