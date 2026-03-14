import os
import re
import pytest
from unittest.mock import patch

from scripts.workflows.initial_translate import discover_files
from scripts.app_settings import LANGUAGES

# Helper to mock update_translate.py logic
def is_valid_for_update_translate(filename: str, filter_lang_string: str) -> bool:
    file_lower = filename.lower()
    if not (file_lower.endswith('.yml') or file_lower.endswith('.yaml')):
        return False
        
    expected_suffix1 = f"l_{filter_lang_string}.yml"
    expected_suffix2 = f"l_{filter_lang_string}.yaml"
    expected_suffix3 = f" {filter_lang_string}.yml"
    expected_suffix4 = f" {filter_lang_string}.yaml"
    
    known_languages = ['english', 'french', 'german', 'spanish', 'russian', 'polish', 'braz_por', 'japanese', 'chinese', 'simp_chinese', 'korean', 'turkish']
    
    if not (file_lower.endswith(expected_suffix1) or file_lower.endswith(expected_suffix2) or file_lower.endswith(expected_suffix3) or file_lower.endswith(expected_suffix4)):
        has_other_lang = False
        for lang in known_languages:
            if lang != filter_lang_string and (f"l_{lang}" in file_lower or f" {lang}." in file_lower):
                has_other_lang = True
                break
        if has_other_lang:
            return False
            
    return True


@pytest.fixture
def mock_game_profile():
    return {
        "id": "victoria3",
        "source_localization_folder": "localization"
    }


def test_initial_translate_filename_matching(mock_game_profile):
    """
    Test that initial_translate correctly matches normal and non-standard filename patterns
    for ALL supported languages.
    """
    for lang_id, lang_info in LANGUAGES.items():
        lang_key = lang_info['key'][2:] # e.g. "english"
        
        valid_filenames = [
            f"events_l_{lang_key}.yml",
            f"events l_{lang_key}.yml",
            f"00 Bookmarks {lang_key}.yml",
            f"00_Bookmarks_{lang_key}.yml",
            f"l_{lang_key}.yml",
            f" {lang_key}.yml"
        ]
        
        invalid_filenames = [
            f"events_l_otherlang.yml",
            f" {lang_key}.txt", 
            f"eventsl{lang_key}.yml", # Missing separator space or underscore entirely
            f"events_english_l_{lang_key}_backup.yml"
        ]

        with patch('os.walk') as mock_walk:
            mock_walk.return_value = [
                (os.path.join("fake_source", "localization"), [], valid_filenames + invalid_filenames)
            ]
            
            found_files = discover_files("fake_mod", mock_game_profile, lang_info, override_path="fake_source")
            found_filenames = [f["filename"] for f in found_files]
            
            for valid_fn in valid_filenames:
                assert valid_fn in found_filenames, f"Failed to match valid file '{valid_fn}' for language {lang_key}"
                
            for invalid_fn in invalid_filenames:
                 assert invalid_fn not in found_filenames, f"Incorrectly matched invalid file '{invalid_fn}' for language {lang_key}"


def test_update_translate_filename_matching():
    """
    Test the manual filename filter loops used in update_translate.py's incremental updates.
    """
    known_languages = ['english', 'french', 'german', 'spanish', 'russian', 'polish', 'braz_por', 'japanese', 'chinese', 'simp_chinese', 'korean', 'turkish']
    
    for lang_key in known_languages:
        valid_filenames = [
            f"events_l_{lang_key}.yml",
            f"events l_{lang_key}.yaml",
            f"00 Bookmarks {lang_key}.yml",
            f"l_{lang_key}.yml"
        ]
        
        invalid_filenames = [
            f" {lang_key}.txt",
        ]

        other_lang = next(l for l in known_languages if l != lang_key)
        invalid_filenames.append(f"events_l_{other_lang}.yml")
        invalid_filenames.append(f"events l_{other_lang}.yml")
        invalid_filenames.append(f"00 Bookmarks {other_lang}.yml")
        
        for valid_fn in valid_filenames:
            assert is_valid_for_update_translate(valid_fn, lang_key) is True, f"Failed to match '{valid_fn}' for target {lang_key}"
            
        for invalid_fn in invalid_filenames:
            assert is_valid_for_update_translate(invalid_fn, lang_key) is False, f"Incorrectly matched '{invalid_fn}' for target {lang_key}"
