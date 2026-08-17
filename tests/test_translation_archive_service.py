import json
import sqlite3
from pathlib import Path

import pytest

from scripts.core.archive_manager import ArchiveManager
from scripts.core.services.translation_archive_service import TranslationArchiveService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService


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


def _write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def _write_project_config(source_root: Path, translation_dirs=None):
    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": translation_dirs or []}}),
        encoding="utf-8",
    )


def test_upload_rejects_mixed_invalid_source_before_archive_write(
    temp_archive_db,
    tmp_path,
):
    source_root = tmp_path / "source_mod" / "BrokenMod"
    valid = source_root / "localization" / "english" / "valid_l_english.yml"
    broken = source_root / "localization" / "english" / "broken_l_english.yml"
    _write_text(valid, 'l_english:\n valid.key:0 "Valid"\n')
    _write_text(broken, 'l_english:\n broken.key:0 "unterminated\n')
    _write_project_config(source_root)

    result = TranslationArchiveService(am=temp_archive_db).upload_project_translations(
        project_id="broken-project",
        project_name="BrokenMod",
        source_path=str(source_root),
        source_lang_code="en",
    )

    assert result["status"] == "error"
    assert result["code"] == "source_scan_failed"
    assert result["scanned_file_count"] == 2
    assert result["issue_count"] == 1
    assert result["issues"][0]["file_path"] == (
        "localization/english/broken_l_english.yml"
    )
    assert result["issues"][0]["code"] == "unterminated_value"
    assert temp_archive_db.connection.execute(
        "SELECT COUNT(*) FROM mods"
    ).fetchone()[0] == 0
    assert temp_archive_db.connection.execute(
        "SELECT COUNT(*) FROM source_versions"
    ).fetchone()[0] == 0


def test_upload_rejects_unreadable_source_before_archive_write(
    temp_archive_db,
    tmp_path,
    monkeypatch,
):
    source_root = tmp_path / "source_mod" / "UnreadableMod"
    source = source_root / "localization" / "english" / "source_l_english.yml"
    _write_text(source, 'l_english:\n source.key:0 "Valid"\n')
    _write_project_config(source_root)

    def fail_parse(_path):
        raise OSError("injected unreadable source")

    monkeypatch.setattr(
        "scripts.core.services.translation_archive_service.parse_loc_file_report",
        fail_parse,
    )
    result = TranslationArchiveService(am=temp_archive_db).upload_project_translations(
        project_id="unreadable-project",
        project_name="UnreadableMod",
        source_path=str(source_root),
        source_lang_code="en",
    )

    assert result["code"] == "source_scan_failed"
    assert result["issues"] == [{
        "file_path": "localization/english/source_l_english.yml",
        "code": "source_read_error",
        "message": "Source file could not be read or parsed.",
        "line_number": None,
        "key": None,
        "error_type": "OSError",
    }]
    assert temp_archive_db.connection.execute(
        "SELECT COUNT(*) FROM source_versions"
    ).fetchone()[0] == 0


def test_upload_rejects_source_directory_scan_error_before_archive_write(
    temp_archive_db,
    tmp_path,
    monkeypatch,
):
    source_root = tmp_path / "source_mod" / "UnavailableMod"
    source_root.mkdir(parents=True)
    _write_project_config(source_root)

    def fail_walk(path, onerror=None):
        error = PermissionError("injected directory denial")
        error.filename = str(path)
        onerror(error)
        return iter(())

    monkeypatch.setattr(
        "scripts.core.services.translation_archive_service.os.walk",
        fail_walk,
    )
    result = TranslationArchiveService(am=temp_archive_db).upload_project_translations(
        project_id="unavailable-project",
        project_name="UnavailableMod",
        source_path=str(source_root),
        source_lang_code="en",
    )

    assert result["code"] == "source_scan_failed"
    assert result["issues"][0]["code"] == "source_directory_scan_error"
    assert result["issues"][0]["error_type"] == "PermissionError"
    assert temp_archive_db.connection.execute(
        "SELECT COUNT(*) FROM source_versions"
    ).fetchone()[0] == 0


