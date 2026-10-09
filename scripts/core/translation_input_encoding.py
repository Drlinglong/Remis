"""Unmasked source serialization for batch translation prompts.

Source values are shown to the model in full. Quotes and Paradox ``\\n``
sequences stay visible; JSON string literals only delimit each value so an
inner quote cannot be mistaken for the end of the value. Semantic Paradox
tokens are never replaced (see AGENTS.md).
"""

import json

SOURCE_VALUE_ENCODING_NOTE = (
    "\nSOURCE VALUE ENCODING:\n"
    "Each source value below is a JSON string literal. Quotation marks and \\n "
    "sequences inside it are part of the text: keep every \\n line break, translate "
    "quoted speech, and return every translation as a valid JSON string, escaping "
    "inner double quotes as \\\".\n"
)


def encode_source_value(text: str) -> str:
    return json.dumps(text or "", ensure_ascii=False)


def decode_single_text_response(raw: str) -> str:
    """Remove only a response wrapper, never semantic quotes inside the value.

    A reply that is a whole JSON string literal is decoded (so ``"\\"New\\" Dawn"``
    keeps its inner quotes). Otherwise exactly one outer pair of straight quotes
    is treated as a wrapper; anything else is returned as written.
    """
    text = (raw or "").strip()
    if len(text) < 2 or not (text.startswith('"') and text.endswith('"')):
        return text
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return text[1:-1]
    return decoded if isinstance(decoded, str) else text
