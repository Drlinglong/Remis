# scripts/utils/text_clean.py
# ---------------------------------------------------------------
"""
Narzędzia do „czyszczenia” tekstu na potrzeby lokalizacji Paradox:

• strip_pl_diacritics(txt) – usuwa polskie znaki diakrytyczne
  (ą Ą ę Ę ó Ó ł Ł ś Ś ć Ć ń Ń ż Ż ź Ź) zachowując całą resztę bez zmian.
  Wywoływana automatycznie, jeśli w GAME_PROFILES dana gra ma
      "strip_pl_diacritics": True

• strip_outer_quotes(txt)  – odcina **pojedynczą** zewnętrzną parę
  cudzysłowów / „” / «» (częsty artefakt LLM-ów) pozostawiając
  cytaty wewnętrzne nietknięte.  
  Stosowana tuż po otrzymaniu odpowiedzi z modelu, dzięki czemu
  pliki .yml nie zawierają typograficznych znaków, które psują
  parser EU4.
"""

import re

# --- Mapa zamian 1-do-1 (ogonków) ------------------------------
DIACRITIC_MAP = str.maketrans({
    "ł": "l", "Ł": "L",
    "ą": "a", "Ą": "A",
    "ę": "e", "Ę": "E",
    "ś": "s", "Ś": "S",
    "ć": "c", "Ć": "C",
    "ń": "n", "Ń": "N",
    "ó": "o", "Ó": "O",
    "ż": "z", "Ż": "Z",
    "ź": "z", "Ź": "Z",
})

def strip_pl_diacritics(txt: str) -> str:
    """
    Zwraca kopię `txt` z usuniętymi polskimi ogonkami.
    Szybsze niż unicodedata.normalize() i nie rusza innych znaków.
    """
    if not txt:
        return txt
    return txt.translate(DIACRITIC_MAP)

# --- Pary cudzysłowów do wycięcia -----------------------------
QUOTE_PAIRS = [
    ('"', '"'),
    ("'", "'"),
    ('„', '”'),
    ('«', '»'),
]
def strip_outer_quotes(txt: str) -> str:
    """
    Usuwa **jedną** zewnętrzną parę cudzysłowów, jeśli tekst
    zaczyna się i kończy pasującymi znakami cudzysłowu.
    Pozostawia cytaty wewnętrzne (np. That's, O'Neil) nietknięte.
    """
    if not txt:
        return txt
    txt = txt.strip()
    if len(txt) < 2:
        return txt

    for open_quote, close_quote in QUOTE_PAIRS:
        if txt.startswith(open_quote) and txt.endswith(close_quote):
            return txt[1:-1].strip()

    return txt


# --- Model output normalization -----------------------------------
# Source text reaches the model unmasked (quotes and ``\n`` stay visible). The
# helpers below only normalize what comes back.

# Legacy input masks, retired 2026-10-09. Kept only so archived raw model
# outputs (checkpoints, Model Arena history, benchmark replays) still parse.
# Remove LEGACY_MASK_* and restore_legacy_mask_tokens once no supported
# archive replays raw outputs produced before that date, i.e. a scan of the
# archived raw responses for "_QT_" / "_NL_" returns zero matches.
LEGACY_MASK_NEWLINE = "[[_NL_]]"
LEGACY_MASK_QUOTE = "[[_QT_]]"
_LEGACY_BARE_TOKENS = {
    "QT_": '"', "_QT_": '"', "[_QT_]": '"',
    "NL_": "\\n", "_NL_": "\\n", "[_NL_]": "\\n",
}
# Accepts well-formed and malformed fragments seen in history, e.g.
# "[[_QT_]]", "[[ _QT_ ]]", "[ [_QT_]]", "[_QT_]]", "[[_QT_]", "_QT_]]".
_LEGACY_TOKEN_TEMPLATE = (
    r"(?:\[\s*){{1,2}}_{kind}_(?:\s*\]){{0,2}}"
    r"|(?<![\w\[])_{kind}_(?:\s*\]){{1,2}}"
)
_LEGACY_QUOTE = re.compile(_LEGACY_TOKEN_TEMPLATE.format(kind="QT"))
# Older models padded newline masks with spaces; one space per side is dropped.
_LEGACY_NEWLINE = re.compile(r" ?(?:" + _LEGACY_TOKEN_TEMPLATE.format(kind="NL") + r") ?")

