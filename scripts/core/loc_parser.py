# scripts/core/loc_parser.py
# ---------------------------------------------------------------
# Parser i generator plików lokalizacyjnych Paradoxu (EU4, Vic3, Stellaris)

import re
from pathlib import Path

from scripts.utils import read_text_bom, write_text_bom

# Relaxed Regex: Captures key (anything before colon), version (digits after colon), and value (in quotes)
# This allows for keys like "FNG_zhernani.100.a" or even ones with strange symbols, as long as they don't have spaces/colons in the key itself.
ENTRY_RE = re.compile(r'^\s*([^:\s]+)\s*:\s*([0-9]*)\s*"(.*)"', re.MULTILINE)

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
            # Flatten JSON if needed, or assume simple key-value
            # If it's a list of objects? Or a dict?
            # Paradox metadata.json is usually a dict.
            if isinstance(data, dict):
                for k, v in data.items():
                    # Fix: key_map is a list of dicts like {'key_part': 'remis.1.t', 'line_num': 5}
                    # We need to extract the actual key string
                    entry_key = k.strip()
                    # Normalize: ensure no trailing colon (legacy consistency)
                    if entry_key.endswith(":"):
                        entry_key = entry_key[:-1].strip()
                    
                    if isinstance(v, str):
                        entries.append((entry_key, v))
                    else:
                        # Handle nested or non-string values as string representation
                        entries.append((entry_key, str(v)))
            elif isinstance(data, list):
                 # Handle list if necessary (unlikely for loc, but possible for metadata)
                 pass
        except Exception as e:
            print(f"JSON parse error: {e}")
            pass
    else:
        # YAML / Paradox Loc
        for line in read_text_bom(path).splitlines():
            match = ENTRY_RE.match(line)
            if match:
                base_key, version, value = match.groups()
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
        # JSON usually doesn't have line numbers in a meaningful way for this context
        # We'll just use 0 or index + 1
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
                base_key, version, value = match.groups()
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
    """
    rows = [header]                       # np. „l_polish:” lub „l_english:”
    for key, value in entries:
        safe = value.replace('"', r'\"')  # escape podwójnych cudzysłowów
        rows.append(f' {key}:0 "{safe}"')
    return "\n".join(rows)


def save_loc_file(path: Path, header: str, entries: list[tuple[str, str]]) -> None:
    """
    Skrót: wypisz plik na dysk, zachowując BOM.
    """
    write_text_bom(path, emit_loc_file(header, entries))
