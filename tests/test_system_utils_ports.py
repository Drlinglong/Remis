from scripts.utils import system_utils


def test_dev_launcher_check_exits_before_mutating_port_selection():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    launcher = (
        repo_root / "scripts" / "developer_tools" / "windows" / "run-dev.bat"
    ).read_text(encoding="utf-8")

    check_index = launcher.index('if /i "%~1"=="--check"')
    selector_index = launcher.index("--select-backend-port")
    default_port_index = launcher.index('set "REMIS_BACKEND_PORT=1453"')

    assert default_port_index < check_index < selector_index
    assert "No process or port was changed" in launcher[check_index:selector_index]


def test_select_backend_port_uses_requested_port_when_available(monkeypatch):
    checked_ports = []

    monkeypatch.setattr(system_utils, "force_free_port", lambda port: checked_ports.append(port))
    monkeypatch.setattr(system_utils, "is_port_available", lambda port: True)

    assert system_utils.select_backend_port(1453) == 1453
    assert checked_ports == [1453]


def test_select_backend_port_falls_back_when_requested_port_is_occupied(monkeypatch):
    checked_ports = []

    monkeypatch.setattr(system_utils, "force_free_port", lambda port: checked_ports.append(port))
    monkeypatch.setattr(system_utils, "is_port_available", lambda port: port == 1455)

    assert system_utils.select_backend_port(1453) == 1455
    assert checked_ports == [1453]
