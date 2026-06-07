from scripts.utils import system_utils


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
