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

# --- Token Masking Constants -----------------------------------
MASK_NEWLINE = "[[_NL_]]"
MASK_QUOTE   = "[[_QT_]]"

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

    # Standard / Fallback (English, Spanish, Portuguese, Turkish)
    "en": ("“", "”"), 
    "es": ("“", "”"),
    "pt": ("“", "”"),
    "tr": ("“", "”"),
    "default": ("\\\"", "\\\"") # Fallback: Escaped straight quote
}

def mask_special_tokens(text: str) -> str:
    """
    Replaces special characters with neutral tokens to prevent LLM formatting hallucinations.
    1. Newlines -> [[_NL_]]
    2. All quotes -> [[_QT_]]
    """
    if not text:
        return text
        
    # 1. Protect Newlines
    # We replace the actual newline character with the token
    text = text.replace("\n", MASK_NEWLINE)
    
    # 2. Flatten Quotes -> [[_QT_]]
    # Treat all variations as a generic "quote boundary"
    text = text.replace("\"", MASK_QUOTE)
    text = text.replace("“", MASK_QUOTE).replace("”", MASK_QUOTE)
    text = text.replace("«", MASK_QUOTE).replace("»", MASK_QUOTE)
    text = text.replace("„", MASK_QUOTE)
    
    return text

def restore_special_tokens(text: str, target_lang: str) -> str:
    """
    Restores special tokens to their language-specific forms.
    1. [[_NL_]] -> \\n (Escaped newline for Paradox files)
    2. [[_QT_]] -> Context-aware quotes (Flip-Flop logic)
    """
    if not text:
        return text

    import re
    # Normalize variants with spaces (e.g. [[ _NL_ ]], [[_QT_ ]]) to standard tokens
    text = re.sub(r'\[\[\s*_NL_\s*\]\]', MASK_NEWLINE, text)
    text = re.sub(r'\[\[\s*_QT_\s*\]\]', MASK_QUOTE, text)

    # 1. Restore Newlines
    # Paradox localization files usually expect escaped newlines (\n)
    # Clean up spaces LLM might add around newline masks FIRST
    text = text.replace(f" {MASK_NEWLINE} ", "\\n")
    text = text.replace(f" {MASK_NEWLINE}", "\\n")
    text = text.replace(f"{MASK_NEWLINE} ", "\\n")
    # Finally replace the bare token
    text = text.replace(MASK_NEWLINE, "\\n")

    # 2. Restore Quotes (Context Aware)
    if MASK_QUOTE in text:
        # Get style for this language, default to generic escaped quotes
        # Handle regional codes like 'zh-Hans' -> 'zh'
        lang_key = target_lang.split('_')[0] if '_' in target_lang else target_lang
        open_q, close_q = QUOTE_STYLES.get(lang_key, QUOTE_STYLES["default"])
        
        # Flip-Flop Replacement Logic
        # First instance -> Open, Second -> Close, Third -> Open...
        parts = text.split(MASK_QUOTE)
        restored_text = ""
        
        for i, part in enumerate(parts):
            restored_text += part
            # If we are not at the last part, we need to add a quote
            if i < len(parts) - 1:
                if i % 2 == 0:
                    restored_text += open_q  # Even index (0, 2...) follows an Open Quote
                else:
                    restored_text += close_q # Odd index (1, 3...) follows a Close Quote
        
        text = restored_text

    # 3. Final Safety: Escape any remaining actual newlines
    # If the LLM returned actual newlines instead of tokens, we must escape them
    # to prevent breaking the YAML-like structure.
    text = text.replace("\n", "\\n")

    return text
