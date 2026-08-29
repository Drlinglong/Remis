import json

from scripts import build_profile


def test_stable_profile_is_the_default(monkeypatch):
    monkeypatch.delenv("REMIS_BUILD_CHANNEL", raising=False)
    monkeypatch.setattr(build_profile, "_bundled_channel", lambda: None)

    profile = build_profile.get_build_profile()

    assert profile.channel == "stable"
    assert profile.app_data_folder == "RemisModFactory"
    assert profile.backend_port == 1453
    assert profile.copilot_enabled is False


def test_agent_preview_profile_is_fully_isolated(monkeypatch):
    monkeypatch.setenv("REMIS_BUILD_CHANNEL", "agent-preview")

    stable = build_profile.PROFILES["stable"]
    preview = build_profile.get_build_profile()

    assert preview.copilot_enabled is True
    assert preview.product_name == "Remis Agent Preview"
    assert preview.version == "3.1.7-agent-preview.1"
    assert preview.identifier != stable.identifier
    assert preview.app_data_folder != stable.app_data_folder
    assert preview.backend_port != stable.backend_port


def test_development_app_data_is_isolated_by_channel():
    stable = build_profile.PROFILES["stable"]
    preview = build_profile.PROFILES["agent-preview"]

    assert build_profile.runtime_app_data_folder(stable, frozen=False) == "RemisModFactoryDev"
    assert build_profile.runtime_app_data_folder(preview, frozen=False) == "RemisAgentPreviewDev"
    assert build_profile.runtime_app_data_folder(stable, frozen=True) == "RemisModFactory"
    assert build_profile.runtime_app_data_folder(preview, frozen=True) == "RemisAgentPreview"


def test_profile_manifest_contains_the_shared_channel(tmp_path):
    path = tmp_path / "missing-parent" / "build_profile.json"
    build_profile.write_profile_manifest(build_profile.PROFILES["agent-preview"], path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["channel"] == "agent-preview"
    assert payload["copilot_enabled"] is True
