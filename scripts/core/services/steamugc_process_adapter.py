"""Isolate native Steam API state and credentials from the FastAPI process."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path


class SteamUGCProcessAdapter:
    def __init__(self, sdk_dir=None, python_exe=None):
        self.sdk_dir = sdk_dir or os.environ.get("REMIS_STEAM_SDK_DIR")
        self.python_exe = python_exe or os.environ.get("REMIS_STEAM_WORKER_PYTHON") or sys.executable

    def availability(self):
        if os.name != "nt":
            return {"ready": False, "code": "windows_runtime_required"}
        if getattr(sys, "frozen", False) and not os.environ.get("REMIS_STEAM_WORKER_PYTHON"):
            return {"ready": False, "code": "packaged_worker_not_configured"}
        if not self.sdk_dir:
            return {"ready": False, "code": "steam_sdk_not_configured"}
        root = Path(self.sdk_dir)
        if not (root / "redistributable_bin/win64/steam_api64.dll").is_file() or not (root / "public/steam/steam_api.json").is_file():
            return {"ready": False, "code": "steam_sdk_incomplete"}
        return {"ready": True, "code": "sdk_available"}

    def _invoke(self, request, work_dir):
        worker = Path(__file__).resolve().parents[2] / "steamugc_worker" / "worker.py"
        payload = json.dumps({**request, "sdk_dir": str(Path(self.sdk_dir).resolve())}, ensure_ascii=False)
        return subprocess.Popen(
            [self.python_exe, "-u", str(worker)], cwd=work_dir,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ), payload

    def probe(self, app_id, work_dir, published_file_id=None):
        availability = self.availability()
        if not availability["ready"]:
            return availability
        process, payload = self._invoke({"operation": "probe", "app_id": app_id, "published_file_id": published_file_id}, work_dir)
        try:
            stdout, _ = process.communicate(payload, timeout=30)
            events = [json.loads(line) for line in stdout.splitlines()]
            result = next((item for item in events if item.get("type") == "probe"), None)
            if process.returncode == 0 and result:
                return {key: result[key] for key in ("ready", "code", "steam_id", "published_file_id", "consumer_app_id", "owner_matches") if key in result}
        except (subprocess.TimeoutExpired, ValueError):
            process.kill()
            process.communicate()
        return {"ready": False, "code": "steam_probe_failed"}

    def publish(self, payload, work_dir, on_event):
        process, request = self._invoke({"operation": "publish", **payload}, work_dir)
        events, protocol_errors = [], []

        def consume():
            try:
                while line := process.stdout.readline(65537):
                    if len(line) > 65536:
                        raise ValueError("worker event too large")
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("invalid event")
                    if event.get("type") in {"remote_started", "created", "progress"}:
                        on_event(event)
                    if event.get("type") == "result":
                        events.append(event)
            except Exception:
                protocol_errors.append(True)
                process.kill()

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        try:
            process.stdin.write(request)
            process.stdin.close()
            process.wait(timeout=960)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        finally:
            reader.join(timeout=10)
            process.stdout.close()
        if reader.is_alive() or protocol_errors:
            return {"status": "unknown", "code": "invalid_worker_protocol"}
        if process.returncode != 0 or len(events) != 1:
            return {"status": "unknown", "code": "worker_interrupted"}
        return events[0]
