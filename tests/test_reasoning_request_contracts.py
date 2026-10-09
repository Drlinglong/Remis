"""Exercise resolved catalog presets through SDK serialization without network."""

import copy
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import OpenAI

from scripts.app_settings import API_PROVIDERS
from scripts.core.api_handler import OPENAI_COMPATIBLE_PROVIDER_IDS, PROVIDER_HANDLER_CLASSES
from scripts.core.anthropic_handler import AnthropicHandler
from scripts.core.chat_request_policy import prepare_chat_request, prepare_model_settings
from scripts.core.gemini_handler import GeminiHandler
from scripts.core.openai_handler import OpenAIHandler
from scripts.core.reasoning_policy import describe_reasoning_settings, resolve_reasoning_parameters
from scripts.core.copilot import agent_planner, help_agent_models
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


GPT6_EFFORTS = {
    "gpt-6-luna": ("none", "low", "medium", "high", "xhigh", "max"),
    "gpt-6-sol": ("none", "low", "medium", "high", "xhigh", "max"),
    "gpt-6.1-sol": ("low", "medium", "high", "xhigh", "max"),
    "gpt-6-astra": ("low", "medium", "high", "xhigh", "max"),
}


def make_handler(provider_id, model, preset, *, enabled=True, custom=None):
    handler_class = (
        OpenAIHandler if provider_id in OPENAI_COMPATIBLE_PROVIDER_IDS
        else PROVIDER_HANDLER_CLASSES[provider_id]
    )
    handler = handler_class.__new__(handler_class)
    handler.provider_name = provider_id
    handler.model_id = model
    handler.reasoning_override = {}
    handler.logger = logging.getLogger("reasoning-request-contract-test")
    handler._provider_config_snapshot = {
        **copy.deepcopy(API_PROVIDERS[provider_id]),
        "default_model": model,
        "reasoning_builtin_enabled": enabled,
        "reasoning_preset": preset,
        "custom_parameters": custom or {},
    }
    return handler


@pytest.mark.parametrize("model,efforts", GPT6_EFFORTS.items())
def test_gpt6_catalog_exposes_only_official_efforts(model, efforts):
    config = {**API_PROVIDERS["openai"], "default_model": model, "reasoning_preset": "high"}
    description = describe_reasoning_settings(config)
    assert model in config["available_models"]
    assert description["supported"] is True
    assert description["available_presets"] == list(efforts)
    assert description["mapping_preview"] == {"reasoning_effort": "high"}
    assert description["source_url"].endswith("/" + model)
    assert "minimal" not in efforts


WIRE_PRESETS = [
    pytest.param(provider_id, model, preset, parameters, id=f"{provider_id}/{model}/{preset}")
    for provider_id, config in API_PROVIDERS.items()
    if provider_id not in {"gemini", "anthropic"}
    for model, capability in (config.get("reasoning") or {}).get("models", {}).items()
    if isinstance(capability, dict)
    for preset, parameters in capability["presets"].items()
]


