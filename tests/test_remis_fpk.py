"""Safety and format tests for the standalone FLPK package."""

from __future__ import annotations

import hashlib
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path as RealPath
from pathlib import Path
from unittest.mock import patch

from tools.remis_fpk import ArchiveError, ArchiveLimits, extract_archive, inspect_archive
from tools.remis_fpk import reader as reader_module

try:
    import zstandard
except ImportError:
    zstandard = None


def record(name: str, offset: int, flags: int, size: int) -> bytes:
    encoded = name.encode("utf-8")
    return (offset.to_bytes(6, "little") + bytes((flags, len(encoded)))
            + struct.pack("<I", size) + encoded + b"\0" * 4)


def pack_archive(index: bytes, payload: bytes = b"") -> bytes:
    header = b"FLPK" + struct.pack("<7I", 32, 1, 32, 0, len(index), len(index), 4)
    return header + index + payload


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _synthetic_png() -> bytes:
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\0\xff\x00\x7f\xff")
    text = b"Comment\0" + b"x" * 1200
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", pixels)
        + _png_chunk(b"tEXt", text)
        + _png_chunk(b"IEND", b"")
    )


class RawProfileTests(unittest.TestCase):
    def write_archive(self, root: Path, data: bytes) -> Path:
        path = root / "mod.fpk"
        path.write_bytes(data)
        return path

    def test_raw_file_inventory_and_extraction_with_hash_pin(self):
        raw = b"\x89PNG\r\n\x1a\nimage"
        placeholder = record("icon.png", 0, 0x10, len(raw))
        start = 32 + len(placeholder)
        data = pack_archive(record("icon.png", start, 0x10, len(raw)), raw)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.write_archive(root, data)
            inventory = inspect_archive(archive)
            self.assertEqual(inventory["file_count"], 1)
            self.assertEqual(inventory["files"][0]["codec"], "raw")
            target = root / "out"
            manifest = extract_archive(archive, target,
                                       expected_sha256=inventory["archive_sha256"])
            self.assertEqual((target / "icon.png").read_bytes(), raw)
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_unknown_flags_are_rejected_without_writing(self):
        path_record = record("thing.bin", 48, 0x20, 1)
        data = pack_archive(path_record, b"x")
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.write_archive(Path(temporary), data)
            with self.assertRaises(ArchiveError):
                inspect_archive(archive)
            self.assertEqual(archive.read_bytes(), data)

    def test_unsafe_names_duplicates_and_payload_overlap_fail_closed(self):
        for name in ("../x", "a\\b", "NUL.txt", "bad.", "bad "):
            with self.subTest(name=name), self.assertRaises(ArchiveError):
                inspect_archive_bytes(pack_archive(record(name, 48, 0x10, 1)))
        duplicate = record("A", 64, 0x10, 1) + record("a", 65, 0x10, 1)
        with self.assertRaises(ArchiveError):
            inspect_archive_bytes(pack_archive(duplicate, b"xy"))
        overlap = record("one", 64, 0x10, 2) + record("two", 65, 0x10, 2)
        with self.assertRaises(ArchiveError):
            inspect_archive_bytes(pack_archive(overlap, b"xy"))

    def test_bad_hash_and_existing_destination_do_not_extract(self):
        raw = b"x"
        record_bytes = record("x.txt", 32 + 16 + len("x.txt"), 0x10, 1)
        data = pack_archive(record_bytes, raw)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.write_archive(root, data)
            target = root / "target"
            with self.assertRaises(ArchiveError):
                extract_archive(archive, target, expected_sha256="0" * 64)
            self.assertFalse(target.exists())
            target.mkdir()
            with self.assertRaises(ArchiveError):
                extract_archive(archive, target, expected_sha256=hashlib.sha256(data).hexdigest())
            self.assertEqual(list(target.iterdir()), [])

    def test_archive_growth_after_stat_is_read_with_a_hard_bound(self):
        record_bytes = record("x.txt", 32 + 16 + len("x.txt"), 0x10, 1)
        data = pack_archive(record_bytes, b"x")
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.write_archive(Path(temporary), data)
            requested_sizes = []

            class GrowingReader:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    self.stream.close()

                def fileno(self):
                    return self.stream.fileno()

                def read(self, size=-1):
                    requested_sizes.append(size)
                    data = self.stream.read(size)
                    # Simulate growth at read time without OS-specific append behavior.
                    return data + b"x" * max(0, size - len(data))

            class GrowingPath:
                def __init__(self, path):
                    self.path = RealPath(path)

                def __fspath__(self):
                    return os.fspath(self.path)

                def is_symlink(self):
                    return self.path.is_symlink()

                def lstat(self):
                    return self.path.lstat()

                def resolve(self, *, strict=False):
                    self.path = self.path.resolve(strict=strict)
                    return self

                def is_file(self):
                    return self.path.is_file()

                def stat(self):
                    return self.path.stat()

                def open(self, mode="r", *args, **kwargs):
                    return GrowingReader(self.path.open(mode, *args, **kwargs))

            with patch.object(reader_module, "Path", GrowingPath):
                with self.assertRaises(ArchiveError):
                    inspect_archive(archive, limits=ArchiveLimits(archive_bytes=128))
            self.assertEqual(requested_sizes, [129])


def inspect_archive_bytes(data: bytes) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "sample.fpk"
        path.write_bytes(data)
        return inspect_archive(path)


