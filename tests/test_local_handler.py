import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import httpx
from openai import APIConnectionError

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


def test_openai_compatible_call_reports_reasoning_only_length_response():
    handler = object.__new__(LocalLLMHandler)
    handler.base_url = "http://localhost:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.get_provider_config = lambda: {"default_model": "gemma4"}

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(
                    content="",
                    reasoning_content="draft translation thoughts",
                    tool_calls=[],
                ),
            )
        ]
    )

    with pytest.raises(ValueError, match="reasoning-only output and hit the context/output limit"):
        handler._call_openai_compatible(client, "translate this")


def test_openai_compatible_call_reports_tool_call_response():
    handler = object.__new__(LocalLLMHandler)
    handler.base_url = "http://localhost:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.get_provider_config = lambda: {"default_model": "gemma4"}

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content="",
                    reasoning_content="",
                    tool_calls=[{"name": "some_tool"}],
                ),
            )
        ]
    )

    with pytest.raises(ValueError, match="returned tool calls instead of translation text"):
        handler._call_openai_compatible(client, "translate this")


def test_provider_prompt_prefix_is_prepended_once():
    handler = object.__new__(LocalLLMHandler)
    handler.model_id = None
    handler.get_provider_config = lambda: {
        "default_model": "qwen3.6",
        "prompt_prefix": "/no_think",
    }

    assert handler._apply_model_prompt_adapter("Translate this") == "/no_think\nTranslate this"
    assert handler._apply_model_prompt_adapter("/no_think\nTranslate this") == "/no_think\nTranslate this"


def test_openai_compatible_call_appends_system_prompt_suffix():
    handler = object.__new__(LocalLLMHandler)
    handler.base_url = "http://localhost:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.get_provider_config = lambda: {
        "default_model": "gemma4",
        "system_prompt_suffix": "/no_think",
    }

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"translations":["ok"]}'))]
    )

    assert handler._call_openai_compatible(client, "translate this") == '{"translations":["ok"]}'
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["content"] == (
        "You are a professional translator for game mods. /no_think"
    )
    assert messages[1]["content"] == "translate this"


def test_generate_with_messages_preserves_assistant_history_for_repairs():
    handler = object.__new__(LocalLLMHandler)
    handler.provider_name = "lm_studio"
    handler.protocol = "openai"
    handler.base_url = "http://localhost:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.model_id = "local-model"
    handler.get_provider_config = lambda: {"default_model": "local-model"}
    handler.client = MagicMock()
    handler.client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='[]'))]
    )
    messages = [
        {"role": "system", "content": "Return JSON."},
        {"role": "user", "content": "Input text"},
        {"role": "assistant", "content": '[{"category":"character"}]'},
        {"role": "user", "content": "Repair it"},
    ]

    assert handler.generate_with_messages(messages, temperature=0.1) == "[]"

    call = handler.client.chat.completions.create.call_args.kwargs
    assert call["messages"] == messages
    assert call["temperature"] == 0.1


def test_openai_compatible_call_reports_provider_and_url_on_connection_failure():
    handler = object.__new__(LocalLLMHandler)
    handler.provider_name = "lm_studio"
    handler.base_url = "http://127.0.0.1:1234/v1"
    handler.logger = logging.getLogger("test_local_handler")
    handler.get_provider_config = lambda: {"default_model": "local-model"}

    client = MagicMock()
    client.chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", "http://127.0.0.1:1234/v1/chat/completions")
    )

    with pytest.raises(ConnectionError) as exc_info:
        handler._call_openai_compatible(client, "translate this")

    message = str(exc_info.value)
    assert "LM Studio" in message
    assert "http://127.0.0.1:1234/v1" in message
    assert "请检查本地服务是否已启动，并确认端口设置正确" in message
