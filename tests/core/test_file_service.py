import os

from scripts.core.services.file_service import FileService


class FakeArchiveManager:
    def __init__(self):
        self.source_versions = []

    def get_or_create_mod_entry(self, project_name, project_id):
        return 7

    def create_source_version(self, mod_id, source_files_data):
        self.source_versions.append((mod_id, source_files_data))


def _write_loc(path, header, key, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{header}:\n {key}:0 \"{value}\"\n", encoding="utf-8")


def test_scan_dir_filters_source_to_requested_language(tmp_path):
    source_root = tmp_path / "mod"
    _write_loc(source_root / "localization" / "english" / "ut_l_english.yml", "l_english", "ut.key", "Hello")
    _write_loc(
        source_root / "localization" / "english" / "replace" / "overwriting_l_english.yml",
        "l_english",
        "ut.replace",
        "Override",
    )
    _write_loc(source_root / "localization" / "french" / "ut_l_french.yml", "l_french", "ut.key", "Bonjour")
    _write_loc(
        source_root / "localization" / "german" / "replace" / "overwriting_l_german.yml",
        "l_german",
        "ut.replace",
        "Uberschreiben",
    )

    service = FileService(kanban_service=None, archive_manager=None, project_repository=None)

    source_files = service.scan_dir(str(source_root), "source", "english", "project-1", [".yml", ".yaml"])
    source_paths = {os.path.relpath(file["file_path"], source_root).replace("\\", "/") for file in source_files}

    assert source_paths == {
        "localization/english/ut_l_english.yml",
        "localization/english/replace/overwriting_l_english.yml",
    }

    translation_files = service.scan_dir(str(source_root), "translation", "english", "project-1", [".yml", ".yaml"])
    translation_paths = {
        os.path.relpath(file["file_path"], source_root).replace("\\", "/") for file in translation_files
    }

    assert translation_paths == {
        "localization/english/ut_l_english.yml",
        "localization/english/replace/overwriting_l_english.yml",
        "localization/french/ut_l_french.yml",
        "localization/german/replace/overwriting_l_german.yml",
    }


def test_archive_notification_skips_non_source_language_files(tmp_path):
    source_root = tmp_path / "mod"
    english_file = source_root / "localization" / "english" / "ut_l_english.yml"
    french_file = source_root / "localization" / "french" / "ut_l_french.yml"
    _write_loc(english_file, "l_english", "ut.key", "Hello")
    _write_loc(french_file, "l_french", "ut.key", "Bonjour")

    archive_manager = FakeArchiveManager()
    service = FileService(kanban_service=None, archive_manager=archive_manager, project_repository=None)
    files = [
        {"file_type": "source", "file_path": str(english_file)},
        {"file_type": "source", "file_path": str(french_file)},
    ]

    service._notify_archive_manager("project-1", "Project Utopia", str(source_root), files, "english")

    assert len(archive_manager.source_versions) == 1
    mod_id, source_files_data = archive_manager.source_versions[0]
    assert mod_id == 7
    assert [file["file_path"] for file in source_files_data] == ["localization/english/ut_l_english.yml"]
    assert source_files_data[0]["key_map"] == ["ut.key:0"]
    assert source_files_data[0]["texts_to_translate"] == ["Hello"]
