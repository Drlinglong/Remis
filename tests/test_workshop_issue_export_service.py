from pathlib import Path

from scripts.core.services.workshop_issue_export_service import WorkshopIssueExportService


def _write_loc(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def test_export_includes_structured_issue_details(tmp_path):
    source_root = tmp_path / "source"
    output_root = tmp_path / "output"

    _write_loc(
        source_root / "localization" / "simp_chinese" / "sample_l_simp_chinese.yml",
        'l_simp_chinese:\n demo.key:0 "你好。"\n',
    )
    _write_loc(
        output_root / "localization" / "english" / "sample_l_english.yml",
        'l_english:\n demo.key:0 "Hello，"\n',
    )

    result = WorkshopIssueExportService().export_for_output(
        output_root=output_root,
        source_root=source_root,
        source_lang_info={"code": "zh-CN", "key": "l_simp_chinese"},
        target_lang_info={"code": "en", "key": "l_english"},
        game_profile={"id": "victoria3"},
        workflow="test",
        project_name="Demo",
    )

    assert result["issue_count"] >= 1
    issue = next(
        item for item in result["issues"]
        if item["error_code"] == "validation_residual_punctuation_found"
    )
    assert issue["error_code"] == "validation_residual_punctuation_found"
    assert issue["details_code"] == "validation_residual_punctuation_details_localized"
    assert issue["details_params"] == {"punctuations": "，"}
