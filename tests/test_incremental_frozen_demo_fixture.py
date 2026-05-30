from pathlib import Path

from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService


def test_remis_vic3_frozen_incremental_fixture_has_expected_delta(tmp_path):
    root = Path(__file__).resolve().parents[1]
    base = root / "source_mod" / "Test_Project_Remis_Vic3"
    update = root / "source_mod" / "Test_Project_Remis_Vic3_Incremental_Frozen"
    lang = {"code": "zh-CN", "key": "l_simp_chinese", "name_en": "Simplified Chinese"}

    snapshot_service = IncrementalSnapshotService()
    diff_service = IncrementalDiffService()
    preparation_service = IncrementalPreparationService()

    base_files = snapshot_service.build_snapshot(str(base), lang)
    update_files = snapshot_service.build_snapshot(str(update), lang)

    history_records = []
    for file_data in base_files:
        for key, original, _line_number in file_data["parsed_entries"]:
            history_records.append(
                {
                    "file_path": file_data["file_path"],
                    "key": key,
                    "original": original,
                    "translation": f"archived::{key}",
                }
            )

    history_index = diff_service.build_history_index(history_records)
    result = preparation_service.prepare_language_update(
        current_files_data=update_files,
        history_index=history_index,
        diff_service=diff_service,
        target_lang_info=lang,
        source_lang_info=lang,
        game_profile={"id": "victoria3"},
        mod_context="",
        selected_provider="gemini",
        source_path=str(update),
        base_output_dir=tmp_path,
        total_targets=1,
    )

    base_keys = {key for file_data in base_files for key, _text, _line in file_data["parsed_entries"]}
    update_keys = {key for file_data in update_files for key, _text, _line in file_data["parsed_entries"]}

    assert result["summary"] == {"total": 35, "new": 6, "changed": 2, "unchanged": 27}
    assert base_keys - update_keys == {"remis_event.3.b:0"}
    assert update_keys - base_keys == {
        "remis_event.7.b:0",
        "remis_journal.remis_restoration:0",
        "remis_news.1.a:0",
        "remis_news.1.d:0",
        "remis_news.1.f:0",
        "remis_news.1.t:0",
    }

    tasks_by_file = {task.filename: task.texts_to_translate for task in result["file_tasks_for_ai"]}
    assert len(tasks_by_file["remis_demo_l_simp_chinese.yml"]) == 4
    assert len(tasks_by_file["remis_newspaper_l_simp_chinese.yml"]) == 4
