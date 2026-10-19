"""Single-use JSONL SteamUGC worker. Never accepts Steam credentials."""
import ctypes as c
import json
import os
from pathlib import Path
import sys
import time

from binding import SteamBinding, SteamFailure
from process_lock import publication_lock


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def outcome(status, code, item_id=None, result=None):
    emit({"type": "result", "status": status, "code": code,
          "published_file_id": str(item_id) if item_id else None,
          "eresult": result, "legal_agreement_required": status == "legal_agreement_required"})


def publish(api, request):
    item_id = request.get("published_file_id")
    created = False
    try:
        if request["mode"] == "create":
            emit({"type": "remote_started", "operation": "create"})
            result = api.wait(api.create(api.ugc, request["app_id"], 0), "CreateItemResult_t")
            if result.m_eResult != 1:
                outcome("failed", "steam_create_rejected", result=result.m_eResult)
                return
            item_id, created = result.m_nPublishedFileId, True
            if not item_id:
                raise SteamFailure("steam_invalid_created_item")
            emit({"type": "created", "published_file_id": str(item_id)})
            if result.m_bUserNeedsToAcceptWorkshopLegalAgreement:
                outcome("legal_agreement_required", "steam_legal_agreement_required", item_id, 1)
                return
        update = api.start(api.ugc, request["app_id"], int(item_id))
        if update in {0, 2**64 - 1}:
            raise SteamFailure("steam_update_handle_invalid")
        api.configure(update, request)
        emit({"type": "remote_started", "operation": "submit", "published_file_id": str(item_id)})
        call = api.submit(api.ugc, update, request["change_note"].encode("utf-8"))
        last_tick = 0

        def tick():
            nonlocal last_tick
            if time.monotonic() - last_tick < 1:
                return
            last_tick = time.monotonic()
            done, total = c.c_uint64(), c.c_uint64()
            phase = api.progress(api.ugc, update, c.byref(done), c.byref(total))
            emit({"type": "progress", "phase": phase, "bytes_done": done.value, "bytes_total": total.value})

        result = api.wait(call, "SubmitItemUpdateResult_t", tick)
        if getattr(result, "m_nPublishedFileId", int(item_id)) != int(item_id):
            raise SteamFailure("steam_result_target_mismatch")
        if result.m_bUserNeedsToAcceptWorkshopLegalAgreement:
            outcome("legal_agreement_required", "steam_legal_agreement_required", item_id, result.m_eResult)
        elif result.m_eResult != 1:
            outcome("unknown" if created else "failed", "steam_submit_rejected", item_id, result.m_eResult)
        else:
            outcome("succeeded", "steam_submit_confirmed", item_id, 1)
    except SteamFailure as exc:
        # Even a deterministic setter failure after CreateItem leaves a remote
        # item. Require verification so a new plan cannot create a duplicate.
        outcome("unknown", exc.code, item_id)


def run_request():
    api = None
    operation = "publish"
    try:
        if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
            raise SteamFailure("windows_x64_required")
        request = json.loads(sys.stdin.read(1024 * 1024))
        operation = request["operation"]
        if any(key in request for key in ("password", "username", "api_key")):
            raise SteamFailure("credentials_not_supported")
        api = SteamBinding(request["sdk_dir"], request["app_id"])
        steam_id = api.preflight(request["app_id"])
        if operation == "probe":
            target = api.inspect_item(request["app_id"], request["published_file_id"]) if request.get("published_file_id") else {}
            emit({"type": "probe", "ready": True, "code": "steam_ready", "steam_id": steam_id, **target})
        elif operation == "publish":
            if steam_id != request["steam_id"]:
                raise SteamFailure("steam_account_changed")
            if request["mode"] == "update":
                api.inspect_item(request["app_id"], request["published_file_id"])
            publish(api, request)
        else:
            raise SteamFailure("operation_not_supported")
    except SteamFailure as exc:
        if operation == "probe":
            emit({"type": "probe", "ready": False, "code": exc.code})
        else:
            outcome("failed", exc.code)
    except Exception:
        if operation == "probe":
            emit({"type": "probe", "ready": False, "code": "steam_runtime_failed"})
        else:
            outcome("unknown", "steam_runtime_failed")
    finally:
        if api:
            api.close()
        (Path.cwd() / "steam_appid.txt").unlink(missing_ok=True)


def main():
    try:
        with publication_lock():
            run_request()
    except SteamFailure as exc:
        outcome("failed", exc.code)


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    main()
