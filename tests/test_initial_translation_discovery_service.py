import os

from scripts.core.services import initial_translation_discovery_service as discovery_service


def test_discover_localizable_files_preserves_nested_module_paths(tmp_path):
    mod_root = tmp_path / "MyMod"
    loc_root = mod_root / "module_a" / "localization"
    file_dir = loc_root / "simp_chinese" / "replace"
    file_dir.mkdir(parents=True)
    source_file = file_dir / "events_l_simp_chinese.yml"
    source_file.write_text("l_simp_chinese:\n key:0 \"Text\"", encoding="utf-8")

    files = discovery_service.discover_localizable_files(
        "MyMod",
        {"source_localization_folder": "localization"},
        {"key": "l_simp_chinese", "name": "Chinese"},
        override_path=str(mod_root),
    )

    assert files == [
        {
            "path": str(source_file),
            "file_path": "module_a/localization/simp_chinese/replace/events_l_simp_chinese.yml",
            "filename": "events_l_simp_chinese.yml",
            "root": str(file_dir),
            "is_custom_loc": False,
            "loc_root": str(loc_root),
        }
    ]


def test_discover_localizable_files_includes_custom_localization(tmp_path):
    mod_root = tmp_path / "MyMod"
    custom_dir = mod_root / "customizable_localization" / "scripted"
    custom_dir.mkdir(parents=True)
    custom_file = custom_dir / "custom_loc.txt"
    custom_file.write_text("defined_text = {}", encoding="utf-8")

    files = discovery_service.discover_localizable_files(
        "MyMod",
        {"source_localization_folder": "localization"},
        {"key": "l_english", "name": "English"},
        override_path=str(mod_root),
    )

    assert files == [
        {
            "path": str(custom_file),
            "file_path": "customizable_localization/scripted/custom_loc.txt",
            "filename": "custom_loc.txt",
            "root": str(custom_dir),
            "is_custom_loc": True,
            "loc_root": "",
        }
    ]


def test_initial_translate_discover_files_keeps_compatibility(monkeypatch, tmp_path):
    from scripts.workflows import initial_translate

    mod_root = tmp_path / "MyMod"
    loc_dir = mod_root / "localization" / "english"
    loc_dir.mkdir(parents=True)
    (loc_dir / "events_l_english.yml").write_text("l_english:\n key:0 \"Text\"", encoding="utf-8")

    monkeypatch.setattr(initial_translate, "SOURCE_DIR", os.fspath(tmp_path))

    files = initial_translate.discover_files(
        "MyMod",
        {"source_localization_folder": "localization"},
        {"key": "l_english", "name": "English"},
    )

    assert files[0]["filename"] == "events_l_english.yml"
