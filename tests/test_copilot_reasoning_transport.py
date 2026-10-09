"""Verify Help Copilot reasoning survives native model/SDK serialization."""

import copy
import json

import httpx2 as httpx
import pytest
from pydantic_ai import Agent

from scripts.app_settings import API_PROVIDERS
from scripts.core.copilot import help_agent_models
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


@pytest.mark.parametrize("provider_id,model,provider_class", [
    ("openai", "gpt-6.1-sol", "OpenAIProvider"),
    ("openrouter", "openai/gpt-6-luna", "OpenRouterProvider"),
    ("anthropic", "claude-opus-5", "AnthropicProvider"),
    ("anthropic", "claude-sonnet-5", "AnthropicProvider"),
    ("gemini", "gemini-3.8-flash", "GoogleProvider"),
])
@pytest.mark.asyncio
async def test_help_copilot_high_effort_reaches_native_request(monkeypatch, provider_id, model, provider_class):
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        if provider_id == "openai":
            payload = {
                "id": "resp_offline", "object": "response", "created_at": 0,
                "model": model, "status": "completed",
                "output": [{"type": "message", "id": "msg_offline", "role": "assistant",
                            "status": "completed", "content": [{"type": "output_text", "text": "done", "annotations": []}]}],
            }
        elif provider_id == "openrouter":
            payload = {
                "id": "offline", "object": "chat.completion", "created": 0, "model": model, "provider": "OpenAI",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}],
            }
        elif provider_id == "anthropic":
            payload = {
                "id": "msg_offline", "type": "message", "role": "assistant", "model": model,
                "content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        else:
            payload = {"candidates": [{"content": {"role": "model", "parts": [{"text": "done"}]}, "finishReason": "STOP"}]}
        return httpx.Response(200, json=payload)

    original_provider = getattr(help_agent_models, provider_class)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        def offline_provider(**kwargs):
            return original_provider(http_client=client, **kwargs)

        monkeypatch.setattr(help_agent_models, provider_class, offline_provider)
        runtime = ProviderRuntimeSnapshot(
            selection_id=provider_id, adapter_id=provider_id, display_name=provider_id,
            model_id=model, config=copy.deepcopy(API_PROVIDERS[provider_id]),
            api_key="offline-test-value", secret_ref=None,
        )
        native_model, settings, _ = help_agent_models.build_help_model(
            provider_id, model, {"reasoning_builtin_enabled": True, "reasoning_preset": "high"},
            provider_runtime=runtime,
        )
        result = await Agent(native_model, model_settings=settings).run("Translate")
        assert result.output == "done"

    assert len(captured) == 1
    body = captured[0]
    if provider_id in {"openai", "openrouter"}:
        assert body["reasoning"]["effort"] == "high"
        assert "temperature" not in body
    elif provider_id == "anthropic":
        assert body["output_config"]["effort"] == "high"
        assert "temperature" not in body
    else:
        # The Google SDK emits the protobuf field name and uppercase enum.
        thinking = body["generationConfig"]["thinkingConfig"]
        assert thinking.get("thinking_level", thinking.get("thinkingLevel", "")).lower() == "high"
