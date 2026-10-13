"""Worker protocol and ctypes callback validation without native Steam access."""
import ctypes as c
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def native(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "scripts/steamugc_worker"
    monkeypatch.syspath_prepend(str(directory))
    return importlib.import_module("binding"), importlib.import_module("worker")


def test_sdk_descriptor_drives_callback_shape_and_size(native):
    binding, _ = native
    api = object.__new__(binding.SteamBinding)
    api.descriptor = {"callback_structs": [{"struct": "SubmitItemUpdateResult_t", "callback_id": 3404,
        "fields": [{"fieldname": "m_eResult", "fieldtype": "EResult"},
                   {"fieldname": "m_bUserNeedsToAcceptWorkshopLegalAgreement", "fieldtype": "bool"},
                   {"fieldname": "m_nPublishedFileId", "fieldtype": "PublishedFileId_t"}]}]}
    structure, callback_id = api.callback_type("SubmitItemUpdateResult_t")
    assert callback_id == 3404
    assert c.sizeof(structure) == 16
    assert structure.m_nPublishedFileId.offset == 8
    api.descriptor["callback_structs"][0]["fields"][0]["fieldtype"] = "unsupported"
    with pytest.raises(binding.SteamFailure, match="abi"):
        api.callback_type("SubmitItemUpdateResult_t")


def test_callback_size_mismatch_is_rejected_and_callback_is_freed(native):
    binding, _ = native
    api = object.__new__(binding.SteamBinding)
    api.pipe = 1
    api.callback_type = lambda _: (binding.CallCompleted, 3404)
    api.run_frame = lambda _: None
    freed = []
    def callback(_pipe, pointer):
        message = c.cast(pointer, c.POINTER(binding.CallbackMessage)).contents
        message.callback, message.size = 703, 1
        return True
    api.next_callback, api.free_callback = callback, lambda _: freed.append(True)
    with pytest.raises(binding.SteamFailure, match="layout"):
        api.wait(10, "SubmitItemUpdateResult_t")
    assert freed == [True]


class FakeNative:
    ugc = 1
    def __init__(self, binding, create_result=1, submit_result=1, legal=False, fail_submit=False):
        self.binding = binding
        self.create_result, self.submit_result = create_result, submit_result
        self.legal, self.fail_submit = legal, fail_submit
        self.calls = []

    def create(self, *args):
        self.calls.append("create")
        return 10

    def start(self, *args):
        self.calls.append("start")
        return 11

    def configure(self, *args):
        self.calls.append("configure")

    def submit(self, *args):
        self.calls.append("submit")
        return 12

    def wait(self, _handle, name, tick=None):
        if name == "CreateItemResult_t":
            return SimpleNamespace(m_eResult=self.create_result, m_nPublishedFileId=12345,
                                   m_bUserNeedsToAcceptWorkshopLegalAgreement=self.legal)
        if self.fail_submit:
            raise self.binding.SteamFailure("steam_callback_timeout")
        return SimpleNamespace(m_eResult=self.submit_result, m_bUserNeedsToAcceptWorkshopLegalAgreement=self.legal)


@pytest.mark.parametrize("mode,eresult,legal,timeout,expected", [
    ("create", 1, False, False, "succeeded"),
    ("create", 1, True, False, "legal_agreement_required"),
    ("create", 2, False, False, "unknown"),
    ("update", 2, False, False, "failed"),
    ("update", 1, False, True, "unknown"),
])
def test_native_submission_requires_confirmed_callback(native, capsys, mode, eresult, legal, timeout, expected):
    binding, worker = native
    api = FakeNative(binding, submit_result=eresult, legal=legal, fail_submit=timeout)
    worker.publish(api, {"mode": mode, "published_file_id": "12345" if mode == "update" else None,
                         "app_id": 529340, "change_note": "更新"})
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["type"] == "result"
    assert events[-1]["status"] == expected
    if mode == "update":
        assert "create" not in api.calls
    if legal:
        assert "submit" not in api.calls


def test_creation_error_never_submits_content(native, capsys):
    binding, worker = native
    api = FakeNative(binding, create_result=15)
    worker.publish(api, {"mode": "create", "app_id": 529340})
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["status"] == "failed" and result["eresult"] == 15
    assert api.calls == ["create"]


def test_sdk_165_accessor_uses_flat_name_not_cpp_name(native):
    binding, _ = native
    api = object.__new__(binding.SteamBinding)
    api.descriptor = {"interfaces": [{"classname": "ISteamUGC", "accessors": [
        {"kind": "user", "name": "SteamUGC", "name_flat": "SteamAPI_SteamUGC_v021"},
    ]}]}
    requested = []
    def function(name, _result, _args):
        requested.append(name)
        return lambda: 123
    api._fn = function
    assert api._interface("ISteamUGC") == 123
    assert requested == ["SteamAPI_SteamUGC_v021"]


def test_flat_initialization_does_not_require_cpp_inline_symbol(native):
    binding, _ = native
    api = object.__new__(binding.SteamBinding)
    functions = {}
    def function(name, result, args):
        functions[name] = (result, args)
        return lambda *args: None
    api._fn = function
    api._bind_core()
    assert "SteamAPI_InitFlat" in functions
    assert "SteamAPI_Init" not in functions
    assert functions["SteamAPI_InitFlat"] == (c.c_int, [c.c_void_p])


@pytest.mark.parametrize("admin_parameter", [True, False])
def test_sdk_tags_signature_and_utf8_metadata(native, admin_parameter):
    binding, _ = native
    api = object.__new__(binding.SteamBinding)
    api.ugc = 1
    params = [{"paramtype": "UGCUpdateHandle_t"}, {"paramtype": "const SteamParamStringArray_t *"}]
    if admin_parameter:
        params.append({"paramtype": "bool"})
    api.descriptor = {"interfaces": [{"classname": "ISteamUGC", "methods": [{"methodname": "SetItemTags", "params": params}]}]}
    calls, signatures = {}, {}
    def function(name, result, args):
        signatures[name] = args
        def call(*values):
            calls[name] = values
            return True
        return call
    api._fn = function
    api._bind_publication()
    api.configure(10, {"language": "schinese", "title": "翻译包", "description": "内容",
                       "content_path": "J:/package", "preview_path": "J:/preview.png",
                       "visibility": "private", "tags": ["Translation"]})
    assert calls["SteamAPI_ISteamUGC_SetItemTitle"][-1] == "翻译包".encode("utf-8")
    assert len(calls["SteamAPI_ISteamUGC_SetItemTags"]) == (4 if admin_parameter else 3)
    if admin_parameter:
        assert calls["SteamAPI_ISteamUGC_SetItemTags"][-1] is False
