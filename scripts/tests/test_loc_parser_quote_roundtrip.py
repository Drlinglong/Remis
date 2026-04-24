import os
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.core.loc_parser import emit_loc_file, parse_loc_file


@pytest.mark.xfail(
    strict=True,
    reason="Potential issue: emit_loc_file currently adds an extra escape to literal backslashes before escaped quotes.",
)
def test_roundtrip_preserves_literal_backslash_before_escaped_quote(tmp_path):
    source = tmp_path / "quote_roundtrip.yml"
    original_value = r'regex \\"quoted\\"'
    source.write_text(
        f'l_english:\n TEST_KEY:0 "{original_value}"\n',
        encoding="utf-8-sig",
    )

    parsed_entries = parse_loc_file(Path(source))
    assert parsed_entries == [("TEST_KEY:0", original_value)]

    emitted = emit_loc_file("l_english:", parsed_entries)
    emitted_line = emitted.splitlines()[1]
    assert emitted_line == f' TEST_KEY:0:0 "{original_value}"'
