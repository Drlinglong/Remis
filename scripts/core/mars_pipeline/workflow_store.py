"""Persist pipeline receipts separately from projects and translation archives."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
import uuid

from scripts.app_settings import APP_DATA_DIR


def _assert_regular_path(path: Path) -> None:
    for candidate in (path, *path.parents):
        if not candidate.exists() and not candidate.is_symlink():
            continue
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Pipeline storage cannot traverse links or junctions")


def root() -> Path:
    path = Path(APP_DATA_DIR) / "mars_pipeline"
    _assert_regular_path(path)
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError("Pipeline storage must not be a redirected directory")
    return path


def run_path(run_id: str) -> Path:
    if not re.fullmatch(r"plan_[a-f0-9]{32}", run_id):
        raise ValueError("Invalid pipeline run identity")
    path = root() / "runs" / run_id
    _assert_regular_path(path)
    return path


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def save_receipt(run_id: str, value: dict) -> None:
    directory = run_path(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "receipt.json"
    _assert_regular_path(target)
    temporary = directory / f".receipt-{uuid.uuid4().hex}.json"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def read_receipt(run_id: str) -> dict:
    path = run_path(run_id) / "receipt.json"
    _assert_regular_path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def project_receipt(project_id: str) -> dict | None:
    directory = root() / "runs"
    _assert_regular_path(directory)
    for path in sorted(directory.glob("plan_*/receipt.json")):
        value = read_receipt(path.parent.name)
        if value.get("project_id") == project_id and value.get("status") == "prepared":
            return value
    return None
