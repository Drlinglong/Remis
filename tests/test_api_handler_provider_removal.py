import pytest

from scripts.app_settings import API_PROVIDERS
from scripts.core import api_handler


def test_gemini_cli_provider_is_explicitly_removed():
    with pytest.raises(ValueError, match="Gemini CLI provider has been removed"):
        api_handler.get_handler("gemini_cli")


def test_hunyuan_provider_is_removed_from_catalog_and_routing():
    assert "hunyuan" not in API_PROVIDERS
    assert "hunyuan" not in api_handler.SUPPORTED_PROVIDER_IDS

    with pytest.raises(ValueError, match="Unknown API provider: hunyuan"):
        api_handler.get_handler("hunyuan")
