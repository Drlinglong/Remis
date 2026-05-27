import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts.core.local_handler import LocalLLMHandler


def test_validate_openai_base_url_accepts_base_url():
    assert (
        LocalLLMHandler._validate_openai_base_url("http://localhost:1234/v1")
        == "http://localhost:1234/v1"
    )


def test_validate_openai_base_url_rejects_responses_endpoint():
    with pytest.raises(ValueError, match="Base URL"):
        LocalLLMHandler._validate_openai_base_url("http://localhost:1234/v1/responses")


def test_validate_openai_base_url_rejects_chat_completions_endpoint():
    with pytest.raises(ValueError, match="Base URL"):
        LocalLLMHandler._validate_openai_base_url("http://localhost:1234/v1/chat/completions")


def test_validate_openai_base_url_rejects_host_without_scheme():
    with pytest.raises(ValueError, match="full base URL"):
        LocalLLMHandler._validate_openai_base_url("localhost:1234")


def test_initialize_client_uses_validated_local_base_url():
    with patch.object(
        LocalLLMHandler,
        "get_provider_config",
        return_value={
            "base_url": "http://localhost:1234/v1",
            "api_key": "local-no-key-required",
            "default_model": "hy-mt2-7b",
        },
    ), patch("scripts.core.local_handler.OpenAI") as mock_openai:
        LocalLLMHandler("lm_studio")

    mock_openai.assert_called_once_with(
        api_key="local-no-key-required",
        base_url="http://localhost:1234/v1",
    )


def test_initialize_client_rejects_endpoint_url():
    with patch.object(
        LocalLLMHandler,
        "get_provider_config",
        return_value={
            "base_url": "http://localhost:1234/v1/responses",
            "api_key": "local-no-key-required",
            "default_model": "hy-mt2-7b",
        },
    ), patch("scripts.core.local_handler.OpenAI") as mock_openai:
        with pytest.raises(ValueError, match="not a concrete endpoint"):
            LocalLLMHandler("lm_studio")

    mock_openai.assert_not_called()


def test_openai_compatible_call_rejects_non_chat_response():
    handler = object.__new__(LocalLLMHandler)
    handler.base_url = "http://localhost:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.get_provider_config = lambda: {"default_model": "hy-mt2-7b"}

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=None)

    with pytest.raises(ValueError, match="returned no chat choices"):
        handler._call_openai_compatible(client, "translate this")
