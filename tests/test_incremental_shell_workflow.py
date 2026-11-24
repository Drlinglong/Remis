import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
from scripts.core.services import incremental_package_service
from scripts.core.services.incremental_archive_service import IncrementalArchiveService
from scripts.core.services.incremental_translation_service import IncrementalTranslationService
from scripts.workflows import update_translate

SOURCE = "localization/english/ut_l_english.yml"
SHELL = {"name": "Italian", "code": "custom", "key": "l_english", "folder_prefix": "it-"}


@pytest.mark.asyncio
async def test_shell_only_translates_delta_and_keeps_an_english_package(tmp_path, monkeypatch):
    source = tmp_path / "source"
    path = source / SOURCE
    path.parent.mkdir(parents=True)
    path.write_text('l_english:\n keep:0 "Retain this text"\n new:0 "Add [concept_new] text"\n', encoding="utf-8-sig")
    metadata = source / ".metadata/metadata.json"
    metadata.parent.mkdir()
    metadata.write_text(json.dumps({"id": "original", "supported_game_version": "1.15.*"}), encoding="utf-8")
    output_root = tmp_path / "output"
    monkeypatch.setattr(incremental_package_service, "DEST_DIR", str(output_root))
    monkeypatch.setattr(update_translate, "DEST_DIR", str(output_root))
    monkeypatch.setattr(update_translate.project_manager, "get_project", AsyncMock(
        return_value={"name": "Utopia Italian", "source_path": str(source)},
    ))
    monkeypatch.setattr(update_translate.project_manager, "add_translation_path", AsyncMock())
    monkeypatch.setattr(update_translate.project_manager, "log_history_event", AsyncMock())
    archived = [{"file_path": SOURCE, "key": "keep:0", "original": "Retain this text", "translation": "Conserva"}]
    monkeypatch.setattr(IncrementalArchiveService, "get_language_entries", lambda self, **kwargs: archived)
    monkeypatch.setattr(IncrementalArchiveService, "get_language_baseline", lambda self, **kwargs: None)
    persist = Mock(return_value=7)
    monkeypatch.setattr(IncrementalArchiveService, "archive_language_result", persist)

    def translate(self, file_tasks_for_ai, target_lang_code, **kwargs):
        assert target_lang_code == "custom"
        assert len(file_tasks_for_ai) == 1
        assert file_tasks_for_ai[0].target_lang == SHELL
        assert file_tasks_for_ai[0].texts_to_translate == ["Add [concept_new] text"]
        return {"ut_l_english.yml": ["Aggiungi il testo [concept_new]"]}, []

    monkeypatch.setattr(IncrementalTranslationService, "translate_dirty_files", translate)
    handler = Mock(side_effect=AssertionError("Shell metadata must not invoke a provider"))
    monkeypatch.setattr(update_translate, "handler_for_selection", handler)
    args = {
        "project_id": "project", "target_lang_infos": [SHELL],
        "source_lang_info": LANGUAGE_BY_CODE["en"], "game_profile": GAME_PROFILES_BY_ID["victoria3"],
        "translation_context_mode": "none", "use_resume": False,
    }
    first = await update_translate.run_incremental_update(**args)
    second = await update_translate.run_incremental_update(**args)
    assert first["status"] == second["status"] == "success"
    root = Path(first["output_dirs"][0])
    other_root = Path(second["output_dirs"][0])
    assert root != other_root
    assert root.name.startswith("it-")
    translated = (root / SOURCE).read_bytes()
    assert translated.startswith(b"\xef\xbb\xbf")
    assert translated.decode("utf-8-sig").splitlines() == [
        "l_english:", ' keep:0 "Conserva"', ' new:0 "Aggiungi il testo [concept_new]"',
    ]
    output_metadata = json.loads((root / ".metadata/metadata.json").read_text(encoding="utf-8"))
    other_metadata = json.loads((other_root / ".metadata/metadata.json").read_text(encoding="utf-8"))
    assert len({output_metadata["id"], other_metadata["id"], "original"}) == 3
    assert output_metadata["supported_game_version"] == other_metadata["supported_game_version"] == "1.15.*"
    assert (other_root / SOURCE).read_bytes() == translated
    assert persist.call_args.kwargs["target_lang_code"] == "custom"
    assert persist.call_args.kwargs["archive_results"] == {SOURCE: ["Conserva", "Aggiungi il testo [concept_new]"]}
    handler.assert_not_called()
    failure = Mock(side_effect=RuntimeError("Injected translation failure"))
    monkeypatch.setattr(IncrementalTranslationService, "translate_dirty_files", failure)
    failed = await update_translate.run_incremental_update(**args)
    assert failed["status"] == "error"
    failure.assert_called_once()
    assert persist.call_count == 2
    for folder in (root, other_root):
        assert (folder / SOURCE).read_bytes() == translated
        assert (folder / ".metadata/metadata.json").is_file()


@pytest.mark.parametrize("invalid_metadata", ["[]", "{"])
def test_invalid_shell_metadata_fails_before_allocating_output(tmp_path, monkeypatch, invalid_metadata):
    source = tmp_path / "source"
    metadata = source / ".metadata/metadata.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(invalid_metadata, encoding="utf-8")
    output_root = tmp_path / "output"
    monkeypatch.setattr(incremental_package_service, "DEST_DIR", str(output_root))

    with pytest.raises(ValueError):
        incremental_package_service.IncrementalPackageService().prepare_output_package(
            "Fixture", str(source), SHELL, GAME_PROFILES_BY_ID["victoria3"],
        )
    assert not output_root.exists()
