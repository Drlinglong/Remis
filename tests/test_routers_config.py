"""
集成测试：config 路由 /api/api-keys。
测试保存 API Key 的完整路径，防止因 ConfigManager 接口变更而产生回归。
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from scripts.web_server import app


MOCK_API_PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "api_key_env": "GOOGLE_API_KEY",
        "available_models": ["gemini-1.5-pro"],
        "default_model": "gemini-1.5-pro",
        "reasoning": {
            "default_enabled": False,
            "default_preset": "medium",
            "models": {
                "gemini-1.5-pro": {
                    "presets": {
                        "low": {"thinking_config": {"thinking_level": "low"}},
                        "medium": {"thinking_config": {"thinking_level": "medium"}},
                    }
                }
            },
        },
    },
    "lm_studio": {
        "name": "LM Studio",
        "available_models": ["local-model"],
        "default_model": "local-model",
        "base_url": "http://localhost:1234/v1",
    },
    "keyless_provider": {
        "name": "Local Ollama",
        # 无 api_key_env 表示不需要 Key
        "available_models": ["llama3"],
        "default_model": "llama3",
    }
}


@pytest.fixture
def mock_config_env():
    """Mock 掉 config 路由依赖的 config_manager 和 API_PROVIDERS。"""
    mock_cm = MagicMock()
    mock_cm.get_value.return_value = {}

    with patch("scripts.routers.config.API_PROVIDERS", MOCK_API_PROVIDERS), \
         patch("scripts.routers.config.config_manager", mock_cm):
        yield mock_cm


class TestPostApiKeys:
    """回归测试：POST /api/api-keys"""

    def test_save_valid_api_key(self, mock_config_env):
        """正常保存 API Key 时，应返回 200 且调用 update_nested_value。"""
        client = TestClient(app)
        response = client.post("/api/api-keys", json={
            "provider_id": "gemini",
            "api_key": "AIza_test_key_12345"
        })
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # 核心断言：确保 update_nested_value 被正确调用
        mock_config_env.update_nested_value.assert_called_once_with(
            "api_keys", "gemini", "AIza_test_key_12345"
        )

    def test_invalid_provider_returns_400(self, mock_config_env):
        """无效的 provider_id 应返回 400。"""
        client = TestClient(app)
        response = client.post("/api/api-keys", json={
            "provider_id": "nonexistent_provider",
            "api_key": "some_key"
        })
        assert response.status_code == 400

    def test_keyless_provider_returns_400(self, mock_config_env):
        """向不需要 API Key 的 provider 发送保存请求，应返回 400。"""
        client = TestClient(app)
        response = client.post("/api/api-keys", json={
            "provider_id": "keyless_provider",
            "api_key": "should_not_be_saved"
        })
        assert response.status_code == 400
        # 确保没有写入任何数据
        mock_config_env.update_nested_value.assert_not_called()

    def test_config_manager_failure_returns_500(self, mock_config_env):
        """当 ConfigManager 写入失败时，应返回 500 而不是崩溃。"""
        mock_config_env.update_nested_value.side_effect = IOError("Disk full")

        client = TestClient(app)
        response = client.post("/api/api-keys", json={
            "provider_id": "gemini",
            "api_key": "AIza_test_key"
        })
        assert response.status_code == 500


class TestPostProviderConfig:
    """回归测试：POST /api/providers/config"""

    def test_rejects_local_openai_endpoint_url(self, mock_config_env):
        client = TestClient(app)
        response = client.post("/api/providers/config", json={
            "provider_id": "lm_studio",
            "api_url": "http://localhost:1234/v1/responses",
            "models": [],
            "selected_model": "local-model"
        })

        assert response.status_code == 400
        assert "Base URL" in response.json()["detail"]
        mock_config_env.set_value.assert_not_called()

    def test_accepts_local_openai_base_url(self, mock_config_env):
        client = TestClient(app)
        response = client.post("/api/providers/config", json={
            "provider_id": "lm_studio",
            "api_url": "http://localhost:1234/v1",
            "models": [],
            "selected_model": "local-model",
            "prompt_prefix": "/no_think",
            "system_prompt_suffix": "/no_think",
        })

        assert response.status_code == 200
        saved_config = mock_config_env.set_value.call_args.args[1]
        assert saved_config["lm_studio"]["api_url"] == "http://localhost:1234/v1"
        assert saved_config["lm_studio"]["prompt_prefix"] == "/no_think"
        assert saved_config["lm_studio"]["system_prompt_suffix"] == "/no_think"

    def test_saves_verified_reasoning_preset_and_custom_parameters(self, mock_config_env):
        client = TestClient(app)
        response = client.post("/api/providers/config", json={
            "provider_id": "gemini",
            "selected_model": "gemini-1.5-pro",
            "reasoning_builtin_enabled": True,
            "reasoning_preset": "medium",
            "custom_parameters": {"thinking_config": {"include_thoughts": False}},
        })

        assert response.status_code == 200
        saved = mock_config_env.set_value.call_args.args[1]["gemini"]
        assert saved["reasoning_builtin_enabled"] is True
        assert saved["reasoning_preset"] == "medium"
        assert saved["custom_parameters"] == {
            "thinking_config": {"include_thoughts": False}
        }

    def test_rejects_builtin_reasoning_for_an_unverified_custom_model(self, mock_config_env):
        client = TestClient(app)
        response = client.post("/api/providers/config", json={
            "provider_id": "gemini",
            "selected_model": "custom-gemini",
            "reasoning_builtin_enabled": True,
            "reasoning_preset": "medium",
        })

        assert response.status_code == 400
        assert "no verified" in response.json()["detail"]
        mock_config_env.set_value.assert_not_called()

    def test_rejects_custom_parameters_that_replace_messages(self, mock_config_env):
        client = TestClient(app)
        response = client.post("/api/providers/config", json={
            "provider_id": "gemini",
            "selected_model": "gemini-1.5-pro",
            "custom_parameters": {"messages": []},
        })

        assert response.status_code == 400
        assert "protected fields" in response.json()["detail"]


class TestLocalProviderConnection:
    def test_openai_compatible_provider_checks_models_endpoint(self, mock_config_env):
        client = TestClient(app)

        with patch("scripts.routers.config.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            response = client.post("/api/providers/test-connection", json={
                "provider_id": "lm_studio",
                "api_url": "http://127.0.0.1:6640/v1",
            })

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_get.assert_called_once_with(
            "http://127.0.0.1:6640/v1/models",
            timeout=5,
        )

    def test_ollama_provider_checks_version_endpoint(self, mock_config_env):
        client = TestClient(app)

        with patch("scripts.routers.config.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            response = client.post("/api/providers/test-connection", json={
                "provider_id": "ollama",
                "api_url": "http://127.0.0.1:11434",
            })

        assert response.status_code == 200
        mock_get.assert_called_once_with(
            "http://127.0.0.1:11434/api/version",
            timeout=5,
        )

    def test_connection_failure_returns_provider_and_url(self, mock_config_env):
        client = TestClient(app)

        with patch("scripts.routers.config.requests.get", side_effect=OSError("refused")):
            response = client.post("/api/providers/test-connection", json={
                "provider_id": "lm_studio",
                "api_url": "http://127.0.0.1:1234/v1",
            })

        assert response.status_code == 502
        detail = response.json()["detail"]
        assert "LM Studio" in detail
        assert "http://127.0.0.1:1234/v1" in detail
