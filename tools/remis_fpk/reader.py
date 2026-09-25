"""Read and validate FLPK archives without executing their contents."""

from __future__ import annotations

import hashlib
import os
import struct
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class ArchiveError(ValueError):
    """The input is malformed, unsafe, or outside the supported FLPK profile."""


@dataclass(frozen=True)
class ArchiveLimits:
    """Resource limits applied before allocating or decompressing archive data."""

    archive_bytes: int = 128 * 1024 * 1024
    index_bytes: int = 8 * 1024 * 1024
    file_bytes: int = 8 * 1024 * 1024
    total_output_bytes: int = 64 * 1024 * 1024
    entries: int = 50_000
    depth: int = 16
    zstd_window_bytes: int = 1024 * 1024


DEFAULT_LIMITS = ArchiveLimits()
_MAGIC = b"FLPK"
_DIRECTORY = 0x01
_RAW_FILE = 0x10
_ZSTD_FILE = 0x30
_ZSTD_MAGIC = b"ZSTD"
_ZSTD_FRAME_MAGIC = b"\x28\xb5\x2f\xfd"
_BLOCK_BYTES = 1024


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            return False
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return False


def _safe_component(raw: bytes) -> str:
    try:
        name = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ArchiveError("entry name is not valid UTF-8") from error
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if (not name or name in {".", ".."} or any(ord(ch) < 32 or ord(ch) == 127 for ch in name)
            or any(ch in name for ch in '/\\:<>' + '"|?*') or name.endswith((".", " "))
            or name.split(".", 1)[0].upper() in reserved):
        raise ArchiveError("unsafe archive path component")
    return name


