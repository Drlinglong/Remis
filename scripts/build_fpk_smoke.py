"""Build-only checks for FPK support in the frozen backend."""

import json
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


PYINSTALLER_FPK_ARGS = (
    "--collect-submodules zstandard "
    "--hidden-import tools.remis_fpk "
    "--hidden-import tools.remis_fpk.reader "
    "--hidden-import tools.remis_fpk.extraction "
    "--hidden-import zstandard"
)


def _synthetic_fpk_smoke_archive(env_python, archive_path):
    """Write a tiny compressed FLPK fixture for the packaged runtime smoke test."""
    source = b"return PlaceObj('ModDef', {'id', 'remis-build-smoke'})"
    compress_script = (
        "import sys, zstandard; "
        "sys.stdout.buffer.write(zstandard.ZstdCompressor().compress(sys.stdin.buffer.read()))"
    )
    frame = subprocess.check_output([env_python, "-c", compress_script], input=source)
    container = b"ZSTD" + struct.pack("<III", len(source), 1024, 16) + frame
    name = b"metadata.lua"
    payload_offset = 32 + 16 + len(name)
    record = (
        payload_offset.to_bytes(6, "little")
        + bytes((0x30, len(name)))
        + struct.pack("<I", len(container))
        + name
        + b"\0" * 4
    )
    archive_path.write_bytes(
        b"FLPK"
        + struct.pack("<7I", 32, 1, 32, 0, len(record), len(record), 4)
        + record
        + container
    )


def verify_frozen_fpk_support(port, env_python, request_timeout_seconds=30):
    """Exercise the frozen parser and zstandard decoder with a synthetic Mod."""
    fixture_root = Path(tempfile.mkdtemp(prefix="remis-fpk-smoke-", dir=Path.home()))
    archive_path = fixture_root / "synthetic-smoke.fpk"
    try:
        _synthetic_fpk_smoke_archive(env_python, archive_path)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/mars-pipeline/prepare/plan",
            data=json.dumps({
                "archive_path": str(archive_path),
                "name": "Remis frozen FPK smoke",
                "delivery_mode": "text_only",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=request_timeout_seconds) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Packaged backend FPK smoke verification failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if (
            result.get("mod_id") != "remis-build-smoke"
            or result.get("file_count") != 1
            or result.get("entry_count") != 0
        ):
            raise RuntimeError(
                "Packaged backend FPK smoke returned an unexpected synthetic Mod inventory."
            )
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)
