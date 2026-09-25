"""Real workflow integration with deterministic model output and temporary storage."""
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.core.game_adapters.registry import get_adapter
from scripts.core.game_adapters.workflow_bridge import safe_output


def _write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture(root, game_id):
    if game_id == "project_zomboid":
        _write(root, "mod.info", "id=synthetic.workflow\nname=Workflow Fixture\n")
        _write(root, "media/lua/shared/Translate/EN/UI.json", '{"UI_Title":"Open %1"}')
    else:
        _write(root, "About/About.xml", '<ModMetaData><packageId>synthetic.workflow</packageId><supportedVersions><li>1.6</li></supportedVersions></ModMetaData>')
        _write(root, "Languages/English/Keyed/UI.xml", '<LanguageData><Title>Open {0}</Title></LanguageData>')
        _write(root, "Defs/ThingDefs/Item.xml", '<Defs><ThingDef><defName>Crystal</defName><label>crystal</label><description>A crystal.</description></ThingDef></Defs>')
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
def test_full_initial_workflow_uses_real_archive_writer_and_validation(tmp_path, monkeypatch, game_id):
    from scripts import app_settings
    from scripts.core.archive_manager import archive_manager
    from scripts.core.services import initial_translation_workspace_service as workspace
    from scripts.core.services import initial_translation_file_service as file_service
    from scripts.core.services import initial_translation_postprocess_service as postprocess
    from scripts.core.game_adapters.output_records import output_files
    from scripts.core.loc_parser import parse_loc_file
    from scripts.workflows import initial_translate

    root = tmp_path / "source"
    hashes = _fixture(root, game_id)
    destination = tmp_path / "output"
    for module in (app_settings, workspace, file_service, postprocess, initial_translate):
        monkeypatch.setattr(module, "DEST_DIR", str(destination))
    connection = sqlite3.connect(tmp_path / "archive.sqlite", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    archive_manager._create_tables(connection)
    monkeypatch.setattr(archive_manager, "_conn", connection)

    class MockProvider:
        provider_name = "mock"
        client = object()

        def translate_batch(self, batch):
            batch.translated_texts = ["译文 " + text for text in batch.texts]
            return batch

    monkeypatch.setattr(initial_translate, "create_translation_handler", lambda *args: MockProvider())
    source = next(l for l in app_settings.LANGUAGES.values() if l["code"] == "en")
    target = next(l for l in app_settings.LANGUAGES.values() if l["code"] == "zh-CN")
    outcome = initial_translate.run(
        "Fixture", source, [target], app_settings.GAME_PROFILES_BY_ID[game_id], "",
        selected_provider="mock", model_name="deterministic-test", use_glossary=False,
        override_path=str(root), translation_context_mode="none", concurrency_limit=1,
        rpm_limit=None, embedded_workshop={"enabled": False}, reference_reuse={"enabled": False},
    )
    assert outcome.status == "completed"
    outputs = output_files(destination, "zh-CN")
    assert outputs
    if game_id == "rimworld":
        assert len(outputs) == 2
        assert all("/Languages/ChineseSimplified/" in Path(path).as_posix() for path in outputs)
        assert sum(len(parse_loc_file(Path(path))) for path in outputs) == 3
    else:
        assert all("/Translate/CH/" in Path(path).as_posix() for path in outputs)
    for path in outputs:
        entries = parse_loc_file(Path(path))
        assert entries and all(value.startswith("译文 ") for _, value in entries)
    assert connection.execute("SELECT COUNT(*) FROM translated_entries").fetchone()[0] >= 1
    for name, digest in hashes.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert not list(destination.rglob("*.dll"))
    connection.close()


def test_legacy_paradox_contract_preserves_tokens_comments_and_target_layout(tmp_path):
    root = tmp_path / "paradox"
    path = _write(root, "localization/english/fixture_l_english.yml", '\ufeffl_english:\n # comment\n greeting:0 "Hello $COUNTRY$"\n')
    profile = {"id": "victoria3", "source_localization_folder": "localization"}
    adapter = get_adapter(profile)
    resource = adapter.discover(root, {"key": "l_english", "code": "en"}).resources[0]
    document = adapter.parse(path, resource.metadata)
    output = adapter.render(document, {"greeting:0": "你好 $COUNTRY$"}, {"key": "l_simp_chinese"})
    content = output["localization/simp_chinese/fixture_l_simp_chinese.yml"]
    assert '# comment' in content and '$COUNTRY$' in content and '你好' in content
    assert 'l_simp_chinese:' in content
    assert content.startswith('\ufeffl_simp_chinese:') and 'l_english:' not in content


def test_legacy_csv_obeys_same_adapter_contract(tmp_path):
    root = tmp_path / "mars"
    path = _write(root, "Game.csv", "ID,Text,Translation,VoiceActor,Context\n001,Hello,,actor,context\n")
    adapter = get_adapter({"id": "surviving_mars", "format_adapter_id": "surviving_mars_csv", "source_localization_folder": "."})
    found = adapter.discover(root, {"key": "l_english"})
    document = adapter.parse(path, found.resources[0].metadata)
    result = adapter.render(document, {"001": "你好"}, {"key": "l_simp_chinese"})
    assert "001,Hello,你好,actor,context" in result["Game.csv"]
    assert adapter.package_metadata(root, {}) == {}


@pytest.mark.parametrize("relative", ["../outside.txt", "C:/outside.txt", "/absolute.txt", "folder/../../escape"])
def test_output_containment_blocks_adapter_paths(tmp_path, relative):
    with pytest.raises(ValueError):
        safe_output(tmp_path, relative)


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
def test_resource_run_output_identity_preserves_resume_and_separates_new_runs(game_id):
    from scripts.core.services.initial_translation_run_service import resource_output_folder

    profile = {"id": game_id}
    original = resource_output_folder("CN-Fixture", profile, "original-run")
    assert original == resource_output_folder("CN-Fixture", profile, "original-run")
    assert original != resource_output_folder("CN-Fixture", profile, "next-run")
    assert resource_output_folder("CN-Fixture", {"id": "victoria3"}, "next-run") == "CN-Fixture"
