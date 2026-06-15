from scripts.core.strategies.file_linking import ParadoxFileLinkingStrategy


def test_paradox_file_linking_omits_metadata_and_preserves_notes(tmp_path):
    source_path = str(tmp_path)
    source_file = tmp_path / "localisation" / "demo_l_english.yml"
    metadata_file = tmp_path / "metadata.json"
    source_file.parent.mkdir()
    source_file.write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    metadata_file.write_text("{}", encoding="utf-8")

    files = [
        {
            "file_id": "source-id",
            "project_id": "project-id",
            "file_path": str(source_file),
            "status": "proofreading",
            "line_count": 2,
            "file_type": "source",
        },
        {
            "file_id": "metadata-id",
            "project_id": "project-id",
            "file_path": str(metadata_file),
            "status": "todo",
            "line_count": 1,
            "file_type": "metadata",
        },
    ]
    existing_tasks = {
        "metadata-id": {
            "id": "metadata-id",
            "type": "file",
            "title": "metadata.json",
            "status": "todo",
            "meta": {"file_type": "metadata"},
        },
        "note-id": {
            "id": "note-id",
            "type": "note",
            "title": "Manual note",
            "status": "todo",
        },
    }

    tasks = ParadoxFileLinkingStrategy().process_files(source_path, files, existing_tasks)

    assert set(tasks) == {"source-id", "note-id"}
    assert tasks["source-id"]["status"] == "proofreading"
    assert tasks["note-id"]["type"] == "note"
