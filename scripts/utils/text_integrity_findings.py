"""Review-only mechanical findings for quotes and Paradox line breaks.

These checks never block a write and never enter the model repair queue: an
odd quote count or a changed line-break count can be a legitimate translation
choice, so a human decides.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Characters that open or close a quotation; straight and curly double quotes
# are counted by parity because “ closes in German but opens in English.
_PARITY_QUOTES = ('"', "“", "”", "„")
_BRACKET_QUOTES = (("«", "»"), ("「", "」"), ("『", "』"))

REVIEW_ONLY_TEXT_INTEGRITY_CODES = frozenset({
    "validation_unpaired_quotes",
    "validation_line_break_count_mismatch",
})


def quotes_paired(text: str) -> bool:
    """Return whether every quotation mark in ``text`` has a partner."""
    value = (text or "").replace('\\"', '"')
    if sum(value.count(quote) for quote in _PARITY_QUOTES) % 2:
        return False
    return all(value.count(opener) == value.count(closer) for opener, closer in _BRACKET_QUOTES)


def line_break_count(text: str) -> int:
    """Count Paradox literal ``\\n`` sequences plus any real newline characters."""
    value = text or ""
    return value.count("\\n") + value.count("\n")


def _review_finding(code: str, default_message: str, details: str) -> Dict[str, Any]:
    return {
        "code": code,
        "default_message": default_message,
        "classification": "possible_reasonable_variation",
        "blocking": False,
        "repair_queue": False,
        "review_queue": True,
        "details": details,
    }


def text_integrity_findings(source_text: str | None, target_text: str | None) -> List[Dict[str, Any]]:
    """Compare a translated value with its source; findings are review-only."""
    if source_text is None or target_text is None:
        return []
    findings: List[Dict[str, Any]] = []
    if quotes_paired(source_text) and not quotes_paired(target_text):
        findings.append(_review_finding(
            "validation_unpaired_quotes",
            "Target quotation marks are unpaired.",
            "The source quotes pair up but the target has an unmatched quotation mark. "
            "Review the quoted span; quotes were left unstyled.",
        ))
    source_breaks = line_break_count(source_text)
    target_breaks = line_break_count(target_text)
    if source_breaks != target_breaks:
        findings.append(_review_finding(
            "validation_line_break_count_mismatch",
            "Line break count differs from the source.",
            f"Source has {source_breaks} \\n line breaks; target has {target_breaks}. "
            "Check for dropped or added paragraph breaks.",
        ))
    return findings


__all__ = [
    "REVIEW_ONLY_TEXT_INTEGRITY_CODES",
    "line_break_count",
    "quotes_paired",
    "text_integrity_findings",
]
