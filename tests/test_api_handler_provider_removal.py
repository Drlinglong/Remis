import pytest

from scripts.core import api_handler


def test_gemini_cli_provider_is_explicitly_removed():
    with pytest.raises(ValueError, match="Gemini CLI provider has been removed"):
        api_handler.get_handler("gemini_cli")
