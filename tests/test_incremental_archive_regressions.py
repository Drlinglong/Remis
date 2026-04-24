import pytest

from scripts.core.archive_manager import ArchiveManager
from scripts.core.services.incremental_diff_service import IncrementalDiffService


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


def test_get_entries_prefers_most_recent_translation_baseline(temp_archive_db):
    mod_id = temp_archive_db.get_or_create_mod_entry("ArchiveMod", "archive-mod-project")

    full_version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "localisation/simp_chinese/sample_l_simp_chinese.yml",
                "texts_to_translate": ["Alpha", "Beta"],
                "key_map": {
                    0: {"key_part": "sample.one"},
                    1: {"key_part": "sample.two"},
                },
            }
        ],
    )
    temp_archive_db.archive_translated_results(
        full_version_id,
        {"localisation/simp_chinese/sample_l_simp_chinese.yml": ["A", "B"]},
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "localisation/simp_chinese/sample_l_simp_chinese.yml",
                "texts_to_translate": ["Alpha", "Beta"],
                "key_map": [
                    {"key_part": "sample.one"},
                    {"key_part": "sample.two"},
                ],
            }
        ],
        "en",
    )
    temp_archive_db.connection.execute(
        """
        UPDATE translated_entries
        SET last_translated_at = '2026-03-26 09:47:00'
        WHERE translated_entry_id IN (
            SELECT t.translated_entry_id
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.version_id = ? AND t.language_code = 'en'
        )
        """,
        (full_version_id,),
    )

    sparse_version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "sample_l_simp_chinese.yml",
                "texts_to_translate": ["Gamma"],
                "key_map": {0: {"key_part": "sample.three"}},
            }
        ],
    )
    temp_archive_db.archive_translated_results(
        sparse_version_id,
        {"sample_l_simp_chinese.yml": ["C"]},
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "sample_l_simp_chinese.yml",
                "texts_to_translate": ["Gamma"],
                "key_map": [{"key_part": "sample.three"}],
            }
        ],
        "en",
    )
    temp_archive_db.connection.execute(
        """
        UPDATE translated_entries
        SET last_translated_at = '2026-01-11 22:18:11'
        WHERE translated_entry_id IN (
            SELECT t.translated_entry_id
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.version_id = ? AND t.language_code = 'en'
        )
        """,
        (sparse_version_id,),
    )
    temp_archive_db.connection.commit()

    entries = temp_archive_db.get_entries(project_id="archive-mod-project", language="en")

    assert [entry["key"] for entry in entries] == ["sample.one", "sample.two"]
    assert [entry["translation"] for entry in entries] == ["A", "B"]


def test_diff_service_matches_unique_key_fallbacks():
    service = IncrementalDiffService()
    history_index = service.build_history_index(
        [
            {
                "file_path": "other_file.yml",
                "key": "shared.unique",
                "original": "Beta",
                "translation": "B",
            },
            {
                "file_path": "dup_a.yml",
                "key": "dup.key",
                "original": "One",
                "translation": "1",
            },
            {
                "file_path": "dup_b.yml",
                "key": "dup.key",
                "original": "Two",
                "translation": "2",
            },
        ]
    )

    status, entry = service.classify_entry(
        "localisation/simp_chinese/KR_country_specific/renamed.yml",
        "shared.unique",
        "Beta",
        history_index,
    )
    assert status == "unchanged"
    assert entry["translation"] == "B"

    status, entry = service.classify_entry(
        "localisation/simp_chinese/KR_country_specific/renamed.yml",
        "dup.key",
        "One",
        history_index,
    )
    assert status == "new"
    assert entry is None


def test_archive_manager_normalizes_stored_relative_paths(temp_archive_db):
    mod_id = temp_archive_db.get_or_create_mod_entry("PathMod", "path-mod-project")
    version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": r".\localisation\simp_chinese\KR_country_specific\sample_l_simp_chinese.yml",
                "texts_to_translate": ["Alpha"],
                "key_map": {0: {"key_part": "path.key"}},
            }
        ],
    )

    row = temp_archive_db.connection.execute(
        "SELECT file_path FROM source_entries WHERE version_id = ?",
        (version_id,),
    ).fetchone()
    assert row["file_path"] == "localisation/simp_chinese/KR_country_specific/sample_l_simp_chinese.yml"


def test_get_entries_accepts_non_normalized_file_path_inputs(temp_archive_db):
    mod_id = temp_archive_db.get_or_create_mod_entry("PathLookupMod", "path-lookup-project")
    version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "localisation/simp_chinese/KR_country_specific/sample_l_simp_chinese.yml",
                "texts_to_translate": ["Alpha"],
                "key_map": {0: {"key_part": "lookup.key"}},
            }
        ],
    )
    temp_archive_db.archive_translated_results(
        version_id,
        {"localisation/simp_chinese/KR_country_specific/sample_l_simp_chinese.yml": ["A"]},
        [
            {
                "filename": "sample_l_simp_chinese.yml",
                "file_path": "localisation/simp_chinese/KR_country_specific/sample_l_simp_chinese.yml",
                "texts_to_translate": ["Alpha"],
                "key_map": [{"key_part": "lookup.key"}],
            }
        ],
        "en",
    )

    entries = temp_archive_db.get_entries(
        project_id="path-lookup-project",
        file_path=r".\localisation\simp_chinese\KR_country_specific\sample_l_simp_chinese.yml",
        language="en",
    )

    assert len(entries) == 1
    assert entries[0]["translation"] == "A"
