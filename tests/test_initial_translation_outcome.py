from unittest.mock import MagicMock

import pytest

from scripts.core.services.initial_translation_snapshot_service import (
    SourceFileIssue,
    SourceReadResult,
)
from scripts.workflows import initial_translate


def _patch_run_dependencies(monkeypatch, source_result):
    handler = MagicMock()
    handler.client = object()
    monkeypatch.setattr(initial_translate, "create_translation_handler", lambda *args: handler)
    monkeypatch.setattr(initial_translate, "load_glossaries_for_run", lambda *args: None)
    monkeypatch.setattr(initial_translate, "prepare_output_workspace", lambda *args: "output")
    monkeypatch.setattr(
        initial_translate,
        "discover_files",
        lambda *args, **kwargs: [{"filename": "source_l_english.yml"}],
    )
    monkeypatch.setattr(
        initial_translate,
        "read_files_for_backup",
        lambda *args, **kwargs: source_result,
    )
    monkeypatch.setattr(initial_translate, "create_source_snapshot", lambda *args: (1, 2))
    monkeypatch.setattr(initial_translate, "run_language_translation", MagicMock())
    monkeypatch.setattr(initial_translate, "finalize_workflow_run", MagicMock())


def _run():
    return initial_translate.run(
        mod_name="TestMod",
        source_lang={"code": "en", "name": "English", "key": "l_english"},
        target_languages=[{
            "code": "zh-CN",
            "name": "Simplified Chinese",
            "key": "l_simp_chinese",
        }],
        game_profile={"id": "stellaris", "source_localization_folder": "localisation"},
        mod_context="",
    )


def test_run_returns_partial_failed_when_a_source_entry_is_recovered(monkeypatch):
    issue = SourceFileIssue(
        filename="source_l_english.yml",
        code="unterminated_value",
        line_number=14,
        key="broken:0",
        recoverable=True,
        action="empty_value",
    )
    _patch_run_dependencies(
        monkeypatch,
        SourceReadResult(
            files=[{"filename": "source_l_english.yml", "texts_to_translate": ["Text"]}],
            issues=[issue],
        ),
    )

    outcome = _run()

    assert outcome.status == "partial_failed"
    assert outcome.issue_count == 1
    assert outcome.recovered_entry_count == 1
    assert outcome.dropped_file_count == 0


def test_run_fails_when_every_discovered_file_is_dropped(monkeypatch):
    issue = SourceFileIssue(
        filename="source_l_english.yml",
        code="unterminated_value",
        line_number=14,
        key="broken:0",
        recoverable=False,
        action="drop_file",
    )
    _patch_run_dependencies(
        monkeypatch,
        SourceReadResult(files=[], issues=[issue]),
    )

    with pytest.raises(
        RuntimeError,
        match=r"source_l_english\.yml:14 unterminated_value",
    ):
        _run()
