from pathlib import Path

from scripts.core.post_processing_manager import PostProcessingManager
import pytest


def test_validation_sanitization_proposal_does_not_write_file(tmp_path):
    source_root = tmp_path / "source"
    target_file = tmp_path / "target" / "demo_l_english.yml"
    source_root.mkdir()
    target_file.parent.mkdir()
    target_file.write_text(
        'l_english:\n demo.one:0 "Text#!#！"\n',
        encoding="utf-8",
    )
    before = target_file.read_bytes()
    manager = PostProcessingManager(
        {"id": "victoria3", "name": "Victoria 3"},
        str(tmp_path / "output"),
        source_root=str(source_root),
    )

    manager._validate_single_file(
        str(target_file),
        {"code": "en", "key": "l_english"},
        {"code": "en", "key": "l_english"},
    )

    assert target_file.read_bytes() == before


@pytest.mark.parametrize("existing", [False, True])
def test_validation_cannot_report_success_without_scanning_files(tmp_path, existing):
    output = tmp_path / "output"
    if existing:
        (output / "localization/simp_chinese").mkdir(parents=True)
    manager = PostProcessingManager({"id": "vic3"}, str(output))
    assert manager.run_validation(
        {"code": "zh-CN", "key": "l_simp_chinese"},
        {"code": "en", "key": "l_english"},
    ) is False
    assert manager.total_files == 0


@pytest.mark.parametrize("mixed", [False, True])
def test_validation_reports_syntax_errors_without_mutating_file(tmp_path, mixed):
    output = tmp_path / "output"
    path = output / "localization/english/demo_l_english.yml"
    path.parent.mkdir(parents=True)
    content = 'l_english:\n' + (' good:0 "Good"\n' if mixed else '') + ' broken:0 "unterminated\n'
    path.write_text(content, encoding="utf-8-sig")
    before = path.read_bytes()
    manager = PostProcessingManager({"id": "stellaris"}, str(output))
    assert manager.run_validation({"code": "en", "key": "l_english"}, {"code": "en"}) is False
    assert manager.total_errors == 1
    assert manager.valid_files == 0
    assert manager.validation_results[str(path)][0].code == "unterminated_value"
    assert path.read_bytes() == before
