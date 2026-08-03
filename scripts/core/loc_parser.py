"""Compatibility facade for the canonical Paradox localization parser."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.core.paradox_localization_parser import (
    ENTRY_PREFIX_RE,
    LocalizationEntry,
    ParseReport,
    escape_value,
    normalize_raw_value,
    parse_file,
)
from scripts.utils import read_text_bom, write_text_bom


# Kept for third-party callers and historical tests.  Production parsing uses
# ``parse_file``; this regex is only a cheap compatibility shape check.
ENTRY_RE = re.compile(r'^\s*([^:\s]+)\s*:\s*([0-9]*)\s*"(.*)"', re.MULTILINE)


def unescape_value(value: str) -> str:
    """Compatibility alias for canonical value normalization."""

    return normalize_raw_value(value)


def _classify_json_value(key: str, value: str) -> bool:
    if not value or value == key:
        return False
    return not (value.startswith("$") and value.endswith("$") and value.count("$") == 2)


def _parse_json(path: Path) -> list[tuple[str, str]]:
    try:
        data = json.loads(read_text_bom(path))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    entries: list[tuple[str, str]] = []
    for raw_key, raw_value in data.items():
        key = str(raw_key).strip().removesuffix(":").strip()
        value = raw_value if isinstance(raw_value, str) else str(raw_value)
        if _classify_json_value(key, value):
            entries.append((key, value))
    return entries


def parse_loc_file_report(path: Path) -> ParseReport:
    """Return canonical syntax, policy and diagnostic information for a file."""

    if path.suffix.lower() == ".json":
        # JSON is an archive interchange format, not Paradox localization
        # syntax.  Keep the old tuple API for it and expose an empty report.
        return ParseReport((), (), read_text_bom(path))
    return parse_file(path)


def parse_loc_file_records(path: Path) -> tuple[LocalizationEntry, ...]:
    """Return canonical entries, including policy-excluded rows."""

    return parse_loc_file_report(path).entries


def parse_loc_file(path: Path) -> list[tuple[str, str]]:
    """Return eligible ``(key, value)`` tuples for legacy consumers."""

    if path.suffix.lower() == ".json":
        return _parse_json(path)
    return [(entry.key, entry.value) for entry in parse_file(path).eligible_entries]


def parse_loc_file_with_lines(path: Path) -> list[tuple[str, str, int]]:
    """Return eligible ``(key, value, one_based_line)`` tuples."""

    if path.suffix.lower() == ".json":
        return [(key, value, index) for index, (key, value) in enumerate(_parse_json(path), 1)]
    return [entry.as_legacy_tuple() for entry in parse_file(path).eligible_entries]


def emit_loc_file(header: str, entries: list[tuple[str, str]]) -> str:
    """Serialize legacy tuple entries while using canonical quote escaping."""

    rows = [header]
    for key, value in entries:
        rows.append(f' {key}:0 "{escape_value(normalize_raw_value(value))}"')
    return "\n".join(rows)


def save_loc_file(path: Path, header: str, entries: list[tuple[str, str]]) -> None:
    """Write a legacy tuple representation with UTF-8 BOM."""

    write_text_bom(path, emit_loc_file(header, entries))
