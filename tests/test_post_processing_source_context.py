from pathlib import Path

from scripts.core.post_processing_manager import PostProcessingManager


def test_post_processing_validation_uses_source_context(tmp_path):
    source_root = tmp_path / "source_mod"
    output_root = tmp_path / "output_mod"
    source_file = source_root / "localization" / "simp_chinese" / "demo_l_simp_chinese.yml"
    target_file = output_root / "localization" / "english" / "simp_chinese" / "demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    target_file.parent.mkdir(parents=True)

    source_file.write_text(
        'l_simp_chinese:\n demo.key:0 "你好，[Root.GetCountry.GetName]。"\n',
        encoding="utf-8-sig",
    )
    target_file.write_text(
        'l_english:\n demo.key:0 "Hello."\n',
        encoding="utf-8-sig",
    )

    manager = PostProcessingManager(
        {"id": "victoria3", "name": "Victoria 3", "source_localization_folder": "localization"},
        str(output_root),
        source_root=str(source_root),
    )

    manager.run_validation(
        {"code": "en", "key": "l_english"},
        {"code": "zh-CN", "key": "l_simp_chinese"},
    )

    stats = manager.get_validation_stats()
    assert stats["total_errors"] == 1
    assert stats["files_with_issues"] == 1
    result = next(iter(manager.validation_results.values()))[0]
    assert result.code == "validation_vic3_variable_parity_mismatch"
