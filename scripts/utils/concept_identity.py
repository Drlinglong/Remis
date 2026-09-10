"""Comparison-only identities for Concept labels; never alter model input."""

import json
import re

_CONCEPT = re.compile(
    r"\[Concept\(\s*'(?P<key>(?:\\.|[^'\\])*)'\s*,\s*"
    r"'(?P<label>(?:\\.|[^'\\])*)'\s*\)(?P<modifier>\|[^\]]+)?\]"
)


def concept_identity(game_id: str, raw: str) -> str:
    if game_id not in {"victoria3", "ck3"}:
        return raw
    match = _CONCEPT.fullmatch(raw)
    if not match:
        return raw
    from scripts.utils.game_format_contract import parse_format_structure

    label = match["label"]
    parsed = parse_format_structure(label, game_id)
    if not parsed.balanced:
        return raw
    # Keep nested runtime expressions, icons, format identities and their binding.
    structure = [(token.kind, token.canonical, token.depth) for token in parsed.tokens]
    return "CONCEPT:" + json.dumps(
        [match["key"], match["modifier"] or "", structure], ensure_ascii=False,
    )


def variable_identities(text: str, pattern: str, game_id: str):
    from scripts.utils.game_format_contract import normalize_game_id, parse_format_structure

    game_id = normalize_game_id(game_id)
    if game_id not in {"victoria3", "ck3"}:
        return re.findall(pattern, text)
    concepts = [token for token in parse_format_structure(text, game_id).runtime_tokens
                if _CONCEPT.fullmatch(token.raw)]
    values, seen = [], set()
    for match in re.finditer(pattern, text):
        containing = next((token for token in concepts
                           if token.start <= match.start() < token.end), None)
        if containing:
            if containing.start not in seen:
                values.append(containing.canonical)
                seen.add(containing.start)
        else:
            groups = match.groups()
            values.append((groups[0] or "") if len(groups) == 1 else groups or match[0])
    return values
