"""Exercise schema failures through real SDK serialization, without networking."""

import json
import logging
import traceback
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
import requests
from openai import OpenAI

from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.local_handler import LocalLLMHandler
from scripts.core.openai_handler import OpenAIHandler
from scripts.core.openrouter_handler import OpenRouterHandler
from scripts.core.provider_errors import ProviderFatalError
from scripts.core.translation_output_contract import is_schema_capability_rejection


PRIVATE_MARKER = "fake-private-schema-safety-marker"
PROVIDERS = ["openai", "openrouter"]


def _handler(provider):
    cls = OpenAIHandler if provider == "openai" else OpenRouterHandler
    handler = cls.__new__(cls)
    handler.provider_name = provider
    handler.model_id = "gpt-6-luna" if provider == "openai" else "openai/gpt-6-luna"
    handler.logger = logging.getLogger(f"schema-safety-{provider}")
    handler.get_provider_config = lambda: {"default_model": handler.model_id}
    handler._reasoning_request_parameters = lambda: {}
    handler._build_prompt = lambda task: "Translate one value"
    return handler


def _task():
    return SimpleNamespace(
        batch_index=0, start_index=0, texts=["source"], warnings=[],
        file_task=SimpleNamespace(target_lang={"code": "json"}, game_profile={}),
    )


