import logging
import traceback
from types import SimpleNamespace

import pytest

from scripts.core.openai_handler import OpenAIHandler
from scripts.core.provider_errors import ProviderFatalError


class _Completions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )


def _handler(model, *, reasoning_effort=None, custom_parameters=None):
    completions = _Completions()
    handler = OpenAIHandler.__new__(OpenAIHandler)
    handler.model_id = model
    handler.provider_name = "openai"
    handler.logger = logging.getLogger("openai-gpt6-parameter-test")
    handler.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    reasoning_models = {}
    if model in {"gpt-6-astra", "gpt-6-sol", "gpt-6-luna"}:
        reasoning_models[model] = {
            "presets": {
                "none": {"reasoning_effort": "none"},
                "low": {"reasoning_effort": "low"},
                "medium": {"reasoning_effort": "medium"},
                "high": {"reasoning_effort": "high"},
                "xhigh": {"reasoning_effort": "xhigh"},
                "max": {"reasoning_effort": "max"},
            }
        }
    config = {
        "default_model": model,
        "reasoning_builtin_enabled": reasoning_effort is not None,
        "reasoning_preset": reasoning_effort or "medium",
        "reasoning": {
            "default_enabled": reasoning_effort is not None,
            "default_preset": "medium",
            "models": reasoning_models,
        },
        "custom_parameters": custom_parameters or {},
    }
    handler.get_provider_config = lambda: config
    handler._record_model_response = lambda response: None
    return handler, completions


@pytest.mark.parametrize("chat", [False, True])
def test_authentication_failure_does_not_log_or_propagate_provider_body(chat, caplog):
    handler, completions = _handler("gpt-6-luna")

    class AuthenticationFailure(RuntimeError):
        status_code = 401

    def reject(**kwargs):
        raise AuthenticationFailure("Incorrect API key provided: sensitive-test-marker")

    completions.create = reject
    with pytest.raises(ProviderFatalError) as caught:
        if chat:
            handler.generate_with_messages([{"role": "user", "content": "Hello"}])
        else:
            handler._call_api(handler.client, "Hello")

    assert caught.value.reason_code == "provider_authentication_failed"
    assert caught.value.status_code == 401
    assert "sensitive-test-marker" not in str(caught.value)
    assert "sensitive-test-marker" not in "".join(traceback.format_exception(caught.value))
    assert "sensitive-test-marker" not in caplog.text


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6-sol", "gpt-6-luna"])
def test_gpt6_omits_default_temperature_for_default_reasoning(model):
    handler, completions = _handler(model)

    assert handler.generate_with_messages([{"role": "user", "content": "Hi"}]) == "ok"

    assert "temperature" not in completions.kwargs
    assert "extra_body" not in completions.kwargs


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6-sol", "gpt-6-luna"])
def test_gpt6_sends_default_temperature_only_for_explicit_none_effort(model):
    handler, completions = _handler(model, reasoning_effort="none")

    handler.generate_with_messages([{"role": "user", "content": "Hi"}])

    assert completions.kwargs["temperature"] == 0.7
    assert completions.kwargs["extra_body"] == {"reasoning_effort": "none"}


def test_gpt6_omits_caller_temperature_with_reasoning_enabled():
    handler, completions = _handler("gpt-6-luna", reasoning_effort="medium")

    handler.generate_with_messages(
        [{"role": "user", "content": "Hi"}], temperature=0.25
    )

    assert "temperature" not in completions.kwargs
    assert completions.kwargs["extra_body"] == {"reasoning_effort": "medium"}


def test_gpt6_none_effort_preserves_caller_temperature_argument():
    handler, completions = _handler("gpt-6-luna", reasoning_effort="none")

    handler.generate_with_messages(
        [{"role": "user", "content": "Hi"}], temperature=0.2
    )

    assert completions.kwargs["temperature"] == 0.2
    assert completions.kwargs["extra_body"] == {"reasoning_effort": "none"}


def test_gpt6_custom_json_temperature_is_preserved_without_system_default():
    handler, completions = _handler(
        "gpt-6-luna",
        reasoning_effort="high",
        custom_parameters={"temperature": 0.2},
    )

    handler.generate_with_messages([{"role": "user", "content": "Hi"}])

    assert "temperature" not in completions.kwargs
    assert completions.kwargs["extra_body"] == {
        "reasoning_effort": "high",
        "temperature": 0.2,
    }


def test_other_model_keeps_existing_default_temperature_behavior():
    handler, completions = _handler("gpt-5.6-luna")

    handler.generate_with_messages([{"role": "user", "content": "Hi"}])

    assert completions.kwargs["temperature"] == 0.7


def test_unknown_model_does_not_receive_builtin_reasoning_parameters():
    handler, completions = _handler("user/custom-model", reasoning_effort="high")

    handler.generate_with_messages([{"role": "user", "content": "Hi"}])

    assert completions.kwargs["temperature"] == 0.7
    assert "extra_body" not in completions.kwargs
