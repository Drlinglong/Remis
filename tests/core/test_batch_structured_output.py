"""Native JSON Schema batch output for providers beyond OpenRouter."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from scripts.core.anthropic_handler import AnthropicHandler
from scripts.core.gemini_handler import GeminiHandler
from scripts.core.local_handler import LocalLLMHandler
from scripts.core.openai_handler import OpenAIHandler
from scripts.core.provider_structured_output import batch_translation_output_mode
from scripts.core.translation_output_contract import (
    TranslationContractError,
    is_schema_capability_rejection,
    translation_batch_schema,
    translation_response_format,
)

ENVELOPE = '{"translations":["他说\\"你好\\"","$VAL$\\\\n[GetName]"]}'


def _bare(cls, provider, config=None):
    handler = cls.__new__(cls)
    handler.provider_name = provider
    handler.model_id = None
    handler.logger = logging.getLogger(f"batch-schema-{provider}")
    handler._record_model_response = Mock()
    handler.get_provider_config = Mock(return_value=config or {"default_model": "model-x"})
    handler._reasoning_request_parameters = Mock(return_value={})
    return handler


def _chat_client(*contents):
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, reasoning_content=None, tool_calls=None),
            finish_reason="stop",
        )])
        for content in contents
    ]
    create = Mock(side_effect=responses)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), create


class _BadRequest(Exception):
    status_code = 400


@pytest.mark.parametrize("provider, mode", [
    ("openrouter", "strict_json_schema"),
    ("openai", "json_schema_with_capability_fallback"),
    ("gemini", "json_schema_with_capability_fallback"),
    ("anthropic", "json_schema_with_capability_fallback"),
    ("lm_studio", "json_schema_with_capability_fallback"),
    ("vllm", "json_schema_with_capability_fallback"),
    ("ollama", "json_schema_with_capability_fallback"),
    ("deepseek", "prompt_json_with_local_validation"),
    ("kimi", "prompt_json_with_local_validation"),
    ("koboldcpp", "prompt_json_with_local_validation"),
])
def test_batch_output_mode_is_explicit_per_provider(provider, mode):
    assert batch_translation_output_mode(provider) == mode


def test_openai_batch_requests_strict_schema_and_returns_valid_envelope():
    handler = _bare(OpenAIHandler, "openai")
    client, create = _chat_client(ENVELOPE)

    assert handler._call_batch_api(client, "translate", 2) == ENVELOPE
    request = create.call_args.kwargs
    assert request["response_format"] == translation_response_format(2)
    assert request["messages"][0]["content"].startswith("You are a professional translator")
    assert handler._parse_response(ENVELOPE, ["a", "b"], "zh-CN") == ["他说“你好”", "$VAL$\\n[GetName]"]


def test_openai_compatible_provider_without_schema_support_stays_prompt_only():
    handler = _bare(OpenAIHandler, "kimi")
    client, create = _chat_client('["a"]')

    assert handler._call_batch_api(client, "translate", 1) == '["a"]'
    assert "response_format" not in create.call_args.kwargs


def test_contract_violation_raises_without_downgrading():
    handler = _bare(OpenAIHandler, "openai")
    client, create = _chat_client('{"translations":["a"],"extra":1}')

    with pytest.raises(TranslationContractError):
        handler._call_batch_api(client, "translate", 1)
    assert create.call_count == 1
    assert not getattr(handler, "_batch_schema_rejected", False)


def test_capability_rejection_falls_back_once_and_is_remembered():
    handler = _bare(OpenAIHandler, "openai")
    client, create = _chat_client('["fallback"]', '["again"]')
    create.side_effect = [
        _BadRequest("Invalid parameter: 'response_format' of type 'json_schema' is not supported"),
        *create.side_effect,
    ]

    assert handler._call_batch_api(client, "translate", 1) == '["fallback"]'
    assert handler._call_batch_api(client, "translate", 1) == '["again"]'
    assert [("response_format" in call.kwargs) for call in create.call_args_list] == [True, False, False]


@pytest.mark.parametrize("error", [
    _BadRequest("context length exceeded"),
    type("RateLimit", (Exception,), {"status_code": 429})("response_format rate limited"),
    TranslationContractError("schema mismatch"),
    json.JSONDecodeError("Expecting value", "", 0),
    RuntimeError("json_schema backend crashed"),
])
def test_other_failures_are_not_capability_rejections(error):
    assert not is_schema_capability_rejection(error)


def test_gemini_batch_uses_native_json_schema_config():
    handler = _bare(GeminiHandler, "gemini")
    part = SimpleNamespace(text=ENVELOPE)
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))], text=ENVELOPE)
    handler._generate_content = Mock(return_value=response)

    assert handler._call_batch_api(object(), "translate", 2) == ENVELOPE
    config = handler._generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == translation_batch_schema(2)
    assert "translations array" in config.system_instruction


@pytest.fixture
def anthropic_handler():
    with (
        patch("scripts.core.anthropic_handler.get_api_key", return_value="test-key"),
        patch("scripts.core.anthropic_handler.requests.Session") as session,
    ):
        handler = AnthropicHandler("anthropic", model_id="claude-sonnet-5-5")
    return handler, session.return_value


def test_anthropic_batch_uses_output_config_format_and_merges_effort(anthropic_handler):
    handler, client = anthropic_handler
    handler._reasoning_request_parameters = Mock(return_value={"output_config": {"effort": "low"}})
    response = MagicMock()
    response.json.return_value = {"content": [{"type": "text", "text": ENVELOPE}]}
    client.post.return_value = response

    assert handler._call_batch_api(client, "translate", 2) == ENVELOPE
    payload = client.post.call_args.kwargs["json"]
    assert payload["output_config"]["effort"] == "low"
    output_format = payload["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    array_schema = output_format["schema"]["properties"]["translations"]
    assert "minItems" not in array_schema and "maxItems" not in array_schema
    assert output_format["schema"]["additionalProperties"] is False


def test_anthropic_schema_rejection_keeps_error_detail_and_falls_back(anthropic_handler):
    handler, client = anthropic_handler
    rejected = requests.Response()
    rejected.status_code = 400
    rejected._content = b'{"error":{"type":"invalid_request_error","message":"output_config.format: model does not support structured outputs"}}'
    ok = MagicMock()
    ok.json.return_value = {"content": [{"type": "text", "text": '["x"]'}]}
    client.post.side_effect = [rejected, ok]

    assert handler._call_batch_api(client, "translate", 1) == '["x"]'
    assert "output_config" not in client.post.call_args_list[1].kwargs["json"]


def test_lm_studio_batch_sends_response_format():
    handler = _bare(LocalLLMHandler, "lm_studio")
    handler.protocol = "openai"
    handler.base_url = "http://localhost:1234/v1"
    handler._apply_reasoning_to_openai_kwargs = lambda kwargs: kwargs
    client, create = _chat_client(ENVELOPE)

    assert handler._call_batch_api(client, "translate", 2) == ENVELOPE
    assert create.call_args.kwargs["response_format"] == translation_response_format(2)


def test_ollama_batch_sends_native_format_schema(monkeypatch):
    handler = _bare(LocalLLMHandler, "ollama")
    handler.protocol = "ollama"
    handler.base_url = "http://localhost:11434"
    response = MagicMock(status_code=200)
    response.json.return_value = {"response": ENVELOPE}
    post = Mock(return_value=response)
    monkeypatch.setattr("scripts.core.local_handler.requests.post", post)

    assert handler._call_batch_api(None, "rules\n--- INPUT LIST ---\n1. \"a\"", 2) == ENVELOPE
    payload = post.call_args.kwargs["json"]
    assert payload["format"] == translation_batch_schema(2)
    assert "translations array" in payload["system"]


def test_koboldcpp_stays_prompt_only():
    handler = _bare(LocalLLMHandler, "koboldcpp")
    handler.protocol = "openai"
    handler.base_url = "http://localhost:5001/v1"
    handler._apply_reasoning_to_openai_kwargs = lambda kwargs: kwargs
    client, create = _chat_client('["a"]')

    assert handler._call_batch_api(client, "translate", 1) == '["a"]'
    assert "response_format" not in create.call_args.kwargs
