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
        "extract_translatable_content_with_diagnostics",
        lambda path: (["l_english:"], ["Hello"], {0: {"key_part": "hello.key"}}, ()),
    )

    result = snapshot_service.read_files_for_backup(
        file_infos,
        total_files=1,
        progress_callback=lambda *args, **kwargs: progress_events.append((args, kwargs)),
    )

    assert result.files[0]["original_lines"] == ["l_english:"]
    assert result.files[0]["texts_to_translate"] == ["Hello"]
    assert result.files[0]["key_map"] == {0: {"key_part": "hello.key"}}
    assert result.issues == []
    assert progress_events[0][0] == (0, 1, "source.yml", "Reading Source")


def test_read_files_recovers_line_local_unterminated_value(tmp_path):
    source = tmp_path / "broken_l_english.yml"
    source.write_text(
        'l_english:\n broken:0 "\n next:0 "Translate me"\n',
        encoding="utf-8-sig",
    )

    result = snapshot_service.read_files_for_backup(
        [{"path": str(source), "filename": source.name}],
        total_files=1,
    )

    assert len(result.files) == 1
    assert result.files[0]["texts_to_translate"] == ["Translate me"]
    assert result.files[0]["archive_texts"] == ["Translate me", ""]
    assert result.files[0]["recovered_entries"][0]["key_part"] == "broken:0"
    assert result.issues[0].recoverable is True
    assert result.issues[0].action == "empty_value"


def test_read_files_drops_ambiguous_file_and_keeps_valid_file(tmp_path):
    broken = tmp_path / "broken_l_english.yml"
    broken.write_text(
        'l_english:\n broken:0 "unterminated\n ambiguous continuation\n',
        encoding="utf-8-sig",
    )
    valid = tmp_path / "valid_l_english.yml"
    valid.write_text(
        'l_english:\n valid:0 "Translate me"\n',
        encoding="utf-8-sig",
    )

    result = snapshot_service.read_files_for_backup(
        [
            {"path": str(broken), "filename": broken.name},
            {"path": str(valid), "filename": valid.name},
        ],
        total_files=2,
    )

    assert [item["filename"] for item in result.files] == [valid.name]
    assert result.dropped_file_count == 1
    assert result.issues[0].code == "unterminated_value"
    assert result.issues[0].action == "drop_file"


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
