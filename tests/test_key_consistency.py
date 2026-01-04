import pytest
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.core.loc_parser import parse_loc_file
from scripts.utils.quote_extractor import QuoteExtractor

def test_key_extraction_consistency():
    # Test different Paradox localization formats
    test_cases = [
        ('  key:0 "Text"', "key:0"),
        ('  key: "Text"', "key"),
        ('  key : 0 "Text"', "key:0"),
        ('  key : "Text"', "key"),
        ('key :99 "Text" # Comment', "key:99"),
        ('l_english:', None), # Header should be skipped
        ('  # Comment line', None),
        ('  key.with.dots : "Text"', "key.with.dots"),
        ('  key_with_underscores : 0 "Text"', "key_with_underscores:0"),
    ]

    for line_content, expected_key in test_cases:
        # 1. Test logic mirroring loc_parser and QuoteExtractor
        from scripts.core.loc_parser import ENTRY_RE
        stripped = line_content.strip()
        match = ENTRY_RE.match(stripped)
        
        if expected_key is None:
            assert match is None
            continue
            
        assert match is not None
        base_key, version, _ = match.groups()
        full_key = f"{base_key.strip()}:{version.strip()}" if version.strip() else base_key.strip()
        
        assert full_key == expected_key

def test_loc_parser_regex():
    from scripts.core.loc_parser import ENTRY_RE
    
    match = ENTRY_RE.search('  key:0 "Text"')
    assert match.group(1) == "key"
    assert match.group(2) == "0"
    
    match = ENTRY_RE.search('  key: "Text"')
    assert match.group(1) == "key"
    assert match.group(2) == ""

    match = ENTRY_RE.search('  key_block:55 "Text"')
    assert match.group(1).strip() == "key_block"
    assert match.group(2).strip() == "55"

    match = ENTRY_RE.search('  spaced_key : 77 "Text"')
    assert match.group(1).strip() == "spaced_key"
    assert match.group(2).strip() == "77"

    match = ENTRY_RE.search('  only_colon_space : "Text"')
    assert match.group(1).strip() == "only_colon_space"
    assert match.group(2).strip() == ""