def test_archive_records_recovered_source_value_and_translation_as_empty(temp_archive_db):
    file_path = "localisation/english/broken_l_english.yml"
    files = [{
        "filename": "broken_l_english.yml",
        "file_path": file_path,
        "texts_to_translate": ["Translate me"],
        "key_map": {0: {"key_part": "valid:0"}},
        "archive_texts": ["Translate me", ""],
        "archive_key_map": {
            0: {"key_part": "valid:0"},
            1: {"key_part": "broken:0"},
        },
        "recovered_entries": [
            {"key_part": "broken:0", "code": "unterminated_value"}
        ],
    }]
    mod_id = temp_archive_db.get_or_create_mod_entry("BrokenMod", "local-BrokenMod")
    version_id = temp_archive_db.create_source_version(mod_id, files)

    temp_archive_db.archive_translated_results(
        version_id,
        {file_path: ["Translated", ""]},
        files,
        "zh-CN",
    )

    rows = temp_archive_db.connection.execute(
        """
        SELECT se.entry_key, se.source_text, te.translated_text
        FROM source_entries se
        LEFT JOIN translated_entries te ON te.source_entry_id = se.source_entry_id
        WHERE se.version_id = ?
        ORDER BY se.entry_key
        """,
        (version_id,),
    ).fetchall()
    values = {
        row["entry_key"]: (row["source_text"], row["translated_text"])
        for row in rows
    }
    assert values == {
        "broken:0": ("", ""),
        "valid:0": ("Translate me", "Translated"),
    }