# --- Paradox Language Quote Standards --------------------------
# Maps target_lang code to (Open_Quote, Close_Quote)
QUOTE_STYLES = {
    # Asian Languages (CJK)
    "zh": ("“", "”"),       # Simp Chinese
    "zh-CN": ("“", "”"),
    "ko": ("“", "”"),       # Korean (Standard)
    "ja": ("「", "」"),      # Japanese (Corner brackets are standard in games)

    # European - Angle Brackets (Guillemets)
    "fr": ("« ", " »"),     # French (With non-breaking space usually)
    "ru": ("«", "»"),       # Russian

    # European - Low-High
    "de": ("„", "“"),       # German
    "pl": ("„", "”"),       # Polish

    # Standard (English, Spanish, Portuguese, Turkish)
    "en": ("“", "”"),
    "es": ("“", "”"),
    "pt": ("“", "”"),
    "tr": ("“", "”"),
}
# Paradox runtime tokens are never restyled: quotes inside them are syntax.
_PROTECTED_QUOTE_SPAN = re.compile(r"\[[^\]]*\]|\$[^$\s]*\$")


def restore_legacy_mask_tokens(text: str) -> str:
    """Compatibility restore: legacy masks become a straight quote or literal ``\\n``."""
    if not text or "QT_" not in text and "NL_" not in text:
        return text
    bare = _LEGACY_BARE_TOKENS.get(text.strip())
    if bare is not None:
        return bare
    text = _LEGACY_NEWLINE.sub(lambda _match: "\\n", text)
    return _LEGACY_QUOTE.sub('"', text)


def quote_style_for(target_lang: str | None):
    """Return the configured (open, close) pair, trying the base language code."""
    code = (target_lang or "").strip()
    if code in QUOTE_STYLES:
        return QUOTE_STYLES[code]
    base = re.split(r"[-_]", code, maxsplit=1)[0]
    return QUOTE_STYLES.get(base)


def _unambiguous_quote_positions(text: str) -> list[int] | None:
    positions = [index for index, char in enumerate(text) if char == '"']
    if not positions or len(positions) % 2:
        return None
    if any(index > 0 and text[index - 1] == "\\" for index in positions):
        return None
    for span in _PROTECTED_QUOTE_SPAN.finditer(text):
        if any(span.start() <= index < span.end() for index in positions):
            return None
    for open_index, close_index in zip(positions[::2], positions[1::2]):
        if close_index == open_index + 1:
            return None
        if text[open_index + 1].isspace() or text[close_index - 1].isspace():
            return None
    return positions


def apply_quote_style(text: str, target_lang: str | None) -> str:
    """Style straight double quotes only when every quote pairs unambiguously."""
    style = quote_style_for(target_lang)
    if not text or not style:
        return text
    positions = _unambiguous_quote_positions(text)
    if positions is None:
        return text
    open_q, close_q = style
    styled = []
    previous = 0
    for order, index in enumerate(positions):
        styled.append(text[previous:index])
        styled.append(open_q if order % 2 == 0 else close_q)
        previous = index + 1
    styled.append(text[previous:])
    return "".join(styled)


def normalize_model_output(text: str, target_lang: str | None) -> str:
    """Normalize one translated value returned by a model.

    1. Restore legacy ``[[_QT_]]`` / ``[[_NL_]]`` fragments (compatibility).
    2. Convert real newline characters to the literal ``\\n`` Paradox expects.
    3. Apply the target-language quote style when quotes pair unambiguously;
       otherwise leave quotes unchanged for the review-only quote finding.
    """
    if not text:
        return text
    text = restore_legacy_mask_tokens(text)
    text = text.replace("\r\n", "\n").replace("\n", "\\n")
    return apply_quote_style(text, target_lang)
