from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.core.nvidia_handler import NvidiaHandler


def _handler():
    handler = object.__new__(NvidiaHandler)
    handler.logger = Mock()
    handler.get_provider_config = lambda: {"default_model": "test-model"}
    return handler


def _client(*, content, reasoning_content=None):
    message = SimpleNamespace(
        content=content,
        reasoning_content=reasoning_content,
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )
    completions = SimpleNamespace(create=Mock(return_value=response))
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_nvidia_requires_final_assistant_content():
    handler = _handler()
    client = _client(content=None, reasoning_content='["reasoning answer"]')

    with pytest.raises(ValueError, match="no final assistant content"):
        handler._call_api(client, "prompt")


def test_nvidia_preserves_final_content_before_structured_parse():
    handler = _handler()
    emitted = '<think>visible model text</think>\n["translation"]'

    assert handler._call_api(_client(content=emitted), "prompt") == emitted
    assert handler.last_completion_source == "assistant_content"
