from pathlib import Path

from scripts.core.post_processing_manager import PostProcessingManager


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