@pytest.mark.parametrize("provider_id,model,preset,parameters", WIRE_PRESETS)
def test_every_verified_chat_preset_reaches_serialized_request(provider_id, model, preset, parameters):
    captured = []

    def respond(request):
        assert request.url.path.endswith("/chat/completions")
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "offline", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}],
        })

    handler = make_handler(provider_id, model, preset)
    with OpenAI(
        api_key="offline-test-value", base_url="https://offline.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        handler.client = client
        assert handler._call_api(client, "Translate") == "done"
        if isinstance(handler, OpenAIHandler):
            assert handler.generate_with_messages([{"role": "user", "content": "Translate"}]) == "done"
    for body in captured:
        assert body["model"] == model
        for key, value in parameters.items():
            assert body[key] == value
        assert "extra_body" not in body
        if provider_id == "openai" and preset != "none":
            assert "temperature" not in body
        if provider_id == "kimi" and model == "kimi-k3":
            assert "temperature" not in body


ANTHROPIC_PRESETS = [
    (model, preset) for model, capability in API_PROVIDERS["anthropic"]["reasoning"]["models"].items()
    for preset in capability["presets"]
]


@pytest.mark.parametrize("model,preset", ANTHROPIC_PRESETS)
def test_anthropic_effort_reaches_both_request_paths(model, preset):
    handler = make_handler("anthropic", model, preset)
    handler.base_url = "https://offline.invalid/v1"
    response = MagicMock()
    response.json.return_value = {"content": [{"type": "text", "text": "done"}]}
    handler.client = MagicMock()
    handler.client.post.return_value = response
    assert handler._call_api(handler.client, "Translate") == "done"
    assert handler.generate_with_messages([{"role": "user", "content": "Translate"}]) == "done"
    for call in handler.client.post.call_args_list:
        body = call.kwargs["json"]
        assert body["model"] == model
        assert body["output_config"] == {"effort": preset}
        if model in {"claude-opus-5", "claude-sonnet-5"}:
            assert "temperature" not in body


@pytest.mark.parametrize("model,level", [("gemini-3.6-flash", "minimal"), ("gemini-3.7-flash", "low"), ("gemini-3.8-flash", "high")])
def test_gemini_messages_use_frozen_model_and_matching_thinking_config(model, level):
    handler = make_handler("gemini", model, level)
    handler.client = MagicMock()
    handler.client.models.generate_content.return_value = SimpleNamespace(text="done")
    assert handler.generate_with_messages([{"role": "user", "content": "Translate"}]) == "done"
    request = handler.client.models.generate_content.call_args.kwargs
    assert request["model"] == model
    assert request["config"].thinking_config.thinking_level.lower() == level


def test_gemini_37_no_longer_sends_unsupported_minimal():
    config = make_handler("gemini", "gemini-3.7-flash", "minimal").get_provider_config()
    resolution = resolve_reasoning_parameters(config)
    assert "minimal" not in resolution.available_presets
    assert resolution.parameters == {"thinking_config": {"thinking_level": "medium"}}


@pytest.mark.parametrize("enabled,custom,expected", [
    (True, {}, {"reasoning_effort": "high"}),
    (False, {}, {}),
    (True, {"reasoning_effort": "low", "seed": 4}, {"reasoning_effort": "low", "seed": 4}),
    (False, {"reasoning_effort": "high"}, {"reasoning_effort": "high"}),
])
def test_gpt6_builtin_toggle_and_custom_override(enabled, custom, expected):
    handler = make_handler("openai", "gpt-6-luna", "high", enabled=enabled, custom=custom)
    assert handler._reasoning_request_parameters() == expected


@pytest.mark.parametrize("model", GPT6_EFFORTS)
@pytest.mark.parametrize("effort", [None, "high", "none"])
def test_openai_sampling_constraints_apply_after_extra_body_overrides(model, effort):
    original = {
        "model": model, "temperature": 0.7, "top_p": 0.8, "logprobs": True,
        "extra_body": {"reasoning_effort": effort, "temperature": 0.1, "top_logprobs": 2, "seed": 4},
    }
    request = prepare_chat_request("openai", original)
    if effort == "none":
        assert request["temperature"] == 0.7
        assert request["extra_body"]["temperature"] == 0.1
    else:
        assert not {"temperature", "top_p", "top_logprobs", "logprobs"}.intersection(request)
        assert not {"temperature", "top_p", "top_logprobs", "logprobs"}.intersection(request["extra_body"])
    assert request["extra_body"]["seed"] == 4
    assert original["temperature"] == 0.7


@pytest.mark.parametrize("provider_id,model", [("openai", "custom-model"), ("meta", "muse-spark-1.3"), ("openrouter", "custom/model")])
def test_sampling_policy_is_scoped_to_verified_direct_models(provider_id, model):
    request = {"model": model, "temperature": 0.7, "extra_body": {"thinking": {"type": "enabled"}}}
    assert prepare_chat_request(provider_id, request) == request


def test_kimi_k3_fixed_sampling_fields_are_removed_from_sdk_and_custom_body():
    fields = {"temperature": 0.3, "top_p": 0.7, "n": 2, "presence_penalty": 1, "frequency_penalty": 1}
    request = prepare_chat_request("kimi", {"model": "kimi-k3", **fields, "extra_body": {**fields, "reasoning_effort": "high"}})
    assert request == {"model": "kimi-k3", "extra_body": {"reasoning_effort": "high"}}


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-sonnet-5", "claude-opus-4-6"])
def test_anthropic_sampling_constraints_keep_older_model_controls(model):
    fields = {"temperature": 0.3, "top_p": 0.7, "top_k": 2}
    request = prepare_chat_request("anthropic", {"model": model, **fields, "output_config": {"effort": "high"}})
    assert bool(set(fields).intersection(request)) is (model == "claude-opus-4-6")
    assert request["output_config"] == {"effort": "high"}


@pytest.mark.parametrize("model", ["openai/gpt-6-luna", "openai/gpt-6.1-sol", "openai/gpt-6-astra", "openai/gpt-6-sol"])
def test_openrouter_gpt6_routes_filter_sampling_and_keep_gateway_reasoning(model):
    handler = make_handler("openrouter", model, "high", custom={"temperature": 0.1})
    options = handler._chat_options(0.2)
    assert options["extra_body"] == {"reasoning": {"effort": "high"}}
    assert "temperature" not in options


@pytest.mark.parametrize("effort", [None, "high", "none"])
def test_pydantic_model_settings_use_the_same_effective_sampling_policy(effort):
    settings = {"temperature": 0.0, "max_tokens": 1024}
    if effort:
        settings["openai_reasoning_effort"] = effort
    prepared = prepare_model_settings("openai", "gpt-6-luna", settings)
    assert ("temperature" in prepared) is (effort == "none")
    assert prepared.get("openai_reasoning_effort") == effort
    assert "reasoning_effort" not in prepared
    assert "model" not in prepared


def runtime_snapshot(provider_id, model):
    return ProviderRuntimeSnapshot(
        selection_id=provider_id, adapter_id=provider_id, display_name=provider_id,
        model_id=model, config=copy.deepcopy(API_PROVIDERS[provider_id]),
        api_key="offline-test-value", secret_ref=None,
    )


@pytest.mark.parametrize("provider_id,model,key,value", [
    ("openai", "gpt-6.1-sol", "openai_reasoning_effort", "high"),
    ("anthropic", "claude-opus-5", "anthropic_effort", "high"),
    ("gemini", "gemini-3.8-flash", "google_thinking_config", {"thinking_level": "high"}),
    ("kimi", "kimi-k3", "openai_reasoning_effort", "high"),
])
def test_help_model_construction_retains_native_reasoning(provider_id, model, key, value):
    _, settings, selected = help_agent_models.build_help_model(
        provider_id, model, {"reasoning_builtin_enabled": True, "reasoning_preset": "high"},
        provider_runtime=runtime_snapshot(provider_id, model),
    )
    assert selected == model
    assert settings[key] == value
    if provider_id in {"openai", "kimi"}:
        assert "temperature" not in settings


@pytest.mark.parametrize("enabled,effort", [(True, "high"), (False, "high"), (True, "none")])
def test_planner_construction_filters_sampling_with_effective_reasoning(monkeypatch, enabled, effort):
    captured = {}

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def tool(self, function):
            return function

        def output_validator(self, function):
            return function

    monkeypatch.setattr(agent_planner, "Agent", FakeAgent)
    agent_planner._build_agent(
        provider="openai", model_name="gpt-6-luna", reasoning_enabled=enabled,
        reasoning_preset=effort, provider_runtime=runtime_snapshot("openai", "gpt-6-luna"),
    )
    settings = captured["model_settings"]
    assert ("temperature" in settings) is (enabled and effort == "none")
    assert settings.get("openai_reasoning_effort") == (effort if enabled else None)