@contextmanager
def _offline_client(statuses, captured):
    statuses = iter(statuses)

    def respond(request):
        captured.append(json.loads(request.content))
        status = next(statuses)
        if status != 200:
            return httpx.Response(status, json={"error": {
                "type": "invalid_api_key" if status == 401 else "upstream_failure",
                "message": "response_format unavailable: " + PRIVATE_MARKER,
            }})
        return httpx.Response(200, json={
            "id": "offline", "object": "chat.completion", "created": 0,
            "model": captured[-1]["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": '{"translations":["translated"]}',
            }}],
        })

    with OpenAI(
        api_key="offline-test-value", base_url="https://offline.invalid/v1",
        max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        yield client


def _assert_safe_exception(error):
    assert PRIVATE_MARKER not in str(error)
    assert PRIVATE_MARKER not in "".join(traceback.format_exception(error))
    assert error.__cause__ is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_direct_schema_authentication_error_is_safe(provider, caplog):
    handler = _handler(provider)
    captured = []
    with _offline_client([401], captured) as client:
        with pytest.raises(ProviderFatalError) as raised:
            handler._call_batch_api(client, "Translate", 1)
    _assert_safe_exception(raised.value)
    assert raised.value.reason_code == "provider_authentication_failed"
    assert raised.value.status_code == 401
    assert PRIVATE_MARKER not in caplog.text
    assert len(captured) == 1
    assert "response_format" in captured[0]
    assert not getattr(handler, "_batch_schema_rejected", False)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_translation_authentication_failure_keeps_logs_and_ledger_safe(
    provider, monkeypatch, caplog,
):
    handler, task, captured = _handler(provider), _task(), []
    monkeypatch.setattr("scripts.utils.rate_limiter.rate_limiter.wait", lambda: None)
    with _offline_client([401], captured) as client:
        handler.client = client
        with pytest.raises(ProviderFatalError) as raised:
            handler.translate_batch(task)
    _assert_safe_exception(raised.value)
    assert len(captured) == 1
    assert PRIVATE_MARKER not in caplog.text
    assert PRIVATE_MARKER not in json.dumps(task.warnings)
    assert len(task.warnings) == 1
    assert task.warnings[0]["type"] == "provider_fatal"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_translation_fixer_direct_schema_call_logs_safe_failure(provider, caplog):
    handler, task, captured = _handler(provider), _task(), []
    fixer = TranslationFixerAgent(handler)
    fixer._build_fix_prompt = lambda *args: "Repair one value"
    warning = SimpleNamespace(level="error", line_number=1)
    with _offline_client([401], captured) as client:
        handler.client = client
        result = fixer.attempt_fix(task, ["broken"], [warning], max_retries=1)
    assert result == (False, ["broken"])
    assert len(captured) == 1
    assert PRIVATE_MARKER not in caplog.text
    assert "Provider authentication failed" in caplog.text


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("status", [429, 500, 502])
def test_retryable_schema_errors_retain_status_without_downgrade(provider, status):
    handler, captured = _handler(provider), []
    with _offline_client([status], captured) as client:
        with pytest.raises(Exception) as raised:
            handler._call_batch_api(client, "Translate", 1)
    _assert_safe_exception(raised.value)
    assert not isinstance(raised.value, ProviderFatalError)
    assert raised.value.status_code == status
    assert not is_schema_capability_rejection(raised.value)
    assert not getattr(handler, "_batch_schema_rejected", False)
    assert len(captured) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("status,expected_delay", [(429, 30), (500, 2)])
def test_schema_retry_keeps_backoff_category_and_safe_warning(
    provider, status, expected_delay, monkeypatch, caplog,
):
    handler, task, captured, sleeps = _handler(provider), _task(), [], []
    monkeypatch.setattr("scripts.core.base_handler.MAX_RETRIES", 2)
    monkeypatch.setattr("scripts.core.base_handler.time.sleep", sleeps.append)
    monkeypatch.setattr("scripts.utils.rate_limiter.rate_limiter.wait", lambda: None)
    with _offline_client([status, 200], captured) as client:
        handler.client = client
        assert handler.translate_batch(task) is task
    assert task.translated_texts == ["translated"]
    assert sleeps == [expected_delay]
    assert len(captured) == 2
    assert all("response_format" in body for body in captured)
    assert not getattr(handler, "_batch_schema_rejected", False)
    assert PRIVATE_MARKER not in caplog.text
    assert PRIVATE_MARKER not in json.dumps(task.warnings)


@pytest.mark.parametrize("status", [429, 500])
def test_prompt_fallback_upstream_failure_is_also_safe(status, caplog):
    handler, captured = _handler("openai"), []
    with _offline_client([400, status], captured) as client:
        with pytest.raises(Exception) as raised:
            handler._call_batch_api(client, "Translate", 1)
    _assert_safe_exception(raised.value)
    assert raised.value.status_code == status
    assert PRIVATE_MARKER not in caplog.text
    assert ["response_format" in body for body in captured] == [True, False]


def test_ollama_explicit_format_rejection_falls_back_and_is_remembered(monkeypatch, caplog):
    handler = LocalLLMHandler.__new__(LocalLLMHandler)
    handler.provider_name, handler.protocol = "ollama", "ollama"
    handler.logger = logging.getLogger("schema-safety-ollama")
    handler.base_url = "https://offline.invalid"
    handler.get_provider_config = lambda: {"default_model": "offline-model"}
    handler._reasoning_request_parameters = lambda: {}
    captured = []

    def post(url, *, json, timeout):
        captured.append(json)
        response = requests.Response()
        response.url = url
        if len(captured) == 1:
            response.status_code = 400
            response._content = (
                '{"error":"json: cannot unmarshal object into Go struct field '
                'GenerateRequest.format of type string; ' + PRIVATE_MARKER + '"}'
            ).encode("utf-8")
        else:
            response.status_code = 200
            response._content = b'{"response":"[\\"fallback\\"]"}'
        return response

    monkeypatch.setattr("scripts.core.local_handler.requests.post", post)
    assert handler._call_batch_api(None, "Translate", 1) == '["fallback"]'
    assert handler._call_batch_api(None, "Translate again", 1) == '["fallback"]'
    assert ["format" in payload for payload in captured] == [True, False, False]
    assert handler._batch_schema_rejected is True
    assert PRIVATE_MARKER not in caplog.text


def test_openrouter_invalid_outer_json_still_retries_once(caplog):
    handler, captured = _handler("openrouter"), []

    def respond(request):
        captured.append(json.loads(request.content))
        if len(captured) == 1:
            return httpx.Response(200, content=("invalid JSON " + PRIVATE_MARKER).encode(),
                                  headers={"content-type": "application/json"})
        return httpx.Response(200, json={
            "id": "offline", "object": "chat.completion", "created": 0,
            "model": handler.model_id,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": '{"text":"done"}',
            }}],
        })

    with OpenAI(api_key="offline-test-value", base_url="https://offline.invalid/v1",
                max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
        handler.client = client
        result = handler.generate_structured_with_messages(
            [{"role": "user", "content": "Translate"}],
            schema={"type": "object", "properties": {"text": {"type": "string"}}},
            schema_name="offline_translation",
        )
    assert result == '{"text":"done"}'
    assert len(captured) == 2
    assert PRIVATE_MARKER not in caplog.text
