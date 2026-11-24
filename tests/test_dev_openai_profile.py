import json

import pytest

from scripts import app_settings


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    standard = tmp_path / "standard.json"
    shared = tmp_path / "shared.json"
    standard.write_text(json.dumps({"api_keys": {"openai": "standard-fixture", "gemini": "gemini-fixture"}}), encoding="utf-8")
    shared.write_text(json.dumps({"api_keys": {"openai": "shared-fixture", "gemini": "unused-fixture"}}), encoding="utf-8")
    monkeypatch.setattr(app_settings, "get_appdata_config_path", lambda: str(standard))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-fixture")
    monkeypatch.setenv("REMIS_DEV_OPENAI_CONFIG", str(shared))
    return shared


def test_explicit_dev_profile_only_applies_to_openai(profiles, monkeypatch):
    assert app_settings.get_api_key("openai", "OPENAI_API_KEY") == "shared-fixture"
    assert app_settings.get_api_key("gemini", "GEMINI_API_KEY") == "gemini-fixture"
    monkeypatch.delenv("REMIS_DEV_OPENAI_CONFIG")
    assert app_settings.get_api_key("openai", "OPENAI_API_KEY") == "standard-fixture"


@pytest.mark.parametrize("invalid", ["missing.json", "{bad json}", "{}"])
def test_explicit_profile_does_not_fall_back(profiles, monkeypatch, invalid):
    if invalid == "missing.json":
        monkeypatch.setenv("REMIS_DEV_OPENAI_CONFIG", invalid)
    else:
        profiles.write_text(invalid, encoding="utf-8")
    assert app_settings.get_api_key("openai", "OPENAI_API_KEY") is None


def test_packaged_runtime_uses_its_own_config(profiles, monkeypatch):
    monkeypatch.setattr(app_settings.sys, "frozen", True, raising=False)
    assert app_settings.get_api_key("openai", "OPENAI_API_KEY") == "standard-fixture"
