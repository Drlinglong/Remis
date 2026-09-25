"""Newline restoration remains format-aware through translation and CSV writeback."""

import csv
import io
import json
from types import SimpleNamespace

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.agents.fix_agent import _parse_fix_translations
from scripts.core import surviving_mars_csv
from scripts.utils.structured_parser import parse_response
from scripts.utils.text_clean import MASK_NEWLINE, mask_special_tokens, restore_special_tokens


def test_restore_keeps_paradox_default_but_can_restore_a_real_lf():
    encoded = f"first{MASK_NEWLINE}second"

    assert restore_special_tokens(encoded, "zh-CN") == r"first\nsecond"
    assert restore_special_tokens(encoded, "zh-CN", preserve_newlines=True) == "first\nsecond"
    assert restore_special_tokens(r"literal\nsequence", "zh-CN", preserve_newlines=True) == r"literal\nsequence"


def test_parse_response_defaults_to_paradox_and_supports_explicit_mars_policy():
    payload = json.dumps({"translations": [f"first{MASK_NEWLINE}second"]}, ensure_ascii=False)

    assert parse_response(payload, target_lang="zh-CN").translations == [r"first\nsecond"]
    assert parse_response(payload, target_lang="zh-CN", preserve_newlines=True).translations == ["first\nsecond"]


def test_mars_batch_parse_and_csv_rewrite_keep_real_lf(tmp_path):
    source_output = io.StringIO(newline="")
    writer = csv.writer(source_output, lineterminator="\r\n")
    writer.writerow(surviving_mars_csv.HEADER)
    writer.writerow(["0001", "English line one\nEnglish line two", "", "", ""])
    source_text = source_output.getvalue()
    translated = "中文第一行\n中文第二行"
    response = json.dumps({"translations": [mask_special_tokens(translated)]}, ensure_ascii=False)
    profile = {"format_adapter_id": "surviving_mars_csv"}

    result = BaseApiHandler._parse_response(
        object(), response, ["source"], "zh-CN", profile
    )
    rewritten = surviving_mars_csv.rewrite_text(
        source_text,
        result,
        {0: {"key_part": "0001", "row_index": 1}},
    )
    path = tmp_path / "table.csv"
    path.write_text(rewritten, encoding="utf-8", newline="")
    entry = surviving_mars_csv.entries(path, "Translation")[0]

    assert entry.value == translated
    assert r"\n" not in entry.value


def test_single_text_translation_uses_profile_and_keeps_literal_backslash_n():
    handler = SimpleNamespace(
        _build_single_text_prompt=lambda *args: "prompt",
        _call_api=lambda client, prompt: f"wrapped {MASK_NEWLINE} text and \\n literal",
        client=object(),
        logger=None,
    )
    result = BaseApiHandler.translate_single_text(
        handler,
        "source", "task", "mod", {}, {"code": "zh-CN"}, "context",
        {"format_adapter_id": "surviving_mars_csv"},
    )

    assert result == "wrapped\ntext and \\n literal"


def test_translation_fixer_passes_mars_newline_policy():
    task = BatchTask(
        file_task=FileTask(
            filename="table.csv", root="", original_lines=[], texts_to_translate=["source"],
            key_map={}, is_custom_loc=False, target_lang={"code": "zh-CN", "name": "Chinese"},
            source_lang={}, game_profile={"format_adapter_id": "surviving_mars_csv"},
            mod_context="", provider_name="mock", output_folder_name="", source_dir="",
            dest_dir="", client=object(), mod_name="mod",
        ),
        batch_index=0, start_index=0, end_index=1, texts=["source"],
    )
    handler = SimpleNamespace(
        client=object(),
        _call_api=lambda client, prompt: json.dumps({"translations": [f"fixed{MASK_NEWLINE}line"]}),
    )
    warning = SimpleNamespace(
        level="error", line_number=1, message="bad", details="",
    )

    success, fixed = TranslationFixerAgent(handler).attempt_fix(
        task, ["old"], [warning], max_retries=1
    )

    assert success is True
    assert fixed == ["fixed\nline"]


def test_reflexion_batch_fixer_uses_game_id_for_newline_policy():
    response = json.dumps({"translations": [f"fixed{MASK_NEWLINE}line"]})

    assert _parse_fix_translations(response, "surviving_mars") == ["fixed\nline"]
    assert _parse_fix_translations(response, "hoi4") == [r"fixed\nline"]


def test_fixer_fallback_rejects_unclosed_brackets_and_nontext_arrays(monkeypatch):
    monkeypatch.setattr("scripts.utils.structured_parser.parse_response", lambda *a, **kw: None)
    assert _parse_fix_translations("[" * 100_000, "surviving_mars") == []
    assert _parse_fix_translations('prefix ["text"] suffix', "surviving_mars") == ["text"]
    assert _parse_fix_translations('prefix [1, {"bad": true}] suffix', "surviving_mars") == []
