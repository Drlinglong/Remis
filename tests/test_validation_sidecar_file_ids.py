from scripts.core.services.validation_sidecar_service import ValidationSidecarService


def test_attach_project_file_ids_matches_absolute_and_relative_issue_paths(tmp_path):
    target = tmp_path / "localization" / "simp_chinese" / "events_l_simp_chinese.yml"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")
    files = [{"file_id": "file-1", "file_path": str(target)}]

    issues = ValidationSidecarService.attach_project_file_ids(
        [
            {"file_path": str(target), "file_name": target.name, "key": "absolute"},
            {"file_name": "localization/simp_chinese/events_l_simp_chinese.yml", "key": "relative"},
        ],
        files,
    )

    assert [issue["file_id"] for issue in issues] == ["file-1", "file-1"]


def test_attach_project_file_ids_does_not_guess_ambiguous_basenames(tmp_path):
    files = [
        {"file_id": "file-1", "file_path": str(tmp_path / "a" / "events.yml")},
        {"file_id": "file-2", "file_path": str(tmp_path / "b" / "events.yml")},
    ]
    issue = ValidationSidecarService.attach_project_file_ids(
        [{"file_name": "events.yml", "key": "ambiguous"}],
        files,
    )[0]

    assert "file_id" not in issue
