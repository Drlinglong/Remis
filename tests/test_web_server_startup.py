import pytest
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
