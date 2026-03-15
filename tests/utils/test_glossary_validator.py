import pytest
from unittest.mock import MagicMock
from scripts.utils.glossary_validator import GlossaryValidator
from scripts.core.parallel_types import BatchTask, FileTask

# --- Mocks and Fixtures ---

class MockFileTask:
    """A standalone fake object that mimics FileTask for validation tests."""
    def __init__(self, filename, source_lang_code, target_lang_code):
        self.filename = filename
        self.source_lang = {"code": source_lang_code}
        self.target_lang = {"code": target_lang_code}

@pytest.fixture
def mock_i18n(mocker):
    """Fixture to mock the i18n translation function."""
    return mocker.patch("scripts.utils.i18n.t", side_effect=lambda key, **kwargs: f"i18n:{key}")

@pytest.fixture
def validator():
    """Fixture to provide a GlossaryValidator instance."""
    return GlossaryValidator()

# --- Test Cases ---

@pytest.mark.parametrize(
    "name, source_lang, target_lang, glossary, original_texts, translated_texts, expect_warning",
    [
        # --- Scenario 1: Alphabetic Language - Exact Match ---
        (
            "alphabetic_exact_match_fail", "en", "pl",
            {"convoy": "konwój"},
            ["A convoy and a fleet."],
            ["Jakiś okręt i flota."], # "konwój" is missing
            True,
        ),
        (
            "alphabetic_exact_match_pass", "en", "pl",
            {"convoy": "konwój"},
            ["A convoy and a fleet."],
            ["Jakiś konwój i flota."], # "konwój" is present
            False,
        ),

        # --- Scenario 2: Alphabetic Language - Substring Trap ---
        (
            "alphabetic_substring_trap_pass", "en", "en",
            {"port": "port"},
            ["An important port."], # "port" is in "important", but also a whole word
            ["A significant port."], # The translation of the whole word is correct
            False, # Should not flag "important"
        ),
        (
            "alphabetic_substring_trap_fail", "en", "pl",
            {"convoy": "konwój"},
            ["The convoy is ready."],
            ["Ten konwojent jest gotowy."], # "konwojent" contains "konwój" but is not a match
            True,
        ),

        # --- Scenario 3: CJK Language - Fuzzy Match ---
        (
            "cjk_fuzzy_match_pass", "zh", "en",
            {"白子": "Shiroko"},
            ["白子和一颗纯白的子弹"],
            ["Shiroko and a pure white bullet"],
            False,
        ),
        (
            "cjk_fuzzy_match_fail", "zh", "en",
            {"白子": "Shiroko"},
            ["白子和纯白子弹"],
            ["A girl and pure white bullet"], # "Shiroko" is missing
            True,
        ),
        (
            "cjk_multiple_terms_pass", "ja", "en",
            {"先生": "Sensei", "忍者": "ninja"},
            ["先生は忍者です。"],
            ["Sensei is a ninja."],
            False
        ),
    ]
)
def test_glossary_validator(validator, mock_i18n, name, source_lang, target_lang, glossary, original_texts, translated_texts, expect_warning):
    """
    Tests the GlossaryValidator across different languages and scenarios.
    """
    # 1. Setup Mock Task
    mock_file_task = MockFileTask("test.yml", source_lang, target_lang)
    mock_batch_task = BatchTask(
        file_task=mock_file_task,
        batch_index=0,
        start_index=0,
        end_index=len(original_texts),
        texts=original_texts
    )
    mock_batch_task.translated_texts = translated_texts

    # 2. Run Validation
    warnings = validator.validate_batch(mock_batch_task, glossary)

    # 3. Assert
    if expect_warning:
        assert len(warnings) > 0, f"Test case '{name}' should have produced a warning, but did not."
    else:
        assert len(warnings) == 0, f"Test case '{name}' produced an unexpected warning: {warnings}"
