# scripts/tests/test_loc_parser_quotes.py
# ---------------------------------------------------------------
# Regression tests for Issue #139:
# - Values starting with \" were skipped (not translated)
# - \"...\" was double-escaped to \\"...\\" during roundtrip

import pytest
from scripts.core.loc_parser import unescape_value, emit_loc_file


class TestUnescapeValue:
    def test_plain_text_unchanged(self):
        assert unescape_value("The New Dawn") == "The New Dawn"

    def test_escaped_quotes_unescaped(self):
        assert unescape_value('\\"The New Dawn\\"') == '"The New Dawn"'

    def test_empty_string(self):
        assert unescape_value("") == ""

    def test_no_quotes(self):
        assert unescape_value("Hello World") == "Hello World"

    def test_internal_escaped_quote(self):
        # e.g. He said \"hello\" → He said "hello"
        assert unescape_value('He said \\"hello\\"') == 'He said "hello"'


class TestEmitLocFile:
    def test_plain_value_escaped(self):
        entries = [("KEY:0", "The New Dawn")]
        result = emit_loc_file("l_english:", entries)
        assert ' KEY:0:0 "The New Dawn"' in result

    def test_no_double_escaping(self):
        """
        Fix #139 Bug 2: If value already contains escaped quote \\"...\\",
        emit_loc_file must NOT double-escape it to \\\\"...\\\\".
        """
        # Simulate value stored after parsing: \"The New Dawn\"
        entries = [("KEY:0", '\\"The New Dawn\\"')]
        result = emit_loc_file("l_english:", entries)
        # Expected: single-escaped quotes in output, NOT double-escaped
        assert '\\\\"' not in result, "Double-escaping detected!"
        assert '\\"The New Dawn\\"' in result

    def test_value_with_internal_quotes(self):
        # Value: He said "hello" → stored as: He said \"hello\"
        entries = [("KEY:0", 'He said "hello"')]
        result = emit_loc_file("l_english:", entries)
        assert 'He said \\"hello\\"' in result

    def test_header_preserved(self):
        entries = [("A:0", "text")]
        result = emit_loc_file("l_simp_chinese:", entries)
        assert result.startswith("l_simp_chinese:")


class TestParseQuotesBug:
    """
    Fix #139 Bug 1: Values starting with \" should NOT be skipped.
    We test via unescape_value since parse_loc_file requires a real file.
    The fix ensures raw_value is unescaped BEFORE the empty-value check.
    """
    def test_quoted_value_not_empty_after_unescape(self):
        # Simulates what ENTRY_RE captures from: KEY:0 "\"The New Dawn\""
        raw_value = '\\"The New Dawn\\"'
        value = unescape_value(raw_value)
        # After unescape, value is '"The New Dawn"' — not empty, should not be skipped
        assert value != ""
        assert value == '"The New Dawn"'

    def test_truly_empty_value_still_skipped(self):
        # Empty value (no content between quotes) should still be skipped
        raw_value = ""
        value = unescape_value(raw_value)
        assert not value  # empty → still skipped correctly

    def test_roundtrip_no_mutation(self):
        """
        Roundtrip: unescape → re-escape should produce identical output,
        not accumulate extra backslashes.
        """
        original = '\\"The New Dawn\\"'
        unescaped = unescape_value(original)
        re_escaped = unescaped.replace('"', '\\"')
        assert re_escaped == original  # must be identical after roundtrip
