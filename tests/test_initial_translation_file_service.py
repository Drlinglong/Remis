import os

from scripts.core.parallel_types import FileTask
from scripts.core.services import initial_translation_file_service as file_service


class FakeTracker:
    def __init__(self):
        self.files = []

    def add_file_info(self, info):
        self.files.append(info)


class FakeCheckpoint:
    def __init__(self):
        self.completed = []

    def mark_file_completed(self, filename):
        self.completed.append(filename)


def _file_task(source_root, **overrides):
    data = {
        "filename": "events_l_english.yml",
        "root": os.path.join(source_root, "MyMod", "module_a", "localization", "english", "replace"),
        "original_lines": ["l_english:"],
        "texts_to_translate": ["Hello"],
        "key_map": [{"key_part": "event.title"}],
        "is_custom_loc": False,
        "target_lang": {"code": "zh-CN", "key": "l_simp_chinese"},
        "source_lang": {"code": "en", "key": "l_english"},
        "game_profile": {"source_localization_folder": "localization"},
        "mod_context": "",
        "provider_name": "gemini",
        "output_folder_name": "zh-CN-MyMod",
        "source_dir": source_root,
        "dest_dir": "unused",
        "client": None,
        "mod_name": "MyMod",
        "loc_root": os.path.join(source_root, "MyMod", "module_a", "localization"),
        "file_path": "module_a/localization/english/replace/events_l_english.yml",
    }
    data.update(overrides)
    return FileTask(**data)


def test_build_dest_dir_preserves_module_structure(monkeypatch, tmp_path):
    source_root = str(tmp_path / "source")
    dest_root = str(tmp_path / "dest")
    monkeypatch.setattr(file_service, "SOURCE_DIR", source_root)
    monkeypatch.setattr(file_service, "DEST_DIR", dest_root)

    task = _file_task(source_root)

    assert os.path.normpath(file_service.build_dest_dir(
        task,
        {"key": "l_simp_chinese"},
        "zh-CN-MyMod",
        {"source_localization_folder": "localization"},
    )) == os.path.normpath(os.path.join(
        dest_root,
        "zh-CN-MyMod",
        "module_a",
        "localization",
        "simp_chinese",
        "replace",
    ))


def test_build_dest_dir_uses_relative_file_path_across_drives(monkeypatch):
    monkeypatch.setattr(file_service, "SOURCE_DIR", r"J:\V3_Mod_Localization_Factory\source_mods")
    monkeypatch.setattr(file_service, "DEST_DIR", r"J:\V3_Mod_Localization_Factory\translated_mods")

    task = _file_task(
        r"C:\Users\Drlin\AppData\Local\Remis\projects",
        root=r"C:\Users\Drlin\AppData\Local\Remis\projects\MyMod\localization\simp_chinese",
        loc_root=r"C:\Users\Drlin\AppData\Local\Remis\projects\MyMod\localization",
        file_path="localization/simp_chinese/remis_demo_l_simp_chinese.yml",
        filename="remis_demo_l_simp_chinese.yml",
    )

    assert os.path.normpath(file_service.build_dest_dir(
        task,
        {"key": "l_simp_chinese"},
        "zh-CN-MyMod",
        {"source_localization_folder": "localization"},
    )) == os.path.normpath(
        r"J:\V3_Mod_Localization_Factory\translated_mods\zh-CN-MyMod\localization\simp_chinese"
    )


def test_handle_empty_file_writes_fallback_and_tracks_file(monkeypatch, tmp_path):
    source_root = str(tmp_path / "source")
    dest_root = str(tmp_path / "dest")
    monkeypatch.setattr(file_service, "SOURCE_DIR", source_root)
    monkeypatch.setattr(file_service, "DEST_DIR", dest_root)

    created = []

    def fake_create_fallback_file(source_path, dest_dir, filename, source_lang, target_lang, game_profile):
        created.append((source_path, dest_dir, filename))
        return os.path.join(dest_dir, filename)

    monkeypatch.setattr(file_service.file_builder, "create_fallback_file", fake_create_fallback_file)

    tracker = FakeTracker()
    file_info = {
        "filename": "empty_l_english.yml",
        "root": os.path.join(source_root, "MyMod", "localization", "english"),
        "is_custom_loc": False,
        "loc_root": os.path.join(source_root, "MyMod", "localization"),
    }

    file_service.handle_empty_file(
        file_info,
        original_lines=[],
        texts=[],
        key_map=[],
        source_lang={"code": "en", "key": "l_english"},
        target_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        game_profile={"source_localization_folder": "localization"},
        output_folder_name="zh-CN-MyMod",
        mod_name="MyMod",
        proofreading_tracker=tracker,
    )

    assert created[0][0] == os.path.join(file_info["root"], "empty_l_english.yml")
    assert tracker.files[0]["translated_lines"] == 0
    assert tracker.files[0]["is_custom_loc"] is False


