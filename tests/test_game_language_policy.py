import pytest

from scripts.app_settings import LANGUAGES
from scripts.core.services.game_language_policy import (
    supported_language_codes,
    validate_target_language_codes,
)


EXPECTED_MARS_CODES = ["zh-CN", "en", "fr", "de", "es", "pl", "pt-BR", "ru", "tr"]


def test_surviving_mars_has_exact_nine_catalog_languages():
    actual = supported_language_codes("surviving_mars")
    assert len(actual) == 9
    assert set(actual) == set(EXPECTED_MARS_CODES)


def test_mars_rejects_removed_languages_but_other_games_keep_global_catalog():
    for code in EXPECTED_MARS_CODES:
        validate_target_language_codes("surviving_mars", [code])

    with pytest.raises(ValueError, match="Unsupported Surviving Mars"):
        validate_target_language_codes("surviving_mars", ["ja"])

    # Victoria 3 keeps its own broader catalog; the Mars rule is scoped by game.
    validate_target_language_codes("victoria3", ["ja"])
    assert "ja" in {entry["code"] for entry in LANGUAGES.values()}
