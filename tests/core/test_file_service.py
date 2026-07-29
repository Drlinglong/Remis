import os

from scripts.core.services.file_service import FileService


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

    service = FileService()

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


def test_discovery_is_transient_and_reports_unavailable_roots(tmp_path):
    source_root = tmp_path / "mod"
    english_file = source_root / "localization" / "english" / "ut_l_english.yml"
    french_file = source_root / "localization" / "french" / "ut_l_french.yml"
    _write_loc(english_file, "l_english", "ut.key", "Hello")
    _write_loc(french_file, "l_french", "ut.key", "Bonjour")

    service = FileService()
    file_id = service.scan_dir(
        str(source_root),
        "source",
        "english",
        "project-1",
        [".yml", ".yaml"],
    )[0]["file_id"]
    manifest = service.discover_files(
        project_id="project-1",
        source_path=str(source_root),
        translation_dirs=[str(tmp_path / "missing-translation")],
        source_language="en",
        game_id="stellaris",
        status_by_file_id={file_id: "proofreading"},
    )

    assert manifest["file_count"] == 1
    assert manifest["files"][0]["file_path"] == str(english_file)
    assert manifest["files"][0]["status"] == "proofreading"
    assert manifest["warnings"] == [
        {
            "code": "directory_unavailable",
            "file_type": "translation",
            "path": str(tmp_path / "missing-translation"),
        }
    ]
    assert not (source_root / ".remis_project.json").exists()
