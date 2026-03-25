from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.core.project_manager import ProjectManager
from scripts.core.services.incremental_build_service import IncrementalBuildService
from scripts.core.services.incremental_diff_service import IncrementalDiffService
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.archive_manager import ArchiveManager


def _write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


@pytest.fixture
def temp_archive_db(tmp_path):
    db_path = tmp_path / "mods_cache_test.sqlite"
    import scripts.core.archive_manager as am_module

    original_path = am_module.MODS_CACHE_DB_PATH
    am_module.MODS_CACHE_DB_PATH = str(db_path)

    manager = ArchiveManager()
    manager.initialize_database()

    yield manager

    manager.close()
    am_module.MODS_CACHE_DB_PATH = original_path


def test_preparation_summary_counts_changed_entries(tmp_path):
    source_root = tmp_path / "source_mod" / "TestMod"
    source_file = source_root / "localization" / "english" / "sample_l_english.yml"
    _write_text(
        source_file,
        'l_english:\n key.one:0 "Alpha changed"\n key.two:0 "Beta"\n',
    )

    snapshot_service = IncrementalSnapshotService()
    current_files_data = snapshot_service.build_snapshot(
        str(source_root),
        {"name_en": "English", "key": "l_english", "code": "en"},
    )

    diff_service = IncrementalDiffService()
    history_index = diff_service.build_history_index(
        [
            {
                "file_path": "localization/english/sample_l_english.yml",
                "key": "key.one:0",
                "original": "Alpha old",
                "translation": "旧阿尔法",
            },
            {
                "file_path": "localization/english/sample_l_english.yml",
                "key": "key.two:0",
                "original": "Beta",
                "translation": "旧贝塔",
            },
        ]
    )

    preparation_service = IncrementalPreparationService()
    result = preparation_service.prepare_language_update(
        current_files_data=current_files_data,
        history_index=history_index,
        diff_service=diff_service,
        target_lang_info={"code": "zh-CN", "key": "l_simp_chinese"},
        source_lang_info={"code": "en", "key": "l_english"},
        game_profile={"id": "victoria3"},
        mod_context="",
        selected_provider="gemini",
        source_path=str(source_root),
        base_output_dir=tmp_path / "out",
        total_targets=1,
    )

    assert result["summary"] == {"total": 2, "new": 0, "changed": 1, "unchanged": 1}
    assert len(result["processing_records"]) == 1
    assert len(result["file_tasks_for_ai"]) == 1
    assert result["file_tasks_for_ai"][0].texts_to_translate == ["Alpha changed"]


def test_build_output_reuses_old_translation_and_applies_ai_result(tmp_path):
    source_root = tmp_path / "source_mod" / "TestMod"
    source_file = source_root / "localization" / "english" / "sample_l_english.yml"
    _write_text(
        source_file,
        'l_english:\n key.one:0 "Alpha changed"\n key.two:0 "Beta"\n',
    )

    snapshot_service = IncrementalSnapshotService()
    current_files_data = snapshot_service.build_snapshot(
        str(source_root),
        {"name_en": "English", "key": "l_english", "code": "en"},
    )
    file_data = current_files_data[0]

    processing_records = [
        {
            "fd": file_data,
            "full_file_entries": [
                {
                    "key": "key.one:0",
                    "source": "Alpha changed",
                    "line_num": 1,
                    "translation": None,
                    "is_dirty": True,
                },
                {
                    "key": "key.two:0",
                    "source": "Beta",
                    "line_num": 2,
                    "translation": "旧贝塔",
                    "is_dirty": False,
                },
            ],
            "key_delta_indices": [0],
        }
    ]

    build_service = IncrementalBuildService()
    result = build_service.build_language_output(
        processing_records=processing_records,
        translated_results={"sample_l_english.yml": ["新阿尔法"]},
        source_path=str(source_root),
        lang_output_dir=tmp_path / "Remis_Incremental_Update",
        source_lang_info={"code": "en", "key": "l_english"},
        target_lang_info={"code": "zh-CN", "key": "l_simp_chinese"},
        game_profile={"id": "victoria3"},
    )

    assert len(result["written_files"]) == 1
    output_path = Path(result["written_files"][0])
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8-sig")
    assert "l_simp_chinese:" in content
    assert 'key.one:0 "新阿尔法"' in content
    assert 'key.two:0 "旧贝塔"' in content
    assert result["archive_results"]["localization/english/sample_l_english.yml"] == ["新阿尔法", "旧贝塔"]


@pytest.mark.asyncio
async def test_check_archive_returns_only_archived_languages(tmp_path):
    repo = MagicMock()
    test_project = {
        "project_id": "test-p1",
        "name": "TestMod",
        "game_id": "victoria3",
        "source_language": "en",
    }
    mock_project = MagicMock()
    mock_project.model_dump.return_value = test_project
    repo.get_project = AsyncMock(return_value=mock_project)

    import scripts.core.archive_manager as am_module
    original_db_path = am_module.MODS_CACHE_DB_PATH
    am_module.MODS_CACHE_DB_PATH = str(tmp_path / "cache.sqlite")

    archive_manager = ArchiveManager()
    archive_manager.initialize_database()
    try:
        mod_id = archive_manager.get_or_create_mod_entry("TestMod", "test-p1")
        version_id = archive_manager.create_source_version(
            mod_id,
            [
                {
                    "filename": "sample_l_english.yml",
                    "file_path": "localization/english/sample_l_english.yml",
                    "texts_to_translate": ["Alpha"],
                    "key_map": {0: {"key_part": "key.one"}},
                }
            ],
        )
        archive_manager.archive_translated_results(
            version_id,
            {"localization/english/sample_l_english.yml": ["阿尔法"]},
            [
                {
                    "filename": "sample_l_english.yml",
                    "file_path": "localization/english/sample_l_english.yml",
                    "texts_to_translate": ["Alpha"],
                    "key_map": {0: {"key_part": "key.one"}},
                }
            ],
            "zh-CN",
        )

        service = MagicMock()
        service.archive_manager = archive_manager
        pm = ProjectManager(project_repository=repo, archive_service=service)

        result = await pm.check_project_archive("test-p1")

        assert result["exists"] is True
        assert result["target_languages"] == ["zh-CN"]
        assert result["archived_languages"] == ["zh-CN"]
    finally:
        archive_manager.close()
        am_module.MODS_CACHE_DB_PATH = original_db_path
