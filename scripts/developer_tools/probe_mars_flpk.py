"""Bounded, read-only inspection of a Surviving Mars FLPK mod archive.

This diagnostic reads directory metadata and decompresses supported text files
in memory. It never imports Lua, writes extracted files, or treats unknown
entry flags as raw data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_FILE_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_ZSTD_WINDOW_KIB = 1024
MAX_ENTRIES = 50_000
MAX_DEPTH = 16
SUPPORTED_TEXT_EXTENSIONS = {".lua", ".csv", ".txt", ".xml", ".json"}
DIRECTORY_FLAG = 0x01
ZSTD_FILE_FLAG = 0x30


class ProbeError(ValueError):
    """An archive or probe input failed a supported-format safety check."""


def _safe_name(raw_name: bytes) -> str:
    try:
        name = raw_name.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProbeError("directory name is not valid UTF-8") from error
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if (not name or name in {".", ".."} or any(char in name for char in '/\\:<>"|?*')
            or any(ord(char) < 32 for char in name) or name.endswith((".", " "))
            or name.split(".", 1)[0].upper() in reserved or "\x7f" in name):
        raise ProbeError("unsafe archive path component")
    return name


def _parse_index(
    archive: bytes,
    index_base: int,
    index_offset: int,
    index_size: int,
    prefix: str = "",
    depth: int = 0,
    total_entries: list[int] | None = None,
    index_ranges: list[tuple[int, int]] | None = None,
    folded_paths: set[str] | None = None,
    index_end: int | None = None,
) -> list[dict[str, Any]]:
    if total_entries is None:
        total_entries = [0]
    if index_ranges is None:
        index_ranges = []
    if folded_paths is None:
        folded_paths = set()
    if depth > MAX_DEPTH or not 0 < index_size <= MAX_INDEX_BYTES:
        raise ProbeError("directory index exceeds depth or size limits")
    start = index_base + index_offset
    end = start + index_size
    if (start < index_base or end < start or end > len(archive)
            or (index_end is not None and end > index_end)):
        raise ProbeError("directory index range lies outside the archive")
    if any(start < prior_end and prior_start < end for prior_start, prior_end in index_ranges):
        raise ProbeError("directory index ranges overlap or form a cycle")
    index_ranges.append((start, end))

    entries: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        if end - cursor < 16:
            raise ProbeError("truncated directory record")
        offset = int.from_bytes(archive[cursor:cursor + 6], "little")
        flags = archive[cursor + 6]
        name_size = archive[cursor + 7]
        size = struct.unpack_from("<I", archive, cursor + 8)[0]
        record_end = cursor + 16 + name_size
        if record_end > end:
            raise ProbeError("directory name or trailing field exceeds index")
        name = _safe_name(archive[cursor + 12:cursor + 12 + name_size])
        trailer = struct.unpack_from("<I", archive, cursor + 12 + name_size)[0]
        path = f"{prefix}/{name}" if prefix else name
        folded = path.casefold()
        if folded in folded_paths:
            raise ProbeError("duplicate archive paths ignoring case")
        folded_paths.add(folded)
        entry: dict[str, Any] = {
            "path": path,
            "offset": offset,
            "flags": flags,
            "size": size,
            "trailer": trailer,
            "kind": "directory" if flags == DIRECTORY_FLAG else
                    "zstd_text_candidate" if flags == ZSTD_FILE_FLAG else "unsupported",
        }
        entries.append(entry)
        total_entries[0] += 1
        if total_entries[0] > MAX_ENTRIES:
            raise ProbeError("archive entry count exceeds limit")
        if flags == DIRECTORY_FLAG:
            entries.extend(_parse_index(
                archive, index_base, offset, size, path, depth + 1, total_entries,
                index_ranges, folded_paths, index_end
            ))
        cursor = record_end
    if cursor != end:
        raise ProbeError("directory index did not end on a record boundary")
    return entries


def _is_text_candidate(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in SUPPORTED_TEXT_EXTENSIONS


def _decode_zstd_file(
    archive: bytes,
    entry: dict[str, Any],
    index_end: int,
    zstandard: Any,
) -> bytes:
    offset = entry["offset"]
    compressed_size = entry["size"]
    if (entry["flags"] != ZSTD_FILE_FLAG or offset < index_end
            or compressed_size <= 0 or offset > len(archive)
            or compressed_size > len(archive) - offset):
        raise ProbeError(f"unsupported or out-of-range file entry: {entry['path']}")
    frame = archive[offset:offset + compressed_size]
    if len(frame) < 16 or frame[:4] != b"ZSTD":
        raise ProbeError(f"unsupported compression header: {entry['path']}")

    raw_size, block_size, first_chunk_offset = struct.unpack_from("<III", frame, 4)
    if raw_size <= 0 or raw_size > MAX_FILE_OUTPUT_BYTES or block_size != 1024:
        raise ProbeError(f"unsupported output/block size: {entry['path']}")
    block_count = (raw_size + block_size - 1) // block_size
    expected_table_size = 12 + 4 * block_count
    if first_chunk_offset != expected_table_size or first_chunk_offset > len(frame):
        raise ProbeError(f"invalid ZSTD chunk table: {entry['path']}")
    chunk_offsets = struct.unpack_from(f"<{block_count}I", frame, 12)
    if (not chunk_offsets or chunk_offsets[0] != first_chunk_offset
            or any(left >= right for left, right in zip(chunk_offsets, chunk_offsets[1:]))
            or chunk_offsets[-1] >= len(frame)):
        raise ProbeError(f"invalid ZSTD chunk offsets: {entry['path']}")

    decompressor = zstandard.ZstdDecompressor(max_window_size=MAX_ZSTD_WINDOW_KIB)
    chunks: list[bytes] = []
    for index, chunk_start in enumerate(chunk_offsets):
        chunk_end = chunk_offsets[index + 1] if index + 1 < block_count else len(frame)
        if chunk_end <= chunk_start or chunk_end > len(frame):
            raise ProbeError(f"invalid ZSTD chunk extent: {entry['path']}")
        compressed_chunk = frame[chunk_start:chunk_end]
        if not compressed_chunk.startswith(b"\x28\xb5\x2f\xfd"):
            raise ProbeError(f"chunk is not a standard Zstandard frame: {entry['path']}")
        expected_size = min(block_size, raw_size - index * block_size)
        try:
            frame_size = zstandard.frame_content_size(compressed_chunk)
            if frame_size != expected_size:
                raise ProbeError(f"Zstandard frame size mismatch: {entry['path']}")
            if (zstandard.get_frame_parameters(compressed_chunk).window_size
                    > MAX_ZSTD_WINDOW_KIB * 1024):
                raise ProbeError(f"Zstandard window exceeds limit: {entry['path']}")
            raw_chunk = decompressor.decompress(
                compressed_chunk, max_output_size=expected_size, allow_extra_data=False
            )
        except ProbeError:
            raise
        except (zstandard.ZstdError, ValueError) as error:
            raise ProbeError(f"Zstandard decode failed: {entry['path']}") from error
        if len(raw_chunk) != expected_size:
            raise ProbeError(f"decompressed chunk size mismatch: {entry['path']}")
        chunks.append(raw_chunk)
    result = b"".join(chunks)
    if len(result) != raw_size:
        raise ProbeError(f"decompressed file size mismatch: {entry['path']}")
    return result


def _compare_reference(path: str, raw: bytes, reference_root: Path) -> dict[str, Any]:
    candidate = reference_root.joinpath(*PurePosixPath(path).parts).resolve()
    if not candidate.is_relative_to(reference_root):
        raise ProbeError("reference path resolves outside the reference directory")
    if not candidate.is_file():
        return {"reference_match": "missing"}
    with candidate.open("rb") as stream:
        reference = stream.read(MAX_FILE_OUTPUT_BYTES + 1)
    if len(reference) > MAX_FILE_OUTPUT_BYTES:
        return {"reference_match": "reference_over_limit"}
    exact = raw == reference
    newline_match = raw.replace(b"\r\n", b"\n") == reference.replace(b"\r\n", b"\n")
    return {
        "reference_match": "exact" if exact else "newline_normalized" if newline_match else "different",
        "reference_bytes": len(reference),
        "reference_sha256": hashlib.sha256(reference).hexdigest(),
    }


def inspect_archive(archive_path: Path, reference_dir: Path | None) -> dict[str, Any]:
    path = archive_path.resolve(strict=True)
    file_size = path.stat().st_size
    if file_size < 36 or file_size > MAX_ARCHIVE_BYTES:
        raise ProbeError("archive size is outside supported limits")
    with path.open("rb") as stream:
        data = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ProbeError("archive exceeds supported input limit")
    if data[:4] != b"FLPK":
        raise ProbeError("archive magic is not FLPK")
    header_size, version, index_base, reserved, index_size, root_size, alignment = struct.unpack_from(
        "<7I", data, 4
    )
    if (header_size != 32 or version != 1 or index_base != 32 or reserved != 0
            or not 0 < index_size <= MAX_INDEX_BYTES or not 0 < root_size <= index_size
            or alignment != 4):
        raise ProbeError("header differs from the supported FLPK profile")
    index_end = index_base + index_size
    if index_end > len(data):
        raise ProbeError("directory index area lies outside the archive")
    entries = _parse_index(data, index_base, 0, root_size, index_end=index_end)
    unsupported = [entry for entry in entries if entry["kind"] == "unsupported"]
    zstd = None
    if any(entry["kind"] == "zstd_text_candidate" and _is_text_candidate(entry["path"])
           for entry in entries):
        try:
            import zstandard as zstd_module
        except ImportError as error:
            raise ProbeError("the zstandard Python package is required for text samples") from error
        zstd = zstd_module

    selected = [entry for entry in entries
                if entry["kind"] == "zstd_text_candidate" and _is_text_candidate(entry["path"])]
    comparisons = []
    total_output = 0
    for entry in selected:
        raw = _decode_zstd_file(data, entry, index_end, zstd)
        total_output += len(raw)
        if total_output > MAX_TOTAL_OUTPUT_BYTES:
            raise ProbeError("total decompressed output exceeds limit")
        result = {
            "path": entry["path"],
            "raw_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if reference_dir is not None:
            result.update(_compare_reference(entry["path"], raw, reference_dir))
        comparisons.append(result)
    return {
        "archive": str(path),
        "archive_bytes": len(data),
        "archive_sha256": hashlib.sha256(data).hexdigest(),
        "header": {"version": version, "index_base": index_base,
                   "index_size": index_size, "root_index_size": root_size,
                   "alignment": alignment},
        "entry_count": len(entries),
        "unsupported_flag_entries": unsupported,
        "text_candidate_count": len(comparisons),
        "decompressed_bytes": total_output,
        "source_comparisons": comparisons,
        "note": "Unknown flags and non-text entries are listed only; they were not decoded.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="local .fpk archive to inspect")
    parser.add_argument("--reference-dir", type=Path,
                        help="optional unpacked mod source tree for read-only comparison")
    args = parser.parse_args()
    try:
        reference_dir = args.reference_dir.resolve(strict=True) if args.reference_dir else None
        if reference_dir is not None and not reference_dir.is_dir():
            raise ProbeError("reference directory is not a directory")
        report = inspect_archive(args.archive, reference_dir)
    except (OSError, ProbeError) as error:
        print(f"probe failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
