"""Synthetic format checks; no proprietary archive or Lua execution in fixtures."""
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.developer_tools import probe_mars_flpk as probe

try:
    import zstandard
except ImportError:
    zstandard = None


def record(name, offset, flags, size):
    encoded = name.encode("utf-8")
    return offset.to_bytes(6, "little") + bytes([flags, len(encoded)]) + struct.pack(
        "<I", size
    ) + encoded + b"\0" * 4


def archive(index, payload=b"", index_size=None):
    size = len(index) if index_size is None else index_size
    return b"FLPK" + struct.pack("<7I", 32, 1, 32, 0, size, len(index), 4) + index + payload


class IndexTests(unittest.TestCase):
    def test_unknown_flags_are_listed_without_decoding(self):
        data = archive(record("image.bin", 57, 0x10, 0))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "mod.fpk"
            path.write_bytes(data)
            result = probe.inspect_archive(path, None)
            self.assertEqual(result["text_candidate_count"], 0)
            self.assertEqual(result["unsupported_flag_entries"][0]["flags"], 0x10)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(len(list(Path(temp).iterdir())), 1)

    def test_child_index_cannot_read_file_payload(self):
        index = record("Code", 20, 1, 20)
        data = archive(index, record("more", 0, 0x10, 0))
        with self.assertRaises(probe.ProbeError):
            probe._parse_index(data, 32, 0, len(index), index_end=32 + len(index))

    def test_duplicate_paths_and_cycles_are_rejected(self):
        index = record("Code", 0, 0x10, 0) + record("code", 0, 0x10, 0)
        with self.assertRaises(probe.ProbeError):
            probe._parse_index(archive(index), 32, 0, len(index))
        cycle = record("Code", 0, 1, 20)
        with self.assertRaises(probe.ProbeError):
            probe._parse_index(archive(cycle), 32, 0, len(cycle))

    def test_unsafe_windows_paths_are_rejected(self):
        for name in ("..", "a/b", "a\\b", "C:foo", "NUL.lua", "con", "name.", "a?b", "a "):
            with self.subTest(name=name), self.assertRaises(probe.ProbeError):
                probe._safe_name(name.encode("utf-8"))

    def test_truncated_compression_header_fails_with_typed_error(self):
        data = b"ZSTD" + b"\0" * 8
        with self.assertRaises(probe.ProbeError):
            probe._decode_zstd_file(data, {"path": "a.lua", "offset": 0,
                                         "size": len(data), "flags": 0x30}, 0, None)


@unittest.skipUnless(zstandard, "optional zstandard diagnostic dependency is unavailable")
class CompressionTests(unittest.TestCase):
    def frame(self, text=b'return "hello"', declared=None, trailing=b""):
        compressed = zstandard.ZstdCompressor().compress(text) + trailing
        size = len(text) if declared is None else declared
        return b"ZSTD" + struct.pack("<III", size, 1024, 16) + compressed

    def decode(self, frame):
        return probe._decode_zstd_file(frame, {"path": "a.lua", "offset": 0,
                                               "size": len(frame), "flags": 0x30}, 0, zstandard)

    def test_known_frame_and_exact_reference(self):
        raw = b'return "hello"'
        frame = self.frame(raw)
        self.assertEqual(self.decode(frame), raw)
        placeholder = record("a.lua", 0, 0x30, len(frame))
        index = record("a.lua", 32 + len(placeholder), 0x30, len(frame))
        data = archive(index, frame)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "mod.fpk"
            path.write_bytes(data)
            (root / "a.lua").write_bytes(raw)
            result = probe.inspect_archive(path, root)
            self.assertEqual(result["source_comparisons"][0]["reference_match"], "exact")
            self.assertEqual(path.read_bytes(), data)

    def test_declared_size_and_trailing_frames_are_rejected(self):
        for frame in (self.frame(declared=1), self.frame(trailing=b"extra")):
            with self.subTest(frame=frame), self.assertRaises(probe.ProbeError):
                self.decode(frame)

    def test_bad_zstd_frame_is_typed_error(self):
        frame = b"ZSTD" + struct.pack("<III", 1, 1024, 16) + b"\x28\xb5\x2f\xfd"
        with self.assertRaises(probe.ProbeError):
            self.decode(frame)


if __name__ == "__main__":
    unittest.main()
