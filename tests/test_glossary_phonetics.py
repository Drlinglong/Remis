import sys
import os
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.core.glossary_manager import GlossaryManager

class TestGlossaryPhonetics:
    @pytest.fixture
    def glossary_manager(self):
        """
        Creates a GlossaryManager with a mocked database connection for testing.
        """
        gm = GlossaryManager()
        # Mock the connection to avoid using the real DB
        gm.conn = MagicMock()
        return gm

    def test_phonetic_match_chinese(self, glossary_manager):
        """
        Test that a Chinese homophone typo is detected as a phonetic match.
        """
        # Setup: Mock the in-memory glossary with a target term
        glossary_manager.in_memory_glossary = {
            'entries': [
                {
                    'entry_id': '1',
                    'translations': {'zh-CN': '格黑娜', 'en': 'Gehenna'},
                    'variants': {},
                    'abbreviations': {},
                    'raw_metadata': {}
                }
            ]
        }

        # Action: Search for a text containing a homophone typo ("格黑那")
        # "格黑那" (ge hei na) sounds like "格黑娜" (ge hei na)
        text = "这就是格黑那的作风吗？"
        results = glossary_manager.extract_relevant_terms([text], 'zh-CN', 'en')

        # Assertion
        assert len(results) > 0, "Should have found a match"
        match = results[0]
        print(f"\nFound match: {match}")
        
        assert match['translations']['zh-CN'] == '格黑娜', "Should match the correct glossary term"
        assert match['match_type'] == 'phonetic', "Match type should be 'phonetic'"
        assert match['confidence'] == 0.85, "Confidence should be 0.85"

    def test_phonetic_match_japanese(self, glossary_manager):
        """
        Test that a Japanese homophone/similar sounding word is detected.
        """
        # Setup: Mock glossary
        glossary_manager.in_memory_glossary = {
            'entries': [
                {
                    'entry_id': '2',
                    'translations': {'ja': '科学', 'en': 'Science'}, # Kagaku
                    'variants': {},
                    'abbreviations': {},
                    'raw_metadata': {}
                }
            ]
        }

        # Action: Search for text with "化学" (Kagaku) - homophone in JP
        text = "この化学はすごいですね" 
        results = glossary_manager.extract_relevant_terms([text], 'ja', 'en')

        # Assertion
        assert len(results) > 0
        match = results[0]
        print(f"\nFound match: {match}")
        
        assert match['translations']['ja'] == '科学'
        assert match['match_type'] == 'phonetic'

    def test_exact_match_priority(self, glossary_manager):
        """
        Test that exact matches are prioritized over phonetic matches.
        """
        glossary_manager.in_memory_glossary = {
            'entries': [
                {
                    'entry_id': '1',
                    'translations': {'zh-CN': '格黑娜', 'en': 'Gehenna'},
                    'variants': {},
                    'abbreviations': {},
                    'raw_metadata': {}
                }
            ]
        }

        # Text contains the CORRECT term
        text = "欢迎来到格黑娜学园"
        results = glossary_manager.extract_relevant_terms([text], 'zh-CN', 'en')

        assert len(results) > 0
        match = results[0]
        assert match['match_type'] == 'exact', "Should be an exact match"
        assert match['confidence'] == 1.0

if __name__ == "__main__":
    # Manually run tests if executed as script
    gm = GlossaryManager()
    gm.conn = MagicMock()
    
    print("Running Manual Verification...")
    
    # 1. Test Chinese
    print("\nTest 1: Chinese Homophone (格黑那 -> 格黑娜)")
    gm.in_memory_glossary = {'entries': [{'entry_id': '1', 'translations': {'zh-CN': '格黑娜', 'en': 'Gehenna'}, 'variants': {}, 'abbreviations': {}, 'raw_metadata': {}}]}
    res = gm.extract_relevant_terms(["格黑那"], 'zh-CN', 'en')
    if res and res[0]['match_type'] == 'phonetic':
        print("✅ PASS")
    else:
        print(f"❌ FAIL: {res}")

    # 2. Test Japanese
    print("\nTest 2: Japanese Homophone (化学 -> 科学)")
    gm.in_memory_glossary = {'entries': [{'entry_id': '2', 'translations': {'ja': '科学', 'en': 'Science'}, 'variants': {}, 'abbreviations': {}, 'raw_metadata': {}}]}
    res = gm.extract_relevant_terms(["化学"], 'ja', 'en')
    if res and res[0]['match_type'] == 'phonetic':
        print("✅ PASS")
    else:
        print(f"❌ FAIL: {res}")
