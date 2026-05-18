from scripts.utils.backend_identity import is_reusable_backend_health
from scripts.utils.system_utils import _is_remis_backend_process


CURRENT_IDENTITY = {
    "status": "ok",
    "app": "remis",
    "pid": 123,
    "version": "3.0.0",
    "api_contract": 1,
    "is_frozen": False,
    "app_root": "J:/V3_Mod_Localization_Factory",
    "started_at": "2026-05-14T00:00:00+00:00",
    "backend_fingerprint": "abc123",
}


def test_reuses_matching_backend_health():
    assert is_reusable_backend_health(dict(CURRENT_IDENTITY), CURRENT_IDENTITY)


def test_rejects_stale_backend_fingerprint():
    health = dict(CURRENT_IDENTITY)
    health["backend_fingerprint"] = "old456"

    assert not is_reusable_backend_health(health, CURRENT_IDENTITY)


def test_rejects_other_app_on_same_port():
    health = dict(CURRENT_IDENTITY)
    health["app"] = "other-service"

    assert not is_reusable_backend_health(health, CURRENT_IDENTITY)


class FakeProcess:
    def __init__(self, name, cmdline=None, exe=""):
        self._name = name
        self._cmdline = cmdline or []
        self._exe = exe

    def name(self):
        return self._name

    def cmdline(self):
        return self._cmdline

    def exe(self):
        return self._exe


def test_port_cleanup_only_targets_remis_backend_processes():
    assert _is_remis_backend_process(FakeProcess("web_server.exe"))
    assert _is_remis_backend_process(
        FakeProcess("python.exe", ["python", "J:/V3_Mod_Localization_Factory/scripts/web_server.py"])
    )
    assert not _is_remis_backend_process(FakeProcess("node.exe", ["node", "server.js"]))
