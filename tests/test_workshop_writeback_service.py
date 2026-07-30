import json
from pathlib import Path

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services import embedded_workshop_service
from scripts.core.services import workshop_writeback_service as writeback


def _write_loc_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'l_english:\n demo.one:0 "{value}"\n', encoding="utf-8-sig")


def test_project_target_must_stay_inside_registered_translation_directory(tmp_path):
    project_root = tmp_path / "project"
    translation_root = tmp_path / "translation"
    source_file = project_root / "events" / "demo_l_english.yml"
    translation_file = translation_root / "events" / "demo_l_english.yml"
    project_root.mkdir()
    _write_loc_file(source_file, "source")
    _write_loc_file(translation_file, "translation")
    ProjectJsonManager(str(project_root)).update_config({
        "translation_dirs": [str(translation_root)],
    })
    project = {"source_path": str(project_root)}

    assert writeback.resolve_project_translation_target(
        project,
        str(translation_file),
        "events/demo_l_english.yml",
    ) == translation_file.resolve()
    assert writeback.resolve_project_translation_target(
        project,
        str(source_file),
        str(source_file),
    ) is None


def test_final_validation_failure_restores_exact_original_file(monkeypatch, tmp_path):
    target_file = tmp_path / "translation" / "demo_l_english.yml"
    _write_loc_file(target_file, "old value")
    original_bytes = target_file.read_bytes()
    validation_results = iter([[], ["still invalid"]])
    monkeypatch.setattr(
        writeback,
        "_validation_errors",
        lambda *_args, **_kwargs: next(validation_results),
    )

    applied, reason, message = writeback.apply_validated_workshop_fix_to_path(
        target_path=target_file,
        game_id="stellaris",
        key="demo.one:0",
        source_str="source value",
        suggested_fix="new value",
        target_lang="en",
    )

    assert applied is False
    assert reason == "post_validation_failure"
    assert "Original file was restored" in message
    assert target_file.read_bytes() == original_bytes


def test_invalid_key_issue_is_scan_only():
    assert writeback.is_repairable_workshop_issue({
        "error_code": "validation_invalid_key_format",
    }) is False
    assert writeback.is_repairable_workshop_issue({
        "error_code": "validation_variable_parity_mismatch",
    }) is True


def test_embedded_workshop_excludes_invalid_keys_before_batching(tmp_path):
    sidecar = tmp_path / "workshop_issues.json"
    sidecar.write_text(json.dumps({
        "issues": [
            {"key": "broken key:0", "error_code": "validation_invalid_key_format"},
            {"key": "valid.key:0", "error_code": "validation_variable_parity_mismatch"},
        ],
    }), encoding="utf-8")

    assert [issue["key"] for issue in embedded_workshop_service._load_issues(sidecar)] == ["valid.key:0"]
