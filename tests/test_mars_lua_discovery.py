import hashlib

import pytest

from scripts.core.services.mars_lua_discovery import scan_lua_file, scan_lua_text


def test_scans_only_direct_calls_and_decodes_literal_forms():
    source = '''
-- Untranslated("comment")
local quoted = "Untranslated('inside')"
local a = Untranslated("line\\n\u4e2d")
local b = Untranslated([=[
long text
]=])
obj.Untranslated("qualified")
obj:Untranslated("method")
'''
    found = scan_lua_text(source, "Defs/example.lua")
    assert [item.text for item in found] == ["line\n中", "long text\n"]
    assert [item.classification for item in found] == ["literal", "literal"]
    assert all(item.manual_review for item in found)
    assert all(item.review_reason for item in found)
    assert [item.line for item in found] == [4, 5]
    assert all(item.candidate_key for item in found)
    for item in found:
        assert source[item.start_offset:item.end_offset].startswith("Untranslated(")
        assert hashlib.sha256(source[item.start_offset:item.end_offset].encode()).hexdigest() == item.call_sha256


def test_dynamic_calls_are_reported_for_manual_review_without_execution():
    source = 'local text = Untranslated(buildText("x"))\nUntranslated("a", extra)\n'
    found = scan_lua_text(source)
    assert len(found) == 2
    assert all(item.classification == "dynamic" for item in found)
    assert all(item.text is None and item.manual_review for item in found)
    assert found[0].candidate_key
    assert found[1].candidate_key is None
    assert all("expression" in item.review_reason for item in found)


def test_string_delimiters_do_not_affect_call_matching_and_lua_sugar_is_supported():
    source = '''
Untranslated("a ) and { and }")
Untranslated [=[table text: ) }]=]
Untranslated { text = "table argument" }
local nested = Untranslated([=[close ) and } chars]=])
'''
    found = scan_lua_text(source)
    assert [item.text for item in found] == ["a ) and { and }", "table text: ) }", None, "close ) and } chars"]
    assert [item.classification for item in found] == ["literal", "literal", "dynamic", "literal"]
    assert [source[item.start_offset:item.end_offset] for item in found] == [
        'Untranslated("a ) and { and }")',
        "Untranslated [=[table text: ) }]=]",
        'Untranslated { text = "table argument" }',
        "Untranslated([=[close ) and } chars]=])",
    ]


def test_malformed_lua_syntax_raises_instead_of_returning_partial_scan():
    for source in ('Untranslated("open)', 'local x = [=[unterminated', '--[=[comment', 'Untranslated("x"'):
        with pytest.raises(ValueError):
            scan_lua_text(source)


def test_candidate_cap_is_enforced_during_collection():
    source = '\n'.join('Untranslated("x")' for _ in range(25))
    with pytest.raises(ValueError, match=r"candidate limit reached \(10\)"):
        scan_lua_text(source, max_candidates=10)
    assert len(scan_lua_text(source, max_candidates=None)) == 25


def test_nested_calls_use_precomputed_delimiters_and_obey_candidate_cap():
    depth = 300
    source = 'Untranslated(' * depth + '"text"' + ')' * depth
    with pytest.raises(ValueError, match=r"candidate limit reached \(20\)"):
        scan_lua_text(source, max_candidates=20)
    found = scan_lua_text(source, max_candidates=depth)
    assert len(found) == depth
    assert sum(item.classification == "literal" for item in found) == 1


def test_function_declaration_is_not_reported_as_call():
    assert scan_lua_text('function Untranslated(value) return value end') == []


def test_escaped_utf8_bytes_decode_as_text():
    result = scan_lua_text(r'local title = Untranslated("\228\184\173")')[0]
    assert result.text == "中"


def test_z_escape_consumes_escaped_whitespace_and_unicode_digit_does_not_crash():
    source = 'local title = Untranslated("a\\z\n  b")\nlocal bad = Untranslated("x\\١")'
    found = scan_lua_text(source)
    assert found[0].text == "ab"
    assert found[1].text is None
    assert found[1].classification == "dynamic"
    assert found[1].manual_review


def test_lone_cr_ends_comments_and_advances_source_lines():
    found = scan_lua_text('-- Untranslated("comment")\rlocal title = Untranslated("text")')
    assert len(found) == 1
    assert found[0].line == 2


def test_duplicate_bindings_and_unbound_calls_have_no_candidate_key():
    found = scan_lua_text('local text = Untranslated("a")\nlocal text = Untranslated("b")\nUntranslated("c")')
    assert [item.candidate_key for item in found] == [None, None, None]
    assert all(item.manual_review for item in found)


def test_hashes_and_candidate_identity_are_deterministic_for_source_path():
    source = 'local title = Untranslated("Title")'
    first = scan_lua_text(source, "Defs/a.lua")[0]
    again = scan_lua_text(source, "Defs/a.lua")[0]
    other_path = scan_lua_text(source, "Defs/b.lua")[0]
    assert first.candidate_key == again.candidate_key
    assert first.candidate_key != other_path.candidate_key
    assert first.source_sha256 == hashlib.sha256(source.encode()).hexdigest()
    assert first.to_dict()["classification"] == "literal"


def test_scan_file_is_utf8_strict_size_limited_and_accepts_relative_identity(tmp_path):
    source = tmp_path / "input.lua"
    source.write_bytes('local title = Untranslated("你好")'.encode("utf-8"))
    found = scan_lua_file(source, source_path="Mod/Defs/input.lua")
    assert found[0].source_path == "Mod/Defs/input.lua"
    assert found[0].text == "你好"
    assert found[0].source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="byte limit"):
        scan_lua_file(source, max_bytes=4)
    source.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        scan_lua_file(source)


def test_scan_file_hash_includes_utf8_bom(tmp_path):
    source = tmp_path / "bom.lua"
    data = b'\xef\xbb\xbfUntranslated("x")'
    source.write_bytes(data)
    found = scan_lua_file(source)
    assert found[0].source_sha256 == hashlib.sha256(data).hexdigest()


def test_scan_file_rejects_symlink(tmp_path):
    source = tmp_path / "input.lua"
    source.write_text('Untranslated("x")', encoding="utf-8")
    link = tmp_path / "linked.lua"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="symlink"):
        scan_lua_file(link)
