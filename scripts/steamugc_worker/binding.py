"""Narrow ctypes binding to Valve's SDK, loaded only by the child process.

Interface accessor names and callback layouts come from the same SDK's
steam_api.json. No SDK binaries or community wrapper code are bundled here.
"""
import ctypes as c
import json
from pathlib import Path
import re
import time

TYPES = {"int": c.c_int, "uint32": c.c_uint32, "uint64": c.c_uint64,
         "bool": c.c_bool, "EResult": c.c_int, "PublishedFileId_t": c.c_uint64,
         "SteamAPICall_t": c.c_uint64}
TYPES.update({"AppId_t": c.c_uint32, "UGCHandle_t": c.c_uint64, "UGCQueryHandle_t": c.c_uint64,
              "EWorkshopFileType": c.c_int, "ERemoteStoragePublishedFileVisibility": c.c_int,
              "int32": c.c_int32, "float": c.c_float})


class SteamFailure(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CallbackMessage(c.Structure):
    _fields_ = [("user", c.c_int), ("callback", c.c_int),
                ("param", c.c_void_p), ("size", c.c_int)]


class CallCompleted(c.Structure):
    _fields_ = [("call", c.c_uint64), ("callback", c.c_int), ("size", c.c_uint32)]


class StringArray(c.Structure):
    _fields_ = [("strings", c.POINTER(c.c_char_p)), ("count", c.c_int)]


class SteamBinding:
    def __init__(self, sdk_dir, app_id):
        root = Path(sdk_dir)
        descriptor = json.loads((root / "public/steam/steam_api.json").read_text(encoding="utf-8"))
        self.descriptor = descriptor
        self.dll = c.CDLL(str(root / "redistributable_bin/win64/steam_api64.dll"))
        self.initialized = False
        self._bind_core()
        (Path.cwd() / "steam_appid.txt").write_text(str(app_id), encoding="utf-8")
        error_buffer = c.create_string_buffer(1024)
        if self.init(c.byref(error_buffer)) != 0:
            raise SteamFailure("steam_initialization_failed")
        self.initialized = True
        try:
            self.manual_init()
            self.pipe = self.get_pipe()
            self.ugc = self._interface("ISteamUGC")
            self.user = self._interface("ISteamUser")
            self.apps = self._interface("ISteamApps")
            self.utils = self._interface("ISteamUtils")
            self._bind_publication()
            self.callback_type("CreateItemResult_t")
            self.callback_type("SubmitItemUpdateResult_t")
            self._bind_queries()
        except Exception:
            self.close()
            raise

    def _fn(self, name, result, args):
        try:
            fn = getattr(self.dll, name)
        except AttributeError as exc:
            raise SteamFailure("steam_sdk_abi_unsupported") from exc
        fn.restype, fn.argtypes = result, args
        return fn

    def _interface(self, class_name):
        interface = next((item for item in self.descriptor["interfaces"]
                          if item["classname"] == class_name), None)
        accessors = (interface or {}).get("accessors", [])
        accessor = next((item.get("name_flat") for item in accessors if item.get("kind") == "user"), None)
        if accessor is None:
            raise SteamFailure("steam_sdk_abi_unsupported")
        value = self._fn(accessor, c.c_void_p, [])()
        if not value:
            raise SteamFailure("steam_interface_unavailable")
        return value

    def _bind_core(self):
        self.init = self._fn("SteamAPI_InitFlat", c.c_int, [c.c_void_p])
        self.shutdown = self._fn("SteamAPI_Shutdown", None, [])
        self.get_pipe = self._fn("SteamAPI_GetHSteamPipe", c.c_int, [])
        self.manual_init = self._fn("SteamAPI_ManualDispatch_Init", None, [])
        self.run_frame = self._fn("SteamAPI_ManualDispatch_RunFrame", None, [c.c_int])
        self.next_callback = self._fn("SteamAPI_ManualDispatch_GetNextCallback", c.c_bool,
                                      [c.c_int, c.POINTER(CallbackMessage)])
        self.free_callback = self._fn("SteamAPI_ManualDispatch_FreeLastCallback", None, [c.c_int])
        self.call_result = self._fn("SteamAPI_ManualDispatch_GetAPICallResult", c.c_bool,
                                   [c.c_int, c.c_uint64, c.c_void_p, c.c_int, c.c_int, c.POINTER(c.c_bool)])

    def _bind_publication(self):
        self.logged_on = self._fn("SteamAPI_ISteamUser_BLoggedOn", c.c_bool, [c.c_void_p])
        self.steam_id = self._fn("SteamAPI_ISteamUser_GetSteamID", c.c_uint64, [c.c_void_p])
        self.subscribed = self._fn("SteamAPI_ISteamApps_BIsSubscribedApp", c.c_bool, [c.c_void_p, c.c_uint32])
        self.app_id = self._fn("SteamAPI_ISteamUtils_GetAppID", c.c_uint32, [c.c_void_p])
        self.create = self._fn("SteamAPI_ISteamUGC_CreateItem", c.c_uint64, [c.c_void_p, c.c_uint32, c.c_int])
        self.start = self._fn("SteamAPI_ISteamUGC_StartItemUpdate", c.c_uint64, [c.c_void_p, c.c_uint32, c.c_uint64])
        self.submit = self._fn("SteamAPI_ISteamUGC_SubmitItemUpdate", c.c_uint64, [c.c_void_p, c.c_uint64, c.c_char_p])
        self.progress = self._fn("SteamAPI_ISteamUGC_GetItemUpdateProgress", c.c_int,
                                [c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64), c.POINTER(c.c_uint64)])
        self.setters = {name: self._fn("SteamAPI_ISteamUGC_" + name, c.c_bool,
                                      [c.c_void_p, c.c_uint64, c.c_char_p])
                        for name in ("SetItemTitle", "SetItemDescription", "SetItemUpdateLanguage",
                                     "SetItemContent", "SetItemPreview")}
        self.set_visibility = self._fn("SteamAPI_ISteamUGC_SetItemVisibility", c.c_bool,
                                       [c.c_void_p, c.c_uint64, c.c_int])
        interface = next(item for item in self.descriptor["interfaces"] if item["classname"] == "ISteamUGC")
        method = next(item for item in interface["methods"] if item["methodname"] == "SetItemTags")
        self.admin_tags_parameter = len(method["params"]) == 3
        if len(method["params"]) not in {2, 3}:
            raise SteamFailure("steam_sdk_abi_unsupported")
        tag_args = [c.c_void_p, c.c_uint64, c.POINTER(StringArray)]
        if self.admin_tags_parameter:
            tag_args.append(c.c_bool)
        self.set_tags = self._fn("SteamAPI_ISteamUGC_SetItemTags", c.c_bool, tag_args)

    def callback_type(self, name):
        structure, specification = self._structure(name, "callback_structs")
        return structure, int(specification["callback_id"])

    def _structure(self, name, collection):
        specification = next((item for item in self.descriptor[collection]
                              if item["struct"] == name), None)
        if not specification:
            raise SteamFailure("steam_sdk_abi_unsupported")
        fields = []
        for field in specification["fields"]:
            field_type = TYPES.get(field["fieldtype"])
            char_array = re.fullmatch(r"char \[(\d+)\]", field["fieldtype"])
            if char_array and 0 < int(char_array[1]) <= 8192:
                field_type = c.c_char * int(char_array[1])
            if field_type is None:
                raise SteamFailure("steam_sdk_abi_unsupported")
            fields.append((field["fieldname"], field_type))
        # Windows Steamworks structs use the native 8-byte packing convention.
        structure = type(name, (c.Structure,), {"_pack_": 8, "_fields_": fields})
        return structure, specification

    def _bind_queries(self):
        self.details_type, _ = self._structure("SteamUGCDetails_t", "structs")
        self.query_create = self._fn("SteamAPI_ISteamUGC_CreateQueryUGCDetailsRequest", c.c_uint64,
                                     [c.c_void_p, c.POINTER(c.c_uint64), c.c_uint32])
        self.query_send = self._fn("SteamAPI_ISteamUGC_SendQueryUGCRequest", c.c_uint64, [c.c_void_p, c.c_uint64])
        self.query_result = self._fn("SteamAPI_ISteamUGC_GetQueryUGCResult", c.c_bool,
                                     [c.c_void_p, c.c_uint64, c.c_uint32, c.POINTER(self.details_type)])
        self.query_release = self._fn("SteamAPI_ISteamUGC_ReleaseQueryUGCRequest", c.c_bool, [c.c_void_p, c.c_uint64])
        self.callback_type("SteamUGCQueryCompleted_t")

    def inspect_item(self, app_id, item_id):
        item = c.c_uint64(int(item_id))
        query = self.query_create(self.ugc, c.byref(item), 1)
        if query in {0, 2**64 - 1}:
            raise SteamFailure("steam_query_failed")
        try:
            result = self.wait(self.query_send(self.ugc, query), "SteamUGCQueryCompleted_t", timeout=20)
            details = self.details_type()
            if result.m_eResult != 1 or result.m_unNumResultsReturned != 1 or not self.query_result(self.ugc, query, 0, c.byref(details)) or details.m_eResult != 1:
                raise SteamFailure("steam_item_not_found")
            if details.m_nPublishedFileId != int(item_id) or details.m_nConsumerAppID != app_id:
                raise SteamFailure("steam_target_app_mismatch")
            if details.m_ulSteamIDOwner != self.steam_id(self.user):
                raise SteamFailure("steam_target_not_owned")
            return {"published_file_id": str(item_id), "consumer_app_id": app_id, "owner_matches": True}
        finally:
            self.query_release(self.ugc, query)

    def wait(self, handle, callback_name, tick=lambda: None, timeout=900):
        if not handle:
            raise SteamFailure("steam_call_invalid")
        structure, callback_id = self.callback_type(callback_name)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.run_frame(self.pipe)
            message = CallbackMessage()
            while self.next_callback(self.pipe, c.byref(message)):
                try:
                    if message.callback != 703:
                        continue
                    if message.size != c.sizeof(CallCompleted):
                        raise SteamFailure("steam_callback_layout_mismatch")
                    completed = c.cast(message.param, c.POINTER(CallCompleted)).contents
                    if completed.call != handle:
                        continue
                    if completed.callback != callback_id or completed.size != c.sizeof(structure):
                        raise SteamFailure("steam_callback_layout_mismatch")
                    result, failed = structure(), c.c_bool()
                    if not self.call_result(self.pipe, handle, c.byref(result), c.sizeof(result), callback_id, c.byref(failed)) or failed.value:
                        raise SteamFailure("steam_call_result_failed")
                    return result
                finally:
                    self.free_callback(self.pipe)
            tick()
            time.sleep(0.1)
        raise SteamFailure("steam_callback_timeout")

    def preflight(self, app_id):
        if not self.logged_on(self.user):
            raise SteamFailure("steam_not_logged_in")
        if self.app_id(self.utils) != app_id or not self.subscribed(self.apps, app_id):
            raise SteamFailure("steam_app_not_owned")
        return str(self.steam_id(self.user))

    def configure(self, handle, request):
        values = {"SetItemUpdateLanguage": request["language"], "SetItemTitle": request["title"],
                  "SetItemDescription": request["description"], "SetItemContent": request["content_path"],
                  "SetItemPreview": request["preview_path"]}
        for name, value in values.items():
            if not self.setters[name](self.ugc, handle, value.encode("utf-8")):
                raise SteamFailure("steam_metadata_rejected")
        visibility = {"public": 0, "friends_only": 1, "private": 2, "unlisted": 3}[request["visibility"]]
        if not self.set_visibility(self.ugc, handle, visibility):
            raise SteamFailure("steam_visibility_rejected")
        encoded = [item.encode("utf-8") for item in request["tags"]]
        array = (c.c_char_p * len(encoded))(*encoded)
        tags = StringArray(array, len(encoded))
        args = [self.ugc, handle, c.byref(tags)]
        if self.admin_tags_parameter:
            args.append(False)
        if not self.set_tags(*args):
            raise SteamFailure("steam_tags_rejected")

    def close(self):
        if self.initialized:
            self.shutdown()
            self.initialized = False
