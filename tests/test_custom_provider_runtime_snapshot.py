import json
from unittest.mock import Mock, patch

from scripts.core.api_handler import get_handler
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


def _snapshot(*, base_url: str, model: str) -> dict:
    return {
        "base_url": base_url,
        "default_model": model,
        "prompt_prefix": "",
        "system_prompt_suffix": "",
    }


def test_custom_handler_uses_immutable_config_and_secret_snapshot():
    first = _snapshot(base_url="https://endpoint-a.example/v1", model="model-a")
    with patch("scripts.core.yourfavourite_handler.OpenAI") as client_factory:
        client_factory.return_value = Mock()
        handler = get_handler(
            "your_favourite_api",
            provider_config_snapshot=first,
            api_key_override="secret-a",
        )

    first["base_url"] = "https://endpoint-b.example/v1"
    first["default_model"] = "model-b"

    client_factory.assert_called_once_with(
        api_key="secret-a",
        base_url="https://endpoint-a.example/v1",
    )
    assert handler.get_provider_config()["base_url"] == "https://endpoint-a.example/v1"
    assert handler.get_provider_config()["default_model"] == "model-a"


def test_custom_handler_does_not_reread_global_config_when_snapshot_exists(monkeypatch):
    with patch("scripts.core.yourfavourite_handler.OpenAI", return_value=Mock()):
        handler = get_handler(
            "your_favourite_api",
            provider_config_snapshot=_snapshot(
                base_url="https://endpoint-a.example/v1",
                model="model-a",
            ),
            api_key_override="secret-a",
        )

    monkeypatch.setattr(
        "scripts.app_settings.config_manager.get_value",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live config read")),
    )
    assert handler.get_provider_config()["default_model"] == "model-a"


def test_runtime_metadata_masks_secret_and_is_stable():
    runtime = ProviderRuntimeSnapshot(
        selection_id="custom-profile-1",
        adapter_id="your_favourite_api",
        display_name="Provider A",
        model_id="model-a",
        config={
            "base_url": "https://endpoint-a.example/v1",
            "default_model": "model-a",
            "api_key": "must-not-leak",
            "headers": {"Authorization": "also-must-not-leak"},
        },
        api_key="must-not-leak",
        secret_ref="custom-profile-1",
    )

    first = runtime.safe_metadata()
    second = runtime.safe_metadata()

    assert first == second
    assert first["config"] == {
        "base_url": "https://endpoint-a.example/v1",
        "default_model": "model-a",
        "headers": {},
    }
    assert "must-not-leak" not in repr(runtime)
    assert "must-not-leak" not in json.dumps(first)
    assert "also-must-not-leak" not in json.dumps(first)
