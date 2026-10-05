"""Mars CSV increments must write real rows before they may advance the archive."""
import csv
from pathlib import Path

import pytest

from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
from scripts.core.services.incremental_build_service import IncrementalBuildService
from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.surviving_mars_csv import parse_file


def _prepare(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with (source / "ModTexts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows([("ID", "Text", "Translation", "VoiceActor", "Context"),
                          ("10", "Kept\nwith newline\n", "", "", ""),
                          ("20", "Changed\n", "", "", ""),
                          ("30", "New", "", "", "")])
    profile = GAME_PROFILES_BY_ID["surviving_mars"]
    english, chinese = LANGUAGE_BY_CODE["en"], LANGUAGE_BY_CODE["zh-CN"]
    snapshot = IncrementalSnapshotService().build_snapshot(str(source), english, game_profile=profile)
    diff = IncrementalDiffService()
    history = diff.build_history_index([
        {"file_path": "ModTexts.csv", "key": "10", "original": "Kept\nwith newline\n", "translation": "复用\n换行\n"},
        {"file_path": "ModTexts.csv", "key": "20", "original": "Old", "translation": "旧"},
    ])
    prepared = IncrementalPreparationService().prepare_language_update(
        current_files_data=snapshot, history_index=history, diff_service=diff,
        target_lang_info=chinese, source_lang_info=english, game_profile=profile,
        mod_context="", selected_provider="fixture", source_path=str(source),
        base_output_dir=tmp_path / "output", total_targets=1,
    )
    return dict(processing_records=prepared["processing_records"], source_path=str(source),
                lang_output_dir=prepared["lang_output_dir"], source_lang_info=english,
                target_lang_info=chinese, game_profile=profile)


def test_multiline_csv_increment_reuses_and_writes_all_rows(tmp_path):
    kwargs = _prepare(tmp_path)
    result = IncrementalBuildService().build_language_output(
        **kwargs, translated_results={"ModTexts.csv": ["已修改\n", "新增"]})
    assert len(result["written_files"]) == 1
    document = parse_file(Path(result["written_files"][0]))
    assert [row[0] for row in document.rows[1:]] == ["10", "20", "30"]
    assert [row[2] for row in document.rows[1:]] == ["复用\n换行\n", "已修改\n", "新增"]
    assert result["archive_files_data"][0]["texts_to_translate"][0] == "Kept\nwith newline\n"


def test_mars_write_failure_and_missing_model_result_are_not_success(tmp_path, monkeypatch):
    kwargs = _prepare(tmp_path)
    with pytest.raises(ValueError, match="Incomplete"):
        IncrementalBuildService().build_language_output(**kwargs, translated_results={})

    def fail_write(**_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("scripts.core.services.incremental_build_service.rebuild_and_write_file", fail_write)
    with pytest.raises(OSError, match="disk unavailable"):
        IncrementalBuildService().build_language_output(
            **kwargs, translated_results={"ModTexts.csv": ["已修改\n", "新增"]})
