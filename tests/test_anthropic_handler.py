from unittest.mock import MagicMock, patch

import pytest

from scripts.core.anthropic_handler import AnthropicHandler


@pytest.fixture
def anthropic_client():
    with (
        patch(
            "scripts.core.anthropic_handler.get_api_key",
            return_value="anthropic-test-key",
        ),
        patch("scripts.core.anthropic_handler.requests.Session") as session,
    ):
        handler = AnthropicHandler("anthropic", model_id="claude-haiku-4-5")
    return handler, session.return_value


def test_anthropic_initialization_uses_native_auth_headers():
    with (
        patch(
            "scripts.core.anthropic_handler.get_api_key",
            return_value="anthropic-test-key",
        ) as get_api_key,
        patch("scripts.core.anthropic_handler.requests.Session") as session,
    ):
        AnthropicHandler("anthropic")

    get_api_key.assert_called_once_with("anthropic", "ANTHROPIC_API_KEY")
    session.return_value.headers.update.assert_called_once_with(
        {
            "content-type": "application/json",
            "x-api-key": "anthropic-test-key",
            "anthropic-version": "2023-06-01",
        }
    )


def test_anthropic_translation_uses_messages_api(anthropic_client):
    handler, client = anthropic_client
    response = MagicMock()
    response.json.return_value = {
        "content": [
            {"type": "text", "text": "Translated "},
            {"type": "text", "text": "text"},
        ]
    }
    client.post.return_value = response

    result = handler._call_api(client, "Translate this")

    assert result == "Translated text"
    client.post.assert_called_once_with(
        "https://api.anthropic.com/v1/messages",
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 4000,
            "system": "You are a professional translator for game mods.",
            "messages": [{"role": "user", "content": "Translate this"}],
        },
        timeout=300,
    )
    response.raise_for_status.assert_called_once_with()


def test_anthropic_rejects_response_without_text(anthropic_client):
    handler, client = anthropic_client
    response = MagicMock()
    response.json.return_value = {"content": [{"type": "tool_use"}]}
    client.post.return_value = response

    with pytest.raises(
        ValueError,
        match="Anthropic API response did not contain text content",
    ):
        handler._call_api(client, "Translate this")


def test_anthropic_reports_missing_key_without_creating_session():
    with (
        patch("scripts.core.anthropic_handler.get_api_key", return_value=None),
        patch("scripts.core.anthropic_handler.requests.Session") as session,
        pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"),
    ):
        AnthropicHandler("anthropic")

    session.assert_not_called()