def test_upload_project_translations_uses_relative_paths(temp_archive_db, tmp_path):
    source_root = tmp_path / "source_mod" / "TestMod"
    translation_root = tmp_path / "my_translation" / "zh-CN-TestMod"

    source_file_a = source_root / "module_a" / "localization" / "english" / "shared_l_english.yml"
    source_file_b = source_root / "module_b" / "localization" / "english" / "shared_l_english.yml"
    trans_file_a = translation_root / "module_a" / "localization" / "simp_chinese" / "shared_l_simp_chinese.yml"
    trans_file_b = translation_root / "module_b" / "localization" / "simp_chinese" / "shared_l_simp_chinese.yml"

    _write_text(source_file_a, 'l_english:\n key.a:0 "Alpha"\n')
    _write_text(source_file_b, 'l_english:\n key.b:0 "Beta"\n')
    _write_text(trans_file_a, 'l_simp_chinese:\n key.a:0 "阿尔法"\n')
    _write_text(trans_file_b, 'l_simp_chinese:\n key.b:0 "贝塔"\n')

    project_json = source_root / ".remis_project.json"
    project_json.write_text(
        json.dumps(
            {
                "version": "1.0",
                "config": {
                    "translation_dirs": [str(translation_root)]
                },
                "kanban": {
                    "columns": ["todo", "in_progress", "proofreading", "paused", "done"],
                    "tasks": {},
                    "column_order": ["todo", "in_progress", "proofreading", "paused", "done"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    service = TranslationArchiveService(am=temp_archive_db)
    result = service.upload_project_translations(
        project_id="project-1",
        project_name="TestMod",
        source_path=str(source_root),
        source_lang_code="en",
    )

    assert result["status"] == "success"
    assert result["match_count"] == 2

    entries_a = temp_archive_db.get_entries(
        project_id="project-1",
        file_path="module_a/localization/english/shared_l_english.yml",
        language="zh-CN",
    )
    entries_b = temp_archive_db.get_entries(
        project_id="project-1",
        file_path="module_b/localization/english/shared_l_english.yml",
        language="zh-CN",
    )

    assert entries_a[0]["translation"] == "阿尔法"
    assert entries_b[0]["translation"] == "贝塔"


def test_archive_manager_migrates_legacy_unique_constraints(tmp_path):
    db_path = tmp_path / "legacy_mods_cache.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE mods (mod_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE mod_identities (identity_id INTEGER PRIMARY KEY AUTOINCREMENT, mod_id INTEGER NOT NULL, remote_file_id TEXT NOT NULL UNIQUE, FOREIGN KEY (mod_id) REFERENCES mods (mod_id))")
    cur.execute("CREATE TABLE source_versions (version_id INTEGER PRIMARY KEY AUTOINCREMENT, mod_id INTEGER NOT NULL, snapshot_hash TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (mod_id) REFERENCES mods (mod_id))")
    cur.execute("CREATE TABLE source_entries (source_entry_id INTEGER PRIMARY KEY AUTOINCREMENT, version_id INTEGER NOT NULL, entry_key TEXT NOT NULL, source_text TEXT NOT NULL, file_path TEXT DEFAULT '', UNIQUE(version_id, entry_key), FOREIGN KEY (version_id) REFERENCES source_versions (version_id))")
    cur.execute("CREATE TABLE translated_entries (translated_entry_id INTEGER PRIMARY KEY AUTOINCREMENT, source_entry_id INTEGER NOT NULL, language_code TEXT NOT NULL, translated_text TEXT NOT NULL, last_translated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(source_entry_id, language_code), FOREIGN KEY (source_entry_id) REFERENCES source_entries (source_entry_id))")
    cur.execute("INSERT INTO mods (mod_id, name) VALUES (1, 'ModA')")
    cur.execute("INSERT INTO mods (mod_id, name) VALUES (2, 'ModB')")
    cur.execute("INSERT INTO source_versions (version_id, mod_id, snapshot_hash) VALUES (1, 1, 'same-hash')")
    cur.execute("INSERT INTO source_entries (source_entry_id, version_id, entry_key, source_text, file_path) VALUES (1, 1, 'shared.key', 'Alpha', 'module_a/file.yml')")
    cur.execute("INSERT INTO translated_entries (translated_entry_id, source_entry_id, language_code, translated_text) VALUES (1, 1, 'zh-CN', '阿尔法')")
    conn.commit()
    conn.close()

    import scripts.core.archive_manager as am_module

    original_path = am_module.MODS_CACHE_DB_PATH
    am_module.MODS_CACHE_DB_PATH = str(db_path)

    manager = ArchiveManager()
    try:
        assert manager.initialize_database() is True

        second_version_id = manager.create_source_version(
            2,
            [
                {
                    "filename": "shared_l_english.yml",
                    "file_path": "module_b/file.yml",
                    "texts_to_translate": ["Alpha"],
                    "key_map": {0: {"key_part": "shared.key"}},
                }
            ],
        )

        assert second_version_id is not None
        assert second_version_id != 1

        entries = manager.get_entries(
            mod_name="ModA",
            file_path="module_a/file.yml",
            language="zh-CN",
        )
        assert entries[0]["translation"] == "阿尔法"

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='source_versions'")
        assert "UNIQUE(mod_id, snapshot_hash)" in cur.fetchone()[0]
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='source_entries'")
        assert "UNIQUE(version_id, file_path, entry_key)" in cur.fetchone()[0]
        conn.close()
    finally:
        manager.close()
        am_module.MODS_CACHE_DB_PATH = original_path


def test_source_scans_only_project_source_language(tmp_path):
    source_root = tmp_path / "source_mod" / "LangMod"
    english_file = source_root / "localization" / "english" / "test_l_english.yml"
    french_file = source_root / "localization" / "french" / "test_l_french.yml"

    _write_text(english_file, 'l_english:\n key.one:0 "Hello"\n')
    _write_text(french_file, 'l_french:\n key.one:0 "Bonjour"\n')

    archive_service = TranslationArchiveService()
    source_files = archive_service._scan_source_files(
        str(source_root), "english"
    ).files
    assert [entry["file_path"] for entry in source_files] == ["localization/english/test_l_english.yml"]

    snapshot_service = IncrementalSnapshotService()
    snapshot_files = snapshot_service.build_snapshot(
        str(source_root),
        {"name_en": "English"},
    )
    assert [entry["file_path"] for entry in snapshot_files] == ["localization/english/test_l_english.yml"]


def test_get_entries_prefers_latest_version_with_translations(temp_archive_db):
    mod_id = temp_archive_db.get_or_create_mod_entry("ArchiveMod", "archive-mod-project")
    translated_version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_english.yml",
                "file_path": "localization/english/sample_l_english.yml",
                "texts_to_translate": ["Alpha"],
                "key_map": {0: {"key_part": "sample.key"}},
            }
        ],
    )
    temp_archive_db.archive_translated_results(
        translated_version_id,
        {"localization/english/sample_l_english.yml": ["阿尔法"]},
        [
            {
                "filename": "sample_l_english.yml",
                "file_path": "localization/english/sample_l_english.yml",
                "texts_to_translate": ["Alpha"],
                "key_map": {0: {"key_part": "sample.key"}},
            }
        ],
        "zh-CN",
    )

    untranslated_version_id = temp_archive_db.create_source_version(
        mod_id,
        [
            {
                "filename": "sample_l_english.yml",
                "file_path": "localization/english/sample_l_english.yml",
                "texts_to_translate": ["Beta"],
                "key_map": {0: {"key_part": "sample.key"}},
            }
        ],
    )
    assert untranslated_version_id != translated_version_id

    latest = temp_archive_db.get_latest_version(project_id="archive-mod-project")
    assert latest["id"] == translated_version_id

    entries = temp_archive_db.get_entries(project_id="archive-mod-project", language="zh-CN")
    assert entries[0]["original"] == "Alpha"
    assert entries[0]["translation"] == "阿尔法"
