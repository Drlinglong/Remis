import pytest
import sys
from fastapi.testclient import TestClient
import scripts.web_server as web_server
from scripts.web_server import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "欢迎使用P社Mod本地化工厂API"}

def test_docs_endpoint():
    response = client.get("/docs")
    assert response.status_code == 200

def test_port_preflight_exit_is_explicit_startup_behavior(monkeypatch):
    monkeypatch.setattr(web_server, "_fetch_existing_backend_health", lambda port: {"status": "ok"})

    import scripts.app_settings as app_settings
    import scripts.utils.backend_identity as backend_identity

    monkeypatch.setattr(app_settings, "get_backend_port", lambda: 1453)
    monkeypatch.setattr(backend_identity, "is_reusable_backend_health", lambda health: True)

    with pytest.raises(SystemExit) as exc_info:
        web_server.run_port_preflight()

    assert exc_info.value.code == 0


def test_port_preflight_replaces_health_verified_mismatched_remis_backend(monkeypatch):
    existing_health = {
        "status": "ok",
        "app": "remis",
        "pid": 77264,
        "api_contract": 1,
        "app_root": "J:/another-remis-checkout",
        "backend_fingerprint": "different",
    }
    monkeypatch.setattr(web_server, "_fetch_existing_backend_health", lambda port: existing_health)

    import scripts.app_settings as app_settings
    import scripts.utils.backend_identity as backend_identity
    import scripts.utils.system_utils as system_utils

    cleanup_calls = []
    monkeypatch.setattr(app_settings, "get_backend_port", lambda: 1453)
    monkeypatch.setattr(backend_identity, "is_reusable_backend_health", lambda health: False)
    monkeypatch.setattr(
        system_utils,
        "force_free_port",
        lambda port, *, trusted_remis_pid=None: cleanup_calls.append((port, trusted_remis_pid)),
    )
    monkeypatch.setattr(system_utils, "is_port_available", lambda port: True)

    web_server.run_port_preflight()

    assert cleanup_calls == [(1453, 77264)]


def test_port_preflight_refuses_to_continue_when_non_remis_process_keeps_port(monkeypatch):
    monkeypatch.setattr(
        web_server,
        "_fetch_existing_backend_health",
        lambda port: {"status": "ok", "app": "other-service", "pid": 12345},
    )

    import scripts.app_settings as app_settings
    import scripts.utils.backend_identity as backend_identity
    import scripts.utils.system_utils as system_utils

    cleanup_calls = []
    monkeypatch.setattr(app_settings, "get_backend_port", lambda: 1453)
    monkeypatch.setattr(backend_identity, "is_reusable_backend_health", lambda health: False)
    monkeypatch.setattr(
        system_utils,
        "force_free_port",
        lambda port, *, trusted_remis_pid=None: cleanup_calls.append((port, trusted_remis_pid)),
    )
    monkeypatch.setattr(system_utils, "is_port_available", lambda port: False)

    with pytest.raises(RuntimeError, match="remains occupied"):
        web_server.run_port_preflight()

    assert cleanup_calls == [(1453, None)]


def test_packaged_build_hides_copilot_router_by_default(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("REMIS_ENABLE_COPILOT", raising=False)

    assert web_server.copilot_router_enabled() is False


def test_copilot_router_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("REMIS_ENABLE_COPILOT", "true")

    assert web_server.copilot_router_enabled() is True


def test_agent_preview_frozen_build_enables_copilot_from_profile(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("REMIS_ENABLE_COPILOT", raising=False)
    monkeypatch.setenv("REMIS_BUILD_CHANNEL", "agent-preview")

    assert web_server.copilot_router_enabled() is True
