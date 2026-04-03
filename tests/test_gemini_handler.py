import pytest
from unittest.mock import MagicMock, patch
import os
from scripts.core.gemini_handler import GeminiHandler

class TestGeminiHandler:

    @pytest.fixture
    def mock_genai_client(self):
        with patch("scripts.core.gemini_handler.genai.Client") as mock:
            yield mock

    @pytest.fixture
    def handler(self, mock_genai_client):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            return GeminiHandler("gemini")

    def test_initialization(self, mock_genai_client):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            handler = GeminiHandler("gemini")
            assert handler.client is not None
            mock_genai_client.assert_called_once_with(api_key="fake_key")

    def test_initialization_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY not set"):
                GeminiHandler("gemini")

    def test_call_api_correct_arguments(self, handler):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Translated Text"
        handler.client.models.generate_content.return_value = mock_response

        # Call the method
        prompt = "Test Prompt"
        result = handler._call_api(handler.client, prompt)

        # Verify result
        assert result == "Translated Text"

        # Verify generate_content was called with correct arguments
        # CRITICAL: This verifies the fix for the 'generation_config' vs 'config' issue
        call_args = handler.client.models.generate_content.call_args
        assert call_args is not None
        
        # Check keyword arguments
        kwargs = call_args.kwargs
        assert kwargs['contents'] == prompt
        assert 'config' in kwargs, "generate_content should be called with 'config' argument"
        assert 'generation_config' not in kwargs, "generate_content should NOT be called with 'generation_config' argument"

    def test_call_api_retries_without_http_options_on_older_sdk(self, handler):
        mock_response = MagicMock()
        mock_response.text = "Translated Text"

        handler.client.models.generate_content.side_effect = [
            TypeError("Models.generate_content() got an unexpected keyword argument 'http_options'"),
            mock_response,
        ]

        result = handler._call_api(handler.client, "Test Prompt")

        assert result == "Translated Text"
        assert handler.client.models.generate_content.call_count == 2

        first_call = handler.client.models.generate_content.call_args_list[0]
        second_call = handler.client.models.generate_content.call_args_list[1]

        assert first_call.kwargs["http_options"] == {"timeout": 300}
        assert "http_options" not in second_call.kwargs

    def test_generate_with_messages(self, handler):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Chat Response"
        handler.client.models.generate_content.return_value = mock_response

        messages = [
            {"role": "system", "content": "System Prompt"},
            {"role": "user", "content": "User Message"}
        ]

        # Call the method
        result = handler.generate_with_messages(messages)

        # Verify result
        assert result == "Chat Response"

        # Verify the prompt construction
        call_args = handler.client.models.generate_content.call_args
        kwargs = call_args.kwargs
        content_arg = kwargs['contents']
        
        assert "System Prompt" in content_arg
        assert "User Message" in content_arg