def _parse_index(
    data: bytes, offset: int, size: int, index_end: int, limits: ArchiveLimits,
    *, prefix: str = "", depth: int = 0, entries: list[dict[str, Any]] | None = None,
    index_ranges: list[tuple[int, int]] | None = None, path_kinds: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if entries is None:
        entries = []
    if index_ranges is None:
        index_ranges = []
    if path_kinds is None:
        path_kinds = {}
    if depth > limits.depth or size <= 0 or size > limits.index_bytes:
        raise ArchiveError("directory index exceeds depth or size limits")
    start, end = 32 + offset, 32 + offset + size
    if start < 32 or end < start or end > index_end:
        raise ArchiveError("directory index range is outside the index area")
    if any(start < prior_end and prior_start < end for prior_start, prior_end in index_ranges):
        raise ArchiveError("directory indexes overlap or form a cycle")
    index_ranges.append((start, end))
    cursor = start
    while cursor < end:
        if end - cursor < 16:
            raise ArchiveError("truncated directory record")
        payload_offset = int.from_bytes(data[cursor:cursor + 6], "little")
        flags, name_size = data[cursor + 6], data[cursor + 7]
        stored_size = struct.unpack_from("<I", data, cursor + 8)[0]
        record_end = cursor + 16 + name_size
        if record_end > end:
            raise ArchiveError("directory record exceeds index boundary")
        name = _safe_component(data[cursor + 12:cursor + 12 + name_size])
        trailer = struct.unpack_from("<I", data, cursor + 12 + name_size)[0]
        archive_path = f"{prefix}/{name}" if prefix else name
        folded = archive_path.casefold()
        kind = { _DIRECTORY: "directory", _RAW_FILE: "raw", _ZSTD_FILE: "zstd" }.get(flags)
        if kind is None:
            raise ArchiveError(f"unsupported entry flags 0x{flags:02x}: {archive_path}")
        if folded in path_kinds:
            raise ArchiveError("duplicate archive paths ignoring case")
        for parent in PurePosixPath(archive_path).parents:
            if str(parent) != "." and path_kinds.get(str(parent).casefold()) in {"raw", "zstd"}:
                raise ArchiveError("file path is also used as a directory")
        if kind != "directory" and any(existing.startswith(folded + "/") for existing in path_kinds):
            raise ArchiveError("file path conflicts with an existing directory")
        path_kinds[folded] = kind
        entry = {"path": archive_path, "offset": payload_offset, "flags": flags,
                 "size": stored_size, "trailer": trailer, "kind": kind}
        entries.append(entry)
        if len(entries) > limits.entries:
            raise ArchiveError("archive entry count exceeds limit")
        if kind == "directory":
            _parse_index(data, payload_offset, stored_size, index_end, limits,
                         prefix=archive_path, depth=depth + 1, entries=entries,
                         index_ranges=index_ranges, path_kinds=path_kinds)
        cursor = record_end
    return entries


def _decode_payload(data: bytes, entry: dict[str, Any], index_end: int,
                    limits: ArchiveLimits, zstd: Any) -> bytes:
    offset, size = entry["offset"], entry["size"]
    if size <= 0 or size > limits.file_bytes or offset < index_end or offset > len(data) or size > len(data) - offset:
        raise ArchiveError(f"file payload is outside supported bounds: {entry['path']}")
    payload = data[offset:offset + size]
    if entry["kind"] == "raw":
        return payload
    if len(payload) < 16 or payload[:4] != _ZSTD_MAGIC:
        raise ArchiveError(f"invalid Zstandard container header: {entry['path']}")
    raw_size, block_size, chunk_table_offset = struct.unpack_from("<III", payload, 4)
    if raw_size <= 0 or raw_size > limits.file_bytes or block_size != _BLOCK_BYTES:
        raise ArchiveError(f"unsupported decompressed size or block size: {entry['path']}")
    chunk_count = (raw_size + block_size - 1) // block_size
    expected_table = 12 + 4 * chunk_count
    if chunk_table_offset != expected_table or expected_table > len(payload):
        raise ArchiveError(f"invalid chunk table: {entry['path']}")
    offsets = struct.unpack_from(f"<{chunk_count}I", payload, 12)
    if (not offsets or offsets[0] != expected_table or offsets[-1] >= len(payload)
            or any(left >= right for left, right in zip(offsets, offsets[1:]))):
        raise ArchiveError(f"invalid chunk offsets: {entry['path']}")
    parts: list[bytes] = []
    decompressor = zstd.ZstdDecompressor(max_window_size=max(1, limits.zstd_window_bytes // 1024))
    for index, begin in enumerate(offsets):
        finish = offsets[index + 1] if index + 1 < chunk_count else len(payload)
        frame = payload[begin:finish]
        expected = min(block_size, raw_size - index * block_size)
        if not frame.startswith(_ZSTD_FRAME_MAGIC):
            if len(frame) == expected:
                parts.append(frame)
                continue
            raise ArchiveError(f"chunk is neither a Zstandard frame nor a raw block: {entry['path']}")
        try:
            if zstd.frame_content_size(frame) != expected:
                raise ArchiveError(f"Zstandard frame size mismatch: {entry['path']}")
            if zstd.get_frame_parameters(frame).window_size > limits.zstd_window_bytes:
                raise ArchiveError(f"Zstandard window exceeds limit: {entry['path']}")
            part = decompressor.decompress(frame, max_output_size=expected, allow_extra_data=False)
        except ArchiveError:
            raise
        except (zstd.ZstdError, ValueError) as error:
            raise ArchiveError(f"Zstandard decode failed: {entry['path']}") from error
        if len(part) != expected:
            raise ArchiveError(f"decompressed chunk size mismatch: {entry['path']}")
        parts.append(part)
    output = b"".join(parts)
    if len(output) != raw_size:
        raise ArchiveError(f"decompressed file size mismatch: {entry['path']}")
    return output


def _load(path: Path, limits: ArchiveLimits) -> tuple[bytes, list[dict[str, Any]], int]:
    supplied = Path(path)
    if _is_link_or_reparse(supplied):
        raise ArchiveError("archive path must be a regular non-link file")
    source = supplied.resolve(strict=True)
    if not source.is_file():
        raise ArchiveError("archive path must be a regular non-link file")
    size = source.stat().st_size
    if size < 32 or size > limits.archive_bytes:
        raise ArchiveError("archive size is outside configured limits")
    data = source.read_bytes()
    if len(data) != size or data[:4] != _MAGIC:
        raise ArchiveError("archive is truncated or has invalid FLPK magic")
    header_size, version, index_base, reserved, index_size, root_size, alignment = struct.unpack_from("<7I", data, 4)
    if (header_size != 32 or version != 1 or index_base != 32 or reserved != 0
            or not 0 < index_size <= limits.index_bytes or not 0 < root_size <= index_size
            or alignment != 4):
        raise ArchiveError("header differs from the supported FLPK version 1 profile")
    index_end = index_base + index_size
    if index_end > len(data):
        raise ArchiveError("index area extends beyond archive")
    entries = _parse_index(data, 0, root_size, index_end, limits)
    ranges = sorted((entry["offset"], entry["offset"] + entry["size"], entry["path"])
                    for entry in entries if entry["kind"] != "directory")
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise ArchiveError(f"file payloads overlap: {previous[2]} and {current[2]}")
    return data, entries, index_end


def inspect_archive(path: str | Path, *, limits: ArchiveLimits | None = None) -> dict[str, Any]:
    """Validate every file and return a JSON-serializable inventory with hashes."""
    limits = limits or DEFAULT_LIMITS
    data, entries, index_end = _load(Path(path), limits)
    try:
        import zstandard
    except ImportError as error:
        if any(entry["kind"] == "zstd" for entry in entries):
            raise ArchiveError("install the zstandard dependency to read this archive") from error
        zstandard = None
    total = 0
    files: list[dict[str, Any]] = []
    for entry in entries:
        if entry["kind"] == "directory":
            continue
        raw = _decode_payload(data, entry, index_end, limits, zstandard)
        total += len(raw)
        if total > limits.total_output_bytes:
            raise ArchiveError("total extracted bytes exceed configured limit")
        files.append({**entry, "stored_size": entry["size"], "size": len(raw),
                      "raw_size": len(raw), "codec": entry["kind"],
                      "sha256": hashlib.sha256(raw).hexdigest()})
    return {"format": "FLPK", "version": 1, "archive_bytes": len(data),
            "archive_sha256": hashlib.sha256(data).hexdigest(), "entry_count": len(entries),
            "file_count": len(files), "total_output_bytes": total, "files": files}


def _read_for_extraction(path: Path, limits: ArchiveLimits) -> tuple[bytes, list[dict[str, Any]], int]:
    """Internal shared entry point for extraction after inspection."""
    return _load(path, limits)


def _payload_for_extraction(data: bytes, entry: dict[str, Any], index_end: int,
                            limits: ArchiveLimits) -> bytes:
    try:
        import zstandard
    except ImportError as error:
        if entry["kind"] == "zstd":
            raise ArchiveError("install the zstandard dependency to extract this archive") from error
        zstandard = None
    return _decode_payload(data, entry, index_end, limits, zstandard)
