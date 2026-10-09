"""Per-game reference for Paradox localization commands, injected on demand.

The full command tables are too large and mostly irrelevant for any one entry.
This module finds the bracket commands an entry actually uses (reusing the
format-contract tokenizer, so nesting, quoted arguments and concepts are
handled the same way as validation) and returns only those dictionary rows.
The text itself is never modified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from scripts.app_settings import CONFIG_DIR
from scripts.utils.game_format_contract import normalize_game_id, parse_format_structure


DICTIONARY_DIR = Path(CONFIG_DIR) / "localization_commands"
PROVENANCES = {"wiki", "wiki_listed", "inferred", "user"}
_PROVENANCE_HINTS = {
    "wiki_listed": " (listed on the wiki; meaning inferred from the name)",
    "inferred": " (meaning inferred from the name)",
}


@dataclass(frozen=True)
class CommandSegment:
    """One link of a bracket command chain, e.g. ``sCharacter('x')``."""

    name: str
    has_args: bool


@dataclass(frozen=True)
class CommandReference:
    name: str
    kind: str  # command | concept | unknown
    meaning: str = ""
    provenance: str = ""
    base: str = ""
    suffixes: Tuple[str, ...] = ()


@lru_cache(maxsize=None)
def load_command_dictionary(game_id: str) -> Optional[Dict]:
    """Load and validate ``<game>_v1.json``; ``None`` when the game has none."""
    path = DICTIONARY_DIR / f"{normalize_game_id(game_id)}_v1.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("commands"), dict):
        raise ValueError(f"Invalid localization command dictionary: {path.name}")
    for name, row in payload["commands"].items():
        if not row.get("meaning") or row.get("provenance") not in PROVENANCES:
            raise ValueError(f"Invalid command row {name!r} in {path.name}")
    return payload


def _split_top_level(body: str, separator: str) -> List[str]:
    parts, depth, quote, start = [], 0, None, 0
    for index, char in enumerate(body):
        if quote:
            quote = None if char == quote else quote
        elif char in {"'", '"'}:
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(body[start:index])
            start = index + 1
    parts.append(body[start:])
    return parts


def parse_command_chain(raw: str) -> Tuple[Tuple[CommandSegment, ...], str]:
    """Split ``[A.B('x').C|U]`` into segments and its ``|`` modifier string."""
    if not (raw.startswith("[") and raw.endswith("]")) or raw.startswith("[?"):
        return (), ""
    body, *modifier = _split_top_level(raw[1:-1].strip(), "|")
    segments = []
    for part in _split_top_level(body, "."):
        part = part.strip()
        name = part.split("(", 1)[0].strip()
        if name:
            segments.append(CommandSegment(name, "(" in part))
    return tuple(segments), "|".join(modifier)


def extract_command_chains(text: str, game_id: str) -> List[Tuple[Tuple[CommandSegment, ...], str]]:
    """Return command chains for every bracket runtime token in ``text``."""
    chains = []
    for token in parse_format_structure(text or "", game_id).runtime_tokens:
        segments, modifier = parse_command_chain(token.raw)
        if segments:
            chains.append((segments, modifier))
    return chains


def _resolve(name: str, dictionary: Dict) -> Optional[CommandReference]:
    commands, suffixes = dictionary["commands"], dictionary.get("suffixes", {})
    stripped: List[str] = []
    base = name
    while base not in commands:
        suffix = next((s for s in sorted(suffixes, key=len, reverse=True)
                       if base.endswith(s) and len(base) > len(s)), None)
        if suffix is None:
            return None
        stripped.insert(0, suffix)
        base = base[: -len(suffix)]
    row = commands[base]
    return CommandReference(name, "command", row["meaning"], row["provenance"], base, tuple(stripped))


def _is_concept(segments: Tuple[CommandSegment, ...], modifier: str) -> bool:
    if len(segments) != 1 or segments[0].has_args:
        return False
    name = segments[0].name
    return name.lower().startswith("concept_") or (name.islower() and "e" in modifier.lower())


def find_command_references(texts: Iterable[str], game_id: str) -> List[CommandReference]:
    """Unique references used by ``texts``, in first-seen order."""
    dictionary = load_command_dictionary(game_id)
    if dictionary is None:
        return []
    scopes = {scope.lower() for scope in dictionary.get("scopes", {})}
    found: Dict[str, CommandReference] = {}
    for text in texts:
        for segments, modifier in extract_command_chains(text, game_id):
            if _is_concept(segments, modifier):
                found.setdefault("concept", CommandReference(segments[0].name, "concept"))
                continue
            for segment in segments:
                if segment.name in found or segment.name.lower() in scopes:
                    continue
                reference = _resolve(segment.name, dictionary)
                if reference is not None:
                    found[segment.name] = reference
                elif segment.name.startswith("Get") or segment.has_args:
                    found[segment.name] = CommandReference(segment.name, "unknown")
    return list(found.values())


def _describe(reference: CommandReference, dictionary: Dict) -> str:
    if reference.kind == "unknown":
        return f"- {reference.name}: not in the reference; keep it unchanged and do not guess its output."
    line = f"- {reference.name}: {reference.meaning}"
    for suffix in reference.suffixes:
        line += f"; {suffix} = {dictionary['suffixes'][suffix]}"
    return line + _PROVENANCE_HINTS.get(reference.provenance, "")


def build_command_context(texts: Iterable[str], game_id: str, target_lang: Optional[str] = None) -> str:
    """Prompt block describing only the commands used by ``texts``; ``""`` if none."""
    references = find_command_references(texts, game_id)
    if not references:
        return ""
    dictionary = load_command_dictionary(game_id)
    lines = [f"Localization command reference ({dictionary['game_id']}):"]
    lines += [f"- {note['text']}" for note in dictionary.get("notes", [])]
    lines += [_describe(ref, dictionary) for ref in references if ref.kind != "concept"]
    lines += [f"- {note['text']}" for note in dictionary.get("language_notes", {}).get(target_lang or "", [])]
    return "\n".join(lines)


def lookup_commands(game_id: str, names: Iterable[str]) -> List[Dict[str, object]]:
    """Agent-tool lookup by command name, e.g. ``GetHerHisCap``."""
    dictionary = load_command_dictionary(game_id)
    results = []
    for name in names:
        reference = _resolve(name, dictionary) if dictionary else None
        if reference is None:
            results.append({"name": name, "found": False})
            continue
        results.append({
            "name": name, "found": True, "base": reference.base, "suffixes": list(reference.suffixes),
            "meaning": reference.meaning, "provenance": reference.provenance,
            "source": dictionary["sources"][0]["url"],
        })
    return results


__all__ = [
    "build_command_context",
    "extract_command_chains",
    "find_command_references",
    "load_command_dictionary",
    "lookup_commands",
    "parse_command_chain",
]
