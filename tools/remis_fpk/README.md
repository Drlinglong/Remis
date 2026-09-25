# Remis FLPK reader

`remis-fpk` is a standalone, read-only parser and safe extractor for the
observed Surviving Mars FLPK version 1 archive profile. It validates all file
payloads, including raw files and chunked Zstandard files, before extraction.
It never executes Lua or modifies the input archive.

Install from this directory with `python -m pip install .`. Then run
`remis-fpk list ModContent.fpk` to validate and print a JSON inventory. The
inventory reports the archive SHA-256. Extract only to a path that does not
already exist, and pin the input hash:

```text
remis-fpk extract ModContent.fpk unpacked-mod --expected-sha256 <sha256-from-list>
```

Python callers can use `inspect_archive(path)` and
`extract_archive(path, destination, expected_sha256=...)` from
`tools.remis_fpk`. Extraction writes a new sibling staging directory and
renames it into the requested destination only after every file is written.
The default limits are defined by `ArchiveLimits`; unsupported flags and
malformed paths fail closed. See [FORMAT.md](FORMAT.md) for supported format
details and limits.
