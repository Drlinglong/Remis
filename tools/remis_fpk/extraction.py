"""Safe extraction helpers for the supported FLPK profile."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .reader import (
    ArchiveError, ArchiveLimits, DEFAULT_LIMITS, _is_link_or_reparse, _payload_for_extraction,
    _read_for_extraction, inspect_archive,
)


def _validate_destination(destination: Path) -> tuple[Path, Path]:
    target = Path(os.path.abspath(destination))
    parent = target.parent
    if target.exists() or _is_link_or_reparse(target):
        raise ArchiveError("destination already exists")
    cursor = parent
    while cursor != cursor.parent:
        if _is_link_or_reparse(cursor) or not cursor.is_dir():
            raise ArchiveError("destination parent chain contains a link or non-directory")
        cursor = cursor.parent
    return target, parent


def _write_files(stage: Path, entries: list[dict[str, Any]], data: bytes,
                 index_end: int, limits: ArchiveLimits) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    total = 0
    for entry in entries:
        relative = PurePosixPath(entry["path"])
        target = stage.joinpath(*relative.parts)
        if entry["kind"] == "directory":
            target.mkdir(parents=True, exist_ok=True)
            continue
        raw = _payload_for_extraction(data, entry, index_end, limits)
        total += len(raw)
        if total > limits.total_output_bytes:
            raise ArchiveError("total extracted bytes exceed configured limit")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        manifest.append({"path": entry["path"], "size": len(raw),
                         "stored_size": entry["size"], "codec": entry["kind"],
                         "sha256": hashlib.sha256(raw).hexdigest()})
    return manifest


def extract_archive(
    path: str | Path,
    destination: str | Path,
    *,
    expected_sha256: str,
    limits: ArchiveLimits | None = None,
) -> dict[str, Any]:
    """Extract into a new destination after matching the caller's archive hash.

    The entire archive is validated before a sibling staging directory is created.
    A completed tree is atomically renamed into place, and an existing destination
    is never overwritten.
    """
    limits = limits or DEFAULT_LIMITS
    archive_path = Path(path)
    inventory = inspect_archive(archive_path, limits=limits)
    if not expected_sha256 or inventory["archive_sha256"].lower() != expected_sha256.lower():
        raise ArchiveError("archive SHA-256 does not match expected_sha256")
    target, parent = _validate_destination(Path(destination))
    data, entries, index_end = _read_for_extraction(archive_path, limits)
    if hashlib.sha256(data).hexdigest() != inventory["archive_sha256"]:
        raise ArchiveError("archive changed after validation")
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.fpk-", dir=parent))
    try:
        files = _write_files(staging, entries, data, index_end, limits)
        if target.exists() or _is_link_or_reparse(target):
            raise ArchiveError("destination appeared during extraction")
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {"archive_sha256": inventory["archive_sha256"],
            "destination": str(target), "file_count": len(files), "files": files}
