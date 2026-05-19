import hashlib
import os
import sys
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict


BACKEND_STARTED_AT = datetime.now(timezone.utc).isoformat()
API_CONTRACT_VERSION = 1


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def normalize_identity_path(path: str) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


def _hash_file(hasher: "hashlib._Hash", path: str, root: str) -> None:
    rel_path = os.path.relpath(path, root).replace("\\", "/")
    hasher.update(rel_path.encode("utf-8"))
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)


def _iter_backend_source_files(root: str):
    source_roots = [
        os.path.join(root, "scripts", "core"),
        os.path.join(root, "scripts", "routers"),
        os.path.join(root, "scripts", "schemas"),
        os.path.join(root, "scripts", "shared"),
        os.path.join(root, "scripts", "utils"),
    ]
    single_files = [
        os.path.join(root, "scripts", "app_settings.py"),
        os.path.join(root, "scripts", "web_server.py"),
    ]

    for path in single_files:
        if os.path.isfile(path):
            yield path

    for source_root in source_roots:
        if not os.path.isdir(source_root):
            continue
        for dirpath, dirnames, filenames in os.walk(source_root):
            dirnames[:] = [
                name for name in dirnames
                if name not in {"__pycache__", ".pytest_cache"} and not name.startswith(".")
            ]
            for filename in filenames:
                if filename.endswith(".py"):
                    yield os.path.join(dirpath, filename)


@lru_cache(maxsize=1)
def get_backend_fingerprint() -> str:
    root = _project_root()
    hasher = hashlib.sha256()

    if getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.executable)
        stat = os.stat(executable)
        hasher.update(b"frozen")
        hasher.update(executable.encode("utf-8", errors="replace"))
        hasher.update(str(stat.st_size).encode("ascii"))
        hasher.update(str(int(stat.st_mtime)).encode("ascii"))
        return hasher.hexdigest()[:16]

    hasher.update(b"source")
    for path in sorted(set(_iter_backend_source_files(root))):
        _hash_file(hasher, path, root)
    return hasher.hexdigest()[:16]


def get_backend_identity() -> Dict[str, Any]:
    root = _project_root()
    try:
        from scripts.app_settings import VERSION
    except Exception:
        VERSION = "unknown"

    return {
        "status": "ok",
        "app": "remis",
        "pid": os.getpid(),
        "version": VERSION,
        "api_contract": API_CONTRACT_VERSION,
        "is_frozen": bool(getattr(sys, "frozen", False)),
        "app_root": root.replace("\\", "/"),
        "started_at": BACKEND_STARTED_AT,
        "backend_fingerprint": get_backend_fingerprint(),
    }


def is_reusable_backend_health(health: Dict[str, Any], current_identity: Dict[str, Any] | None = None) -> bool:
    if not isinstance(health, dict):
        return False
    if health.get("app") != "remis":
        return False

    current = current_identity or get_backend_identity()
    same_root = normalize_identity_path(health.get("app_root", "")) == normalize_identity_path(current["app_root"])
    same_contract = health.get("api_contract") == current["api_contract"]
    same_fingerprint = health.get("backend_fingerprint") == current["backend_fingerprint"]

    return same_root and same_contract and same_fingerprint
