# scripts/core/loc_parser.py
# ---------------------------------------------------------------
# Parser i generator plików lokalizacyjnych Paradoxu (EU4, Vic3, Stellaris)
# Fix #139: Correct quote escaping for HOI4 loc files

import re
from pathlib import Path

from scripts.utils import read_text_bom, write_text_bom

# Relaxed Regex: Captures key (anything before colon), version (digits after colon), and value (in quotes)
# This allows for keys like "FNG_zhernani.100.a" or even ones with strange symbols, as long as they don't have spaces/colons in the key itself.
ENTRY_RE = re.compile(r'^\s*([^:\s]+)\s*:\s*([0-9]*)\s*"(.*)"', re.MULTILINE)


def unescape_value(value: str) -> str:
    """
    Fix #139: Unescape Paradox YAML values before processing.
    Converts escaped quotes \\" back to " so that:
    1. Values starting with \\" are not treated as empty and skipped.
    2. emit_loc_file does not double-escape already-escaped quotes.
    """
    return value.replace('\\"', '"')


def parse_loc_file(path: Path) -> list[tuple[str, str]]:
    """
    Wczytaj plik .yml lub .json i zwróć listę krotek (key, text).
    UTF-8 + BOM obsługiwane przez read_text_bom().
    """
    entries: list[tuple[str, str]] = []
    
    if path.suffix.lower() == '.json':
        import json
        try:
            content = read_text_bom(path)
            data = json.loads(content)
            if isinstance(data, dict):
                for k, v in data.items():
                    entry_key = k.strip()
                    if entry_key.endswith(":"):
                        entry_key = entry_key[:-1].strip()
                    
                    if isinstance(v, str):
                        entries.append((entry_key, v))
                    else:
                        entries.append((entry_key, str(v)))
            elif isinstance(data, list):
                 pass
        except Exception as e:
            print(f"JSON parse error: {e}")
            pass
    else:
        # YAML / Paradox Loc
        for line in read_text_bom(path).splitlines():
            match = ENTRY_RE.match(line)
            if match:
                base_key, version, raw_value = match.groups()
                # Fix #139: unescape before filtering so \"text\" is not treated as empty
                value = unescape_value(raw_value)
                # Universal Normalization: Strip spaces and recombine to 'key:version' or just 'key'
                full_key = f"{base_key.strip()}:{version.strip()}" if version.strip() else base_key.strip()
                
                # --- [UNIFICATION] Filtering Logic matching QuoteExtractor ---
                # 1. Skip if value is same as key (self-referencing)
                if full_key == value:
                    continue
                
                # 2. Skip if value is empty
                if not value:
                    continue
                
                # 3. Skip if value is a pure variable (e.g. $VAR$)
                if value.startswith('$') and value.endswith('$') and value.count('$') == 2:
                    continue
                
                entries.append((full_key, value))
    return entries


def parse_loc_file_with_lines(path: Path) -> list[tuple[str, str, int]]:
    """
    Same as parse_loc_file but returns (key, value, line_number).
    Line numbers are 1-based.
    """
    entries: list[tuple[str, str, int]] = []
    
    if path.suffix.lower() == '.json':
        import json
        try:
            content = read_text_bom(path)
            data = json.loads(content)
            if isinstance(data, dict):
                for i, (k, v) in enumerate(data.items()):
                    val = str(v)
                    entries.append((k, val, i + 1))
        except Exception:
            pass
    else:
        # YAML / Paradox Loc
        lines = read_text_bom(path).splitlines()
        for i, line in enumerate(lines):
            match = ENTRY_RE.match(line)
            if match:
                base_key, version, raw_value = match.groups()
                # Fix #139: unescape before filtering
                value = unescape_value(raw_value)
                # Universal Normalization: Strip spaces and recombine
                full_key = f"{base_key.strip()}:{version.strip()}" if version.strip() else base_key.strip()

                # --- [UNIFICATION] Filtering Logic matching QuoteExtractor ---
                if full_key == value:
                    continue
                if not value:
                    continue
                if value.startswith('$') and value.endswith('$') and value.count('$') == 2:
                    continue

                entries.append((full_key, value, i + 1))
    return entries


def emit_loc_file(header: str, entries: list[tuple[str, str]]) -> str:
    """
    Zamień listę krotek z powrotem na tekst pliku lokalizacyjnego.
    Fix #139: Unescape before re-escaping to prevent double-escaping roundtrip.
    """
    rows = [header]                       # np. „l_polish:” lub „l_english:”
    for key, value in entries:
        # Fix #139: unescape first so already-escaped quotes are not double-escaped
        unescaped = unescape_value(value)
        safe = unescaped.replace('"', '\\"')  # escape podwójnych cudzysłowów
        rows.append(f' {key}:0 "{safe}"')
    return "\n".join(rows)


def save_loc_file(path: Path, header: str, entries: list[tuple[str, str]]) -> None:
    """
    Skrót: wypisz plik na dysk, zachowując BOM.
    """
    write_text_bom(path, emit_loc_file(header, entries))
