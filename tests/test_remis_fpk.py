"""Safety and format tests for the standalone FLPK package."""

from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from tools.remis_fpk import ArchiveError, extract_archive, inspect_archive

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

    def test_wrong_raw_size_or_trailing_frame_bytes_are_rejected(self):
        frame = zstandard.ZstdCompressor().compress(b"a")
        for container in (
            b"ZSTD" + struct.pack("<III", 2, 1024, 16) + frame,
            b"ZSTD" + struct.pack("<III", 1, 1024, 16) + frame + b"extra",
        ):
            data = pack_archive(record("x.lua", 48, 0x30, len(container)), container)
            with self.assertRaises(ArchiveError):
                inspect_archive_bytes(data)


class RealReferenceTests(unittest.TestCase):
    archive_path = Path(r"I:\SteamLibrary\steamapps\workshop\content\3215050\3679917456\ModContent.fpk")
    reference_root = Path(__file__).resolve().parents[1] / "source_mod" / "Exotic Minerals Expanded"

    @unittest.skipUnless(archive_path.is_file(), "provided Workshop archive is not available")
    def test_every_archive_file_matches_reference_bytes(self):
        inventory = inspect_archive(self.archive_path)
        self.assertEqual(inventory["file_count"], 56)
        self.assertEqual(inventory["archive_sha256"],
                         "6172b0f49135824271c887930c2601d9e92e36a314169756db8f78b14102e962")
        matched = 0
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