def test_finalize_translated_file_updates_tracker_checkpoint_and_archive(monkeypatch, tmp_path):
    source_root = str(tmp_path / "source")
    dest_root = str(tmp_path / "dest")
    monkeypatch.setattr(file_service, "SOURCE_DIR", source_root)
    monkeypatch.setattr(file_service, "DEST_DIR", dest_root)

    task = _file_task(source_root)
    tracker = FakeTracker()
    checkpoint = FakeCheckpoint()
    archive_calls = []
    synced_paths = []

    def fake_rebuild_and_write_file(*args):
        dest_dir = args[4]
        filename = args[5]
        return os.path.join(dest_dir, filename)

    monkeypatch.setattr(file_service.file_builder, "rebuild_and_write_file", fake_rebuild_and_write_file)
    monkeypatch.setattr(file_service, "sync_project_file_status", lambda path: synced_paths.append(path))
    monkeypatch.setattr(
        file_service.archive_manager,
        "archive_translated_results",
        lambda version_id, results, all_files_content, lang_code: archive_calls.append(
            (version_id, results, all_files_content, lang_code)
        ),
    )

    file_service.finalize_translated_file(
        task,
        translated_texts=["你好"],
        is_failed=False,
        target_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        output_folder_name="zh-CN-MyMod",
        game_profile={"source_localization_folder": "localization"},
        proofreading_tracker=tracker,
        checkpoint_manager=checkpoint,
        project_id="project-1",
        version_id=9,
        all_files_content=[{"filename": "events_l_english.yml"}],
    )

    source_file_path = os.path.join(task.root, task.filename)
    assert tracker.files[0]["source_path"] == source_file_path
    assert tracker.files[0]["translated_lines"] == 1
    assert checkpoint.completed == ["events_l_english.yml"]
    assert synced_paths == [source_file_path]
    assert archive_calls == [
        (
            9,
            {"module_a/localization/english/replace/events_l_english.yml": ["你好"]},
            [{"filename": "events_l_english.yml"}],
            "zh-CN",
        )
    ]


def test_finalize_failed_file_writes_fallback_without_success_side_effects(monkeypatch, tmp_path):
    source_root = str(tmp_path / "source")
    dest_root = str(tmp_path / "dest")
    monkeypatch.setattr(file_service, "SOURCE_DIR", source_root)
    monkeypatch.setattr(file_service, "DEST_DIR", dest_root)

    task = _file_task(source_root)
    tracker = FakeTracker()
    checkpoint = FakeCheckpoint()
    archive_calls = []
    synced_paths = []

    def fake_rebuild_and_write_file(*args):
        dest_dir = args[4]
        filename = args[5]
        return os.path.join(dest_dir, filename)

    monkeypatch.setattr(file_service.file_builder, "rebuild_and_write_file", fake_rebuild_and_write_file)
    monkeypatch.setattr(file_service, "sync_project_file_status", lambda path: synced_paths.append(path))
    monkeypatch.setattr(
        file_service.archive_manager,
        "archive_translated_results",
        lambda *args: archive_calls.append(args),
    )

    file_service.finalize_translated_file(
        task,
        translated_texts=task.texts_to_translate,
        is_failed=True,
        target_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        output_folder_name="zh-CN-MyMod",
        game_profile={"source_localization_folder": "localization"},
        proofreading_tracker=tracker,
        checkpoint_manager=checkpoint,
        project_id="project-1",
        version_id=9,
        all_files_content=[{"filename": "events_l_english.yml"}],
    )

    assert tracker.files[0]["translated_lines"] == 1
    assert tracker.files[0]["translation_failed"] is True
    assert checkpoint.completed == []
    assert synced_paths == []
    assert archive_calls == []
