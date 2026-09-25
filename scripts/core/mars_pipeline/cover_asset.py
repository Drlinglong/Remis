"""Read and validate optional cover art for a local source-copy package."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


MAX_COVER_BYTES = 1024 * 1024
MAX_COVER_DIMENSION = 8192
MAX_COVER_PIXELS = 25_000_000


class CoverAssetError(ValueError):
    """Raised when cover art is unsafe, unsupported, or changed since review."""


def _reject_linked_path(path: Path) -> None:
    cursor = path
    while True:
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(info.st_mode) or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ):
                raise CoverAssetError("Cover image path cannot contain a symbolic link or junction.")
        if cursor == cursor.parent:
            return
        cursor = cursor.parent


def _validate_image_header(path: Path, data: bytes) -> str:
    extension = path.suffix.lower()
    if extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if not width or not height or width > MAX_COVER_DIMENSION or height > MAX_COVER_DIMENSION:
            raise CoverAssetError("Cover image dimensions exceed the supported limit.")
        if width * height > MAX_COVER_PIXELS:
            raise CoverAssetError("Cover image pixel count exceeds the supported limit.")
        return extension
    if extension in {".jpg", ".jpeg"}:
        dimensions = _jpeg_dimensions(data)
        if dimensions:
            width, height = dimensions
            if width > MAX_COVER_DIMENSION or height > MAX_COVER_DIMENSION:
                raise CoverAssetError("Cover image dimensions exceed the supported limit.")
            if width * height > MAX_COVER_PIXELS:
                raise CoverAssetError("Cover image pixel count exceeds the supported limit.")
            return ".jpg"
    raise CoverAssetError("Cover image must be a PNG or JPEG file with a matching extension.")


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 12 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        return None
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    cursor = 2
    dimensions = None
    while cursor < len(data) - 2:
        if data[cursor] != 0xFF:
            return None
        while cursor < len(data) and data[cursor] == 0xFF:
            cursor += 1
        if cursor >= len(data):
            return None
        marker = data[cursor]
        cursor += 1
        if marker == 0xD9:
            break
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if cursor + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[cursor:cursor + 2], "big")
        if segment_length < 2 or cursor + segment_length > len(data):
            return None
        if marker in frame_markers:
            if segment_length < 8:
                return None
            height = int.from_bytes(data[cursor + 3:cursor + 5], "big")
            width = int.from_bytes(data[cursor + 5:cursor + 7], "big")
            if not width or not height:
                return None
            dimensions = (width, height)
        if marker == 0xDA:
            break
        cursor += segment_length
    return dimensions


def read_cover_snapshot(path_value: str, expected_sha256: str) -> dict[str, object]:
    """Read a bounded regular image and require the reviewed SHA-256 digest."""
    path = Path(path_value)
    if not path.is_absolute() or not expected_sha256 or len(expected_sha256) != 64:
        raise CoverAssetError("Cover image path and SHA-256 snapshot are required.")
    if any(character not in "0123456789abcdefABCDEF" for character in expected_sha256):
        raise CoverAssetError("Cover image SHA-256 snapshot is invalid.")
    _reject_linked_path(path)
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_COVER_BYTES:
            raise CoverAssetError("Cover image must be a regular file under the size limit.")
        with path.open("rb") as stream:
            data = stream.read(MAX_COVER_BYTES + 1)
        _reject_linked_path(path)
        after = path.stat()
    except OSError as error:
        raise CoverAssetError("Cover image could not be read.") from error
    before_identity = (before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev)
    after_identity = (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev)
    if (len(data) != before.st_size or len(data) > MAX_COVER_BYTES
            or before_identity != after_identity):
        raise CoverAssetError("Cover image changed while it was being inspected.")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise CoverAssetError("Cover image changed since its reviewed SHA-256 snapshot.")
    extension = _validate_image_header(path, data)
    return {"data": data, "sha256": digest, "extension": extension,
            "path": os.path.abspath(path)}
