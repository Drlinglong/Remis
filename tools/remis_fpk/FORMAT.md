# Supported FLPK profile

This reader implements the version 1 profile observed in the supplied
Surviving Mars `ModContent.fpk`. It is not a general-purpose implementation of
every FLPK variant.

The 32-byte little-endian header contains `FLPK`, header size 32, version 1,
index base 32, a zero reserved word, total index bytes, root index bytes, and
alignment 4. Index records have a 6-byte offset, one-byte flags, one-byte
UTF-8 component length, four-byte stored size, component bytes, and a four-byte
trailer. Directory offsets address nested indexes relative to byte 32.

Flags `0x01` mark directories, `0x10` mark raw file payloads, and `0x30` mark
the observed `ZSTD` container. For `0x10`, the stored bytes are emitted
unchanged. The `0x30` payload begins with `ZSTD`, followed by raw size, 1024-byte
block size, and a table of 32-bit chunk offsets. Each chunk is either one
standard Zstandard frame or an exact-length literal block. The latter mixed
block form is verified against six PNGs in the supplied sample. Every decoded
frame size, window, chunk boundary, literal block length, and aggregate output
size is checked. Any other flag, version, block size, or compression variant
raises `ArchiveError`.

The defaults cap the archive at 128 MiB, index at 8 MiB, each decoded file at
8 MiB, total decoded output at 64 MiB, entry count at 50,000, nesting at 16,
and Zstandard windows at 1 MiB. Names must be safe Windows path components and
unique ignoring case. Payloads may not overlap the index or one another.

The implementation was compared byte-for-byte against the supplied
`Exotic Minerals Expanded` unpacked reference: all 56 files (28 raw `0x10`
PNGs and 28 `0x30` files, including six mixed-block PNGs) matched byte-for-byte.
The emitted total was 9,714,338 bytes. That validates this sample profile;
other versions remain unsupported until independently verified.
