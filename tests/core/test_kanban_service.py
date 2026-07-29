from scripts.core.services.kanban_service import KanbanService


def test_preview_board_for_files_does_not_create_sidecar(tmp_path):
    source_file = tmp_path / "localization" / "english" / "demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_text('l_english:\n demo.key:0 "Demo"\n', encoding="utf-8")
    files = [
        {
            "file_id": "demo-file",
            "project_id": "demo-project",
            "file_path": str(source_file),
            "status": "todo",
            "file_type": "source",
            "line_count": 2,
        }
    ]

    board = KanbanService().preview_board_for_files(str(tmp_path), files)

    assert board["tasks"]["demo-file"]["filePath"] == str(source_file)
    assert not (tmp_path / ".remis_project.json").exists()
