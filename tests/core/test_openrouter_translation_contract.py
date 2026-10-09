from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import logging

from scripts.core.base_handler import BaseApiHandler
from scripts.core.openrouter_handler import OpenRouterHandler
from scripts.core.translation_output_contract import translation_response_format


def handler_for(content):
    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler._chat_options = Mock(return_value={
        "model": "anthropic/claude-haiku-5.5",
        "extra_body": {"reasoning": {"effort": "high"}, "provider": {"only": ["anthropic"]}},
    })
    handler._record_model_response = Mock()
    completion = Mock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    ))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    return handler, client, completion


def test_openrouter_batch_requires_schema_keeps_routing_and_parser_compatibility():
    raw = '{"translations":["译文 [Root.GetName]","$VALUE$"]}'
    handler, client, completion = handler_for(raw)
    assert handler._call_batch_api(client, "translate", 2) == raw
    request = completion.call_args.kwargs
    assert request["response_format"] == translation_response_format(2)
    assert request["extra_body"] == {
        "reasoning": {"effort": "high"},
        "provider": {"only": ["anthropic"], "require_parameters": True, "allow_fallbacks": False},
    }
    assert handler._parse_response(raw, ["one", "two"], "en") == ["译文 [Root.GetName]", "$VALUE$"]


@pytest.mark.parametrize("raw", [
    '', '```json\n{"translations":["a"]}\n```', '{"translations":[]}',
    '{"translations":[1]}', '{"translations":["a"],"extra":1}', '["a"]',
])
def test_batch_contract_failure_does_not_retry_as_plain_text(raw):
    handler, client, completion = handler_for(raw)
    with pytest.raises(ValueError):
        handler._call_batch_api(client, "translate", 1)
    assert completion.call_count == 1


def test_unsupported_endpoint_is_not_downgraded():
    handler, client, completion = handler_for(None)
    completion.side_effect = RuntimeError("No endpoints support response_format")
    with pytest.raises(RuntimeError, match="No endpoints"):
        handler._call_batch_api(client, "translate", 1)
    assert completion.call_count == 1


def test_real_batch_workflow_dispatches_strict_contract(monkeypatch):
    handler, client, completion = handler_for('{"translations":["translated"]}')
    handler.client = client
    handler.logger = logging.getLogger("structured-batch-test")
    handler._build_prompt = Mock(return_value="Translate the supplied entry")
    monkeypatch.setattr("scripts.utils.rate_limiter.rate_limiter.wait", lambda: None)
    task = SimpleNamespace(
        batch_index=0, texts=["source"], file_task=SimpleNamespace(target_lang={"code": "en"}),
    )
    assert handler.translate_batch(task).translated_texts == ["translated"]
    schema = completion.call_args.kwargs["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["translations"]["minItems"] == 1


def test_other_provider_batch_hook_retains_existing_behavior():
    handler = SimpleNamespace(_call_api=Mock(return_value='["a"]'))
    assert BaseApiHandler._call_batch_api(handler, "client", "prompt", 1) == '["a"]'
    handler._call_api.assert_called_once_with("client", "prompt")


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_schema_rejects_invalid_count(count):
    with pytest.raises(ValueError):
        translation_response_format(count)
