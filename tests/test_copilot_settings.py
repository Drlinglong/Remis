import pytest

from scripts.core.copilot import settings
from scripts.routers import copilot as copilot_router
from scripts.schemas.copilot import CopilotChatMessage, CopilotChatRequest


@pytest.fixture
def config_store(monkeypatch):
    store = {}
    monkeypatch.setattr(settings.config_manager, "get_value", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(settings.config_manager, "set_value", lambda key, value: store.__setitem__(key, value))
    return store


def test_shared_settings_persist_without_api_keys(config_store):
    saved = settings.update_copilot_settings(
        provider="openai",
        model="gpt-5.6-luna",
        reasoning_enabled=True,
        reasoning_preset="high",
    )

    assert saved["provider"] == "openai"
    assert saved["model"] == "gpt-5.6-luna"
    assert saved["reasoning"]["effective_preset"] == "high"
    assert "api_key" not in config_store[settings.CONFIG_KEY]


def test_default_shared_settings_use_200k_context_budget(config_store):
    status = copilot_router.copilot_status()

    assert status.default_provider == "lm_studio"
    assert status.context_budget_tokens == 200000
    assert "200000" in status.context_policy


def test_unverified_reasoning_mapping_is_rejected(config_store):
    with pytest.raises(ValueError, match="no verified reasoning mapping"):
        settings.update_copilot_settings(
            provider="lm_studio",
            model="local-model",
            reasoning_enabled=True,
            reasoning_preset="medium",
        )


def test_chat_uses_server_settings_when_request_omits_model(config_store, monkeypatch):
    config_store[settings.CONFIG_KEY] = {
        "provider": "openai",
        "model": "gpt-5.6-terra",
        "reasoning_enabled": True,
        "reasoning_preset": "xhigh",
    }
    captured = {}
    monkeypatch.setattr(copilot_router, "run_copilot_chat", lambda **kwargs: captured.update(kwargs) or {
        "reply": "ok", "provider": kwargs["provider"], "model": kwargs["model"]
    })

    copilot_router.copilot_chat(CopilotChatRequest(messages=[CopilotChatMessage(content="hello")]))

    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-5.6-terra"
    assert captured["reasoning_override"]["reasoning_builtin_enabled"] is True
    assert captured["reasoning_override"]["reasoning_preset"] == "xhigh"


def test_explicit_legacy_chat_model_still_overrides_default(config_store, monkeypatch):
    captured = {}
    monkeypatch.setattr(copilot_router, "run_copilot_chat", lambda **kwargs: captured.update(kwargs) or {
        "reply": "ok", "provider": kwargs["provider"], "model": kwargs["model"]
    })

    copilot_router.copilot_chat(CopilotChatRequest(
        messages=[CopilotChatMessage(content="hello")],
        provider="ollama",
        model="qwen3:4b",
    ))

    assert captured["provider"] == "ollama"
    assert captured["model"] == "qwen3:4b"


def test_status_reports_effective_shared_settings(config_store):
    config_store[settings.CONFIG_KEY] = {
        "provider": "openai",
        "model": "gpt-5.6-luna",
        "reasoning_enabled": True,
        "reasoning_preset": "high",
    }

    status = copilot_router.copilot_status()

    assert status.default_provider == "openai"
    assert status.default_model == "gpt-5.6-luna"
    assert status.reasoning_enabled is True
    assert status.reasoning_preset == "high"
    assert status.context_budget_tokens == 200000
    assert "200000" in status.context_policy
