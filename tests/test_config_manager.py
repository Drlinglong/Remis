"""
测试 ConfigManager 的核心功能，尤其是 update_nested_value 方法。
这些测试专门用于防止"保存 API Key 路径"因架构重构而产生回归。
"""
import json
import os
import pytest
import tempfile

from scripts.core.config_manager import ConfigManager


@pytest.fixture
def temp_config_dir(tmp_path):
    """提供一个临时的、独立的配置目录，防止污染真实配置。"""
    return str(tmp_path)


@pytest.fixture
def manager(temp_config_dir):
    return ConfigManager(temp_config_dir)


class TestGetAndSetValue:
    def test_get_returns_default_when_key_missing(self, manager):
        assert manager.get_value("nonexistent_key", "default") == "default"

    def test_set_and_get_roundtrip(self, manager):
        manager.set_value("rpm_limit", 60)
        assert manager.get_value("rpm_limit") == 60

    def test_set_overwrites_existing(self, manager):
        manager.set_value("rpm_limit", 40)
        manager.set_value("rpm_limit", 80)
        assert manager.get_value("rpm_limit") == 80


class TestUpdateNestedValue:
    """
    专门测试 update_nested_value。
    这是导致首次用户无法保存 API Key 的 Bug 来源，必须覆盖。
    """

    def test_method_exists(self, manager):
        """回归测试：确保方法存在，防止架构重构后再次丢失。"""
        assert hasattr(manager, "update_nested_value"), (
            "ConfigManager 缺少 update_nested_value 方法。"
            "这个方法是保存 API Key 所必需的。"
        )

    def test_creates_parent_key_if_missing(self, manager):
        """当父键不存在时，应自动创建父级字典。"""
        manager.update_nested_value("api_keys", "gemini", "AIza_test_key")
        result = manager.get_value("api_keys")
        assert result == {"gemini": "AIza_test_key"}

    def test_adds_child_to_existing_parent(self, manager):
        """已有父键时，应只更新指定的子键，不影响其他 Key。"""
        manager.update_nested_value("api_keys", "gemini", "key_gemini")
        manager.update_nested_value("api_keys", "openai", "key_openai")
        result = manager.get_value("api_keys")
        assert result["gemini"] == "key_gemini"
        assert result["openai"] == "key_openai"

    def test_overwrites_existing_child_key(self, manager):
        """应能覆盖已存在的子键。"""
        manager.update_nested_value("api_keys", "gemini", "old_key")
        manager.update_nested_value("api_keys", "gemini", "new_key")
        assert manager.get_value("api_keys")["gemini"] == "new_key"

    def test_persists_to_disk(self, manager, temp_config_dir):
        """写入后，真实的 config.json 文件内容必须包含正确数据。"""
        manager.update_nested_value("api_keys", "gemini", "AIza_persisted")
        config_path = os.path.join(temp_config_dir, "config.json")
        assert os.path.exists(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["api_keys"]["gemini"] == "AIza_persisted"

    def test_recovers_if_parent_value_is_not_dict(self, manager):
        """若父键已存在但值不是字典（数据损坏场景），应覆盖为字典。"""
        manager.set_value("api_keys", "corrupted_string_value")
        # 不应抛出异常
        manager.update_nested_value("api_keys", "gemini", "AIza_recovered")
        assert manager.get_value("api_keys") == {"gemini": "AIza_recovered"}