@unittest.skipUnless(zstandard, "zstandard dependency is unavailable")
class ZstandardProfileTests(unittest.TestCase):
    def test_chunked_zstd_file_round_trips(self):
        raw = b"return 'mars'"
        frame = zstandard.ZstdCompressor().compress(raw)
        container = b"ZSTD" + struct.pack("<III", len(raw), 1024, 16) + frame
        item = record("code.lua", 0, 0x30, len(container))
        start = 32 + len(item)
        data = pack_archive(record("code.lua", start, 0x30, len(container)), container)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "mod.fpk"
            archive.write_bytes(data)
            inventory = inspect_archive(archive)
            target = root / "out"
            extract_archive(archive, target,
                            expected_sha256=inventory["archive_sha256"])
            self.assertEqual((target / "code.lua").read_bytes(), raw)

    def test_mixed_compressed_and_literal_chunks_extract_synthetic_png(self):
        raw = _synthetic_png()
        first_block, literal_tail = raw[:1024], raw[1024:]
        self.assertTrue(literal_tail)
        self.assertLess(len(literal_tail), 1024)
        frame = zstandard.ZstdCompressor().compress(first_block)
        second_offset = 20 + len(frame)
        container = (
            b"ZSTD"
            + struct.pack("<II", len(raw), 1024)
            + struct.pack("<II", 20, second_offset)
            + frame
            + literal_tail
        )
        item = record("preview.png", 0, 0x30, len(container))
        start = 32 + len(item)
        data = pack_archive(record("preview.png", start, 0x30, len(container)), container)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "mixed-image.fpk"
            archive.write_bytes(data)
            inventory = inspect_archive(archive)
            destination = root / "out"
            extract_archive(archive, destination,
                            expected_sha256=inventory["archive_sha256"])
            emitted = (destination / "preview.png").read_bytes()
            self.assertEqual(emitted, raw)
            self.assertEqual(emitted[:8], b"\x89PNG\r\n\x1a\n")
            cursor = 8
            chunk_types = []
            while cursor < len(emitted):
                size = struct.unpack_from(">I", emitted, cursor)[0]
                kind = emitted[cursor + 4:cursor + 8]
                payload_start = cursor + 8
                payload = emitted[payload_start:payload_start + size]
                expected_crc = struct.unpack_from(">I", emitted, payload_start + size)[0]
                self.assertEqual(zlib.crc32(kind + payload) & 0xFFFFFFFF, expected_crc)
                chunk_types.append(kind)
                cursor = payload_start + size + 4
            self.assertEqual(chunk_types, [b"IHDR", b"IDAT", b"tEXt", b"IEND"])

    def test_wrong_raw_size_or_trailing_frame_bytes_are_rejected(self):
        frame = zstandard.ZstdCompressor().compress(b"a")
        for container in (
            b"ZSTD" + struct.pack("<III", 2, 1024, 16) + frame,
            b"ZSTD" + struct.pack("<III", 1, 1024, 16) + frame + b"extra",
        ):
            item = record("x.lua", 0, 0x30, len(container))
            start = 32 + len(item)
            index = record("x.lua", start, 0x30, len(container))
            data = pack_archive(index, container)
            with self.assertRaises(ArchiveError):
                inspect_archive_bytes(data)


class RealReferenceTests(unittest.TestCase):
    archive_path = Path(os.environ.get("REMIS_FLPK_REFERENCE_ARCHIVE", ""))
    reference_root = Path(os.environ.get("REMIS_FLPK_REFERENCE_DIR", ""))
    enabled = os.environ.get("REMIS_FLPK_RUN_REFERENCE_TEST") == "1"

    @unittest.skipUnless(
        enabled and archive_path.is_file() and reference_root.is_dir(),
        "set REMIS_FLPK_RUN_REFERENCE_TEST=1 and provide both reference archive and complete reference directory",
    )
    def test_every_archive_file_matches_reference_bytes(self):
        inventory = inspect_archive(self.archive_path)
        self.assertEqual(inventory["file_count"], 56)
        self.assertEqual(inventory["archive_sha256"],
                         "6172b0f49135824271c887930c2601d9e92e36a314169756db8f78b14102e962")
        matched = 0
        reference_files = {
            path.relative_to(self.reference_root).as_posix()
            for path in self.reference_root.rglob("*") if path.is_file()
        }
        self.assertEqual(reference_files, {item["path"] for item in inventory["files"]})
        with tempfile.TemporaryDirectory() as temporary:
            extracted = Path(temporary) / "unpacked"
            extract_archive(self.archive_path, extracted,
                            expected_sha256=inventory["archive_sha256"])
            for item in inventory["files"]:
                reference = self.reference_root.joinpath(*item["path"].split("/"))
                emitted = extracted.joinpath(*item["path"].split("/"))
                self.assertTrue(reference.is_file(), item["path"])
                self.assertTrue(emitted.is_file(), item["path"])
                reference_bytes = reference.read_bytes()
                emitted_bytes = emitted.read_bytes()
                self.assertEqual(len(reference_bytes), item["size"], item["path"])
                self.assertEqual(emitted_bytes, reference_bytes, item["path"])
                self.assertEqual(hashlib.sha256(emitted_bytes).hexdigest(), item["sha256"], item["path"])
                matched += len(emitted_bytes)
        self.assertEqual(matched, inventory["total_output_bytes"])


if __name__ == "__main__":
    unittest.main()
