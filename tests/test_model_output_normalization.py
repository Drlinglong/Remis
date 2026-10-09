"""Output normalization after retiring the [[_QT_]] / [[_NL_]] input masks."""

import pytest

from scripts.core.base_handler import BaseApiHandler, _build_numbered_input
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.utils.structured_parser import parse_response
from scripts.utils.text_clean import (
    QUOTE_STYLES,
    apply_quote_style,
    normalize_model_output,
    restore_legacy_mask_tokens,
)


def _file_task(texts):
    return FileTask(
        filename="sample_l_english.yml", root="root", original_lines=[],
        texts_to_translate=texts, key_map={}, is_custom_loc=False,
        target_lang={"code": "zh-CN", "name": "Simplified Chinese"},
        source_lang={"code": "en", "name": "English"},
        game_profile={"id": "victoria3"}, mod_context="", provider_name="openai",
        output_folder_name="output", source_dir="source", dest_dir="dest",
        client=None, mod_name="Demo",
    )


# --- Input: nothing is masked -------------------------------------------------

def test_numbered_input_keeps_quotes_and_paradox_line_breaks_visible():
    texts = ['He said "Hello"\\nThen [GetName] left', 'Plain']
    task = BatchTask(_file_task(texts), 0, 0, 2, texts)

    numbered, _ = _build_numbered_input(task, texts)

    assert numbered == '1. "He said \\"Hello\\"\\\\nThen [GetName] left"\n2. "Plain"'
    assert "_QT_" not in numbered and "_NL_" not in numbered


def test_neighbor_context_is_serialized_not_masked():
    task = BatchTask(_file_task(["x"]), 0, 0, 1, ["x"])
    task.context_entries = [{"key": "k", "source": 'Say "hi"\\n$VAL$'}]

    prompt = BaseApiHandler._build_source_context_prompt(task)

    assert '- k: "Say \\"hi\\"\\\\n$VAL$"' in prompt
    assert "_QT_" not in prompt


def test_prompt_templates_no_longer_mention_legacy_tokens():
    from scripts.config import prompts

    for name in dir(prompts):
        value = getattr(prompts, name)
        if isinstance(value, str):
            assert "_QT_" not in value and "_NL_" not in value, name


# --- Output: JSON values with quotes ---------------------------------------

def test_quotes_inside_json_values_are_parsed_and_styled():
    raw = '{"translations": ["他说\\"你好\\"", "$VAL$ [GetName]"]}'
    parsed = parse_response(raw, target_lang="zh-CN")
    assert parsed.translations == ["他说“你好”", "$VAL$ [GetName]"]


def test_json_newline_escape_and_literal_paradox_newline_both_become_literal():
    raw = '{"translations": ["A\\nB", "C\\\\nD"]}'
    parsed = parse_response(raw, target_lang="en")
    assert parsed.translations == ["A\\nB", "C\\nD"]


@pytest.mark.parametrize("text", [
    'odd " quote',                       # unpaired
    'Size 5" and 6"',                    # inch marks: open quote followed by space
    '[Concept("war", "War")] "x"',      # quote inside a protected token
    'Already \\"escaped\\"',            # serialized quotes are left alone
    '"" empty',                          # empty pair
])
def test_ambiguous_quotes_are_left_unchanged(text):
    assert apply_quote_style(text, "zh") == text


@pytest.mark.parametrize("text", [
    '[Concept("war", "War")] "x"',
    '[Outer("a", [Inner("b")])] "x"',
    '$VAR"x"$ "outside"',
    '[prefix $VAR"x"$ "outside"',
    '$prefix["x"$] "outside"',
])
def test_quote_protection_preserves_nested_and_overlapping_runtime_tokens(text):
    assert apply_quote_style(text, "en") == text


def test_tokens_without_quotes_allow_prose_quotes_to_be_styled():
    assert apply_quote_style('[Root.GetName] $VAR$ "hello"', "en") == '[Root.GetName] $VAR$ “hello”'
    assert apply_quote_style('$not a token "hello" $', "en") == '$not a token “hello” $'


