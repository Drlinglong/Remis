from scripts.core.services import initial_translation_snapshot_service as snapshot_service


def test_get_chunk_size_for_provider_honors_override():
    assert snapshot_service.get_chunk_size_for_provider("gemini", batch_size_limit=0) >= 1
    assert snapshot_service.get_chunk_size_for_provider("gemini", batch_size_limit=12) == 12


def test_calculate_total_batches_skips_empty_files():
    files = [
        {"texts_to_translate": ["a", "b", "c"]},
        {"texts_to_translate": []},
        {"texts_to_translate": ["d"]},
        {},
    ]

    assert snapshot_service.calculate_total_batches(files, chunk_size=2) == 3


def test_read_files_for_backup_attaches_parsed_content(monkeypatch):
    progress_events = []
    file_infos = [
        {"path": "source.yml", "filename": "source.yml"},
    ]

    monkeypatch.setattr(
        snapshot_service.file_parser,
        "extract_translatable_content",
        lambda path: (["l_english:"], ["Hello"], [{"key_part": "hello.key"}]),
    )

    result = snapshot_service.read_files_for_backup(
        file_infos,
        total_files=1,
        progress_callback=lambda *args, **kwargs: progress_events.append((args, kwargs)),
    )

    assert result[0]["original_lines"] == ["l_english:"]
    assert result[0]["texts_to_translate"] == ["Hello"]
    assert result[0]["key_map"] == [{"key_part": "hello.key"}]
    assert progress_events[0][0] == (0, 1, "source.yml", "Reading Source")


def test_create_source_snapshot_uses_resolved_archive_name(monkeypatch):
    calls = []

    class FakeArchiveManager:
        def get_or_create_mod_entry(self, mod_name, remote_file_id):
            calls.append(("mod", mod_name, remote_file_id))
            return 42

        def create_source_version(self, mod_id, all_files_content):
            calls.append(("version", mod_id, all_files_content))
            return 7

    monkeypatch.setattr(snapshot_service, "archive_manager", FakeArchiveManager())
    monkeypatch.setattr(snapshot_service, "resolve_archive_mod_name", lambda mod_name, project_id=None: "Project Name")

    progress_events = []
    mod_id, version_id = snapshot_service.create_source_snapshot(
        "LocalFolder",
        [{"filename": "source.yml"}],
        total_files=1,
        total_batches=3,
        progress_callback=lambda *args, **kwargs: progress_events.append((args, kwargs)),
        project_id="project-1",
    )

    assert (mod_id, version_id) == (42, 7)
    assert calls == [
        ("mod", "Project Name", "local_LocalFolder"),
        ("version", 42, [{"filename": "source.yml"}]),
    ]
    assert progress_events[0] == ((0, 1, "", "Creating Backup"), {"total_batches": 3})
