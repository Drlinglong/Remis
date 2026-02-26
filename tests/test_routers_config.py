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