def test_unclosed_bracket_run_does_not_block_normalization():
    """A bounded child prevents a quadratic regression from hanging pytest."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "from scripts.utils.text_clean import apply_quote_style; "
         "prefix = '[' * 500000; "
         "assert apply_quote_style(prefix + chr(34) + 'ok' + chr(34), 'en') "
         "== prefix + chr(0x201c) + 'ok' + chr(0x201d)"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_nested_straight_quotes_are_ambiguous_and_left_unchanged():
    assert apply_quote_style('"a "b" c"', "en") == '"a "b" c"'


def test_multiple_quote_pairs_alternate_open_close():
    assert apply_quote_style('"a" and "b"', "en") == "“a” and “b”"


def test_unknown_language_keeps_straight_quotes_for_the_writer_to_escape():
    assert normalize_model_output('Say "hi"', "xx") == 'Say "hi"'


def test_regional_code_falls_back_to_base_language():
    assert normalize_model_output('Diz "oi"', "pt-BR") == "Diz “oi”"


def test_french_style_does_not_double_spaces():
    assert normalize_model_output('Il a dit "Bonjour"', "fr") == "Il a dit « Bonjour »"


@pytest.mark.parametrize("lang", [lang for lang in QUOTE_STYLES])
def test_every_configured_language_styles_a_simple_pair(lang):
    open_q, close_q = QUOTE_STYLES[lang]
    assert normalize_model_output('"test"', lang) == f"{open_q}test{close_q}"


def test_real_newline_becomes_literal_and_existing_literal_is_preserved():
    assert normalize_model_output("Line 1\r\nLine 2\\nLine 3", "en") == "Line 1\\nLine 2\\nLine 3"


# --- Legacy compatibility restore ------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("He said [[_QT_]]Hello[[_QT_]]", "He said “Hello”"),
    ("He said [[ _QT_ ]]Hello[[_QT_ ]]", "He said “Hello”"),
    ("He said [ [_QT_]]Hello[_QT_]]", "He said “Hello”"),
    ("He said [[_QT_]Hello[_QT_]]", "He said “Hello”"),
    ("He said _QT_]]Hello[[_QT_", "He said “Hello”"),
    ("Line 1 [[_NL_]] Line 2", "Line 1\\nLine 2"),
    ("Line 1[[ _NL_ ]]Line 2", "Line 1\\nLine 2"),
    ("_QT_", '"'),
    ("NL_", "\\n"),
])
def test_legacy_and_malformed_mask_fragments_are_restored(raw, expected):
    assert normalize_model_output(raw, "en") == expected


def test_odd_legacy_quote_count_is_not_flip_flopped():
    # The old restore reversed every later quote; now the text stays unstyled.
    assert normalize_model_output("a [[_QT_]]b[[_QT_]]c[[_QT_]]d", "zh") == 'a "b"c"d'


def test_legacy_restore_does_not_touch_identifiers_or_spaced_line_breaks():
    for text in ("$MY_QT_VAR$", "KEY_NL_VALUE", "keep \\n spaced"):
        assert restore_legacy_mask_tokens(text) == text


def test_structured_parser_restores_legacy_tokens_from_archives():
    parsed = parse_response('["[[_QT_]]hi[[_QT_]][[_NL_]]x"]', target_lang="de")
    assert parsed.translations == ["„hi“\\nx"]


def test_full_batch_prompt_explains_unmasked_encoding(monkeypatch):
    from scripts.core.base_handler import glossary_manager, prompt_manager

    class _Handler(BaseApiHandler):
        def initialize_client(self):
            return None

        def _call_api(self, client, prompt):
            return ""

    monkeypatch.setattr(glossary_manager, "get_glossary_for_translation", lambda: None)
    monkeypatch.setattr(prompt_manager, "get_custom_global_prompt", lambda: "")
    handler = _Handler("openai", provider_config_snapshot={"default_model": "m"})
    texts = ['He said "Hello"\\nBye']
    prompt = handler._build_prompt(BatchTask(_file_task(texts), 0, 0, 1, texts))

    assert "SOURCE VALUE ENCODING" in prompt
    assert '1. "He said \\"Hello\\"\\\\nBye"' in prompt
    assert "_QT_" not in prompt and "_NL_" not in prompt


# --- Single-text path (mod name / description) -----------------------------

@pytest.mark.parametrize("raw, expected", [
    ('"风味包"', "风味包"),                          # wrapper only
    ('"\\"New Dawn\\""', '"New Dawn"'),            # JSON literal keeps semantic quotes
    ('"The "New" Dawn"', 'The "New" Dawn'),          # invalid JSON: strip one pair only
    ('The "New" Dawn', 'The "New" Dawn'),            # no wrapper: unchanged
    ('"x', '"x'),
])
def test_single_text_response_keeps_semantic_quotes(raw, expected):
    from scripts.core.translation_input_encoding import decode_single_text_response

    assert decode_single_text_response(raw) == expected


def test_single_text_prompt_serializes_source(monkeypatch):
    from scripts.core.base_handler import glossary_manager, prompt_manager

    class _Handler(BaseApiHandler):
        def initialize_client(self):
            return None

        def _call_api(self, client, prompt):
            return '"\\"新\\"黎明"'

    monkeypatch.setattr(glossary_manager, "get_glossary_for_translation", lambda: None)
    monkeypatch.setattr(prompt_manager, "get_custom_global_prompt", lambda: "")
    handler = _Handler("openai", provider_config_snapshot={"default_model": "m"})
    profile = {"single_prompt_template": "Translate {task_description} for {mod_name} from {source_lang_name} to {target_lang_name}.\n"}
    source = 'The "New"\nDawn'
    args = (source, "mod name", "Demo", {"code": "en", "name": "English"},
            {"code": "zh-CN", "name": "Chinese"}, "", profile)

    prompt = handler._build_single_text_prompt(*args)
    assert 'Translate this: "The \\"New\\"\\nDawn"' in prompt
    assert handler.translate_single_text(*args) == "“新”黎明"
