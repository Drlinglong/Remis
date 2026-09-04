"""Shared, lossless structure checks for Paradox localization values.

The legacy validators compare marker counts.  That is useful as a cheap signal,
but it cannot distinguish ``#italic`` from ``#b`` or detect a formatting span
being rebound to a different runtime token.  This module deliberately keeps the
original lexemes and visible text intact while exposing a small structural model
that each game's validator can consume.

This is not a translation normalizer.  It never replaces protected text with an
opaque placeholder and it never edits either input string.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


GAME_ALIASES = {
    "1": "victoria3",
    "victoria3": "victoria3",
    "vic3": "victoria3",
    "2": "stellaris",
    "stellaris": "stellaris",
    "3": "eu4",
    "eu4": "eu4",
    "4": "hoi4",
    "hoi4": "hoi4",
    "5": "ck3",
    "ck3": "ck3",
    "6": "eu5",
    "eu5": "eu5",
}


@dataclass(frozen=True)
class GameFormatContract:
    """Game-specific delimiters and protected-token policy."""

    game_id: str
    format_family: str
    format_open: str
    format_close: str
    icon_family: Optional[str] = None
    flag_family: Optional[str] = None
    allow_ck3_concept_label_translation: bool = False


GAME_FORMAT_CONTRACTS = {
    "victoria3": GameFormatContract(
        game_id="victoria3",
        format_family="hash",
        format_open="#",
        format_close="#!",
        icon_family="at_bang",
    ),
    "ck3": GameFormatContract(
        game_id="ck3",
        format_family="hash",
        format_open="#",
        format_close="#!",
        icon_family="at_bang",
        allow_ck3_concept_label_translation=True,
    ),
    "hoi4": GameFormatContract(
        game_id="hoi4",
        format_family="section",
        format_open="§",
        format_close="§!",
        icon_family="pound",
        flag_family="at_bare",
    ),
    "stellaris": GameFormatContract(
        game_id="stellaris",
        format_family="section",
        format_open="§",
        format_close="§!",
        icon_family="pound",
    ),
    "eu5": GameFormatContract(
        game_id="eu5",
        format_family="hash",
        format_open="#",
        format_close="#!",
        icon_family="at_bang",
    ),
}


@dataclass(frozen=True)
class FormatToken:
    """A source-preserving token with its original character span."""

    kind: str
    raw: str
    start: int
    end: int
    depth: int
    canonical: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "raw": self.raw,
            "start": self.start,
            "end": self.end,
            "depth": self.depth,
            "canonical": self.canonical,
        }


@dataclass(frozen=True)
class FormatSpan:
    """A balanced formatting wrapper and the protected tokens it encloses."""

    opener: FormatToken
    closer: FormatToken
    protected_tokens: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "opener": self.opener.as_dict(),
            "closer": self.closer.as_dict(),
            "protected_tokens": list(self.protected_tokens),
        }


@dataclass
class ParsedFormatStructure:
    game_id: str
    text: str
    tokens: Tuple[FormatToken, ...]
    spans: Tuple[FormatSpan, ...]
    unmatched_closes: Tuple[FormatToken, ...] = ()
    unclosed_openers: Tuple[FormatToken, ...] = ()
    parse_errors: Tuple[str, ...] = ()

    @property
    def balanced(self) -> bool:
        return not self.unmatched_closes and not self.unclosed_openers and not self.parse_errors

    @property
    def runtime_tokens(self) -> Tuple[FormatToken, ...]:
        return tuple(token for token in self.tokens if token.kind == "runtime")

    @property
    def format_tokens(self) -> Tuple[FormatToken, ...]:
        return tuple(
            token
            for token in self.tokens
            if token.kind in {"format_open", "format_close"}
        )


@dataclass
class FormatStructureDiff:
    """Deterministic comparison of source and target structure.

    ``hard_issues`` are safe to block automatically.  ``possible_variations``
    are intentionally not treated as correctness: they are a hand-off to a
    semantic assessor or human review and must not be requeued for repair.
    """

    game_id: str
    source: ParsedFormatStructure
    target: ParsedFormatStructure
    missing_protected: List[str] = field(default_factory=list)
    extra_protected: List[str] = field(default_factory=list)
    protected_identity_changes: List[Dict[str, Any]] = field(default_factory=list)
    protected_order_changed: bool = False
    format_identity_changes: List[Dict[str, Any]] = field(default_factory=list)
    format_order_changed: bool = False
    boundary_changes: List[Dict[str, Any]] = field(default_factory=list)
    nesting_changes: List[Dict[str, Any]] = field(default_factory=list)
    possible_variations: List[Dict[str, Any]] = field(default_factory=list)
    runtime_variations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def source_issue(self) -> bool:
        return not self.source.balanced

    @property
    def hard_issues(self) -> List[str]:
        issues: List[str] = []
        if not self.target.balanced:
            issues.append("target_unbalanced")
        runtime_variation_only = self.runtime_variation_only
        if (self.missing_protected or self.extra_protected) and not runtime_variation_only:
            issues.append("protected_token_parity")
        if self.protected_identity_changes:
            issues.append("protected_token_identity")
        if self.protected_order_changed:
            issues.append("protected_token_order")
        if self.format_identity_changes:
            issues.append("format_tag_identity")
        if self.format_order_changed:
            issues.append("format_tag_order")
        if self.boundary_changes and not runtime_variation_only:
            issues.append("format_boundary")
        if self.nesting_changes:
            issues.append("format_nesting")
        return issues

    @property
    def runtime_variation_only(self) -> bool:
        """Whether duplicate runtime-token reduction is the only difference."""
        return bool(self.runtime_variations) and not any(
            (
                not self.source.balanced,
                not self.target.balanced,
                self.protected_identity_changes,
                self.protected_order_changed,
                self.format_identity_changes,
                self.format_order_changed,
                self.nesting_changes,
            )
        )

    @property
    def passed(self) -> bool:
        return not self.hard_issues and not self.source_issue

    @property
    def repairable(self) -> bool:
        return bool(self.hard_issues) and not self.source_issue

    @property
    def reviewable(self) -> bool:
        return self.source_issue or bool(self.possible_variations)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "source_balanced": self.source.balanced,
            "target_balanced": self.target.balanced,
            "source_issue": self.source_issue,
            "hard_issues": self.hard_issues,
            "repairable": self.repairable,
            "reviewable": self.reviewable,
            "missing_protected": list(self.missing_protected),
            "extra_protected": list(self.extra_protected),
            "protected_identity_changes": list(self.protected_identity_changes),
            "protected_order_changed": self.protected_order_changed,
            "format_identity_changes": list(self.format_identity_changes),
            "format_order_changed": self.format_order_changed,
            "boundary_changes": list(self.boundary_changes),
            "nesting_changes": list(self.nesting_changes),
            "possible_variations": list(self.possible_variations),
            "runtime_variations": list(self.runtime_variations),
            "source_parse_errors": list(self.source.parse_errors),
            "target_parse_errors": list(self.target.parse_errors),
        }


def normalize_game_id(game_id: str) -> str:
    normalized = str(game_id or "").strip().lower()
    return GAME_ALIASES.get(normalized, normalized)


def get_game_format_contract(game_id: str) -> Optional[GameFormatContract]:
    return GAME_FORMAT_CONTRACTS.get(normalize_game_id(game_id))


def _append_token(
    tokens: List[FormatToken],
    kind: str,
    raw: str,
    start: int,
    end: int,
    depth: int,
    canonical: Optional[str] = None,
) -> FormatToken:
    token = FormatToken(
        kind=kind,
        raw=raw,
        start=start,
        end=end,
        depth=depth,
        canonical=canonical if canonical is not None else raw,
    )
    tokens.append(token)
    return token


def _read_balanced_bracket(text: str, start: int) -> Tuple[int, bool]:
    depth = 0
    quote: Optional[str] = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index + 1, True
    return len(text), False


def _read_hash_opener(text: str, start: int) -> Optional[int]:
    match = re.match(r"#[A-Za-z_][A-Za-z0-9_]*", text[start:])
    if not match:
        return None
    cursor = start + match.end()

    # Vic3/CK3 tooltip forms can carry a code parameter without a separating
    # space. Preserve that parameter as part of the format opener, but leave
    # the visible text after ``>`` as translatable text.
    while text.startswith(";tooltip:<", cursor):
        close = text.find(">", cursor + len(";tooltip:<"))
        if close < 0:
            return len(text)
        cursor = close + 1

    if cursor < len(text) and text[cursor] == ":":
        cursor += 1
        while cursor < len(text) and not text[cursor].isspace() and not text.startswith("#!", cursor):
            cursor += 1
    elif cursor < len(text) and text[cursor] == ";":
        while cursor < len(text) and not text[cursor].isspace() and not text.startswith("#!", cursor):
            cursor += 1
    return cursor


def _read_section_opener(text: str, start: int) -> Optional[int]:
    if start + 1 >= len(text) or text[start] != "§" or text[start + 1] == "!":
        return None
    if text[start + 1] == "=":
        cursor = start + 2
        while cursor < len(text) and not text[cursor].isspace() and text[cursor] != "§":
            if text.startswith("§!", cursor):
                break
            if text[cursor] == "$":
                break
            cursor += 1
        return cursor
    if text[start + 1].isalnum():
        return start + 2
    return None


def _canonical_runtime(game_id: str, raw: str) -> str:
    """Return comparison identity while preserving ``raw`` on the token."""
    if normalize_game_id(game_id) == "ck3":
        concept = re.fullmatch(
            r"\[Concept\('([^']*)',\s*'[^']*'\)(\|[^\]]+)?\]",
            raw,
        )
        if concept:
            # CK3's second Concept argument is player-visible text and may be
            # translated; the key and display modifier remain protected.
            return f"CK3_CONCEPT:{concept.group(1)}:{concept.group(2) or ''}"
    return raw


def _scan_format_tokens(
    value: str,
    contract: GameFormatContract,
    normalized_game_id: str,
) -> Tuple[List[FormatToken], List[FormatSpan], List[FormatToken], List[FormatToken], List[str]]:
    tokens: List[FormatToken] = []
    spans: List[FormatSpan] = []
    open_stack: List[FormatToken] = []
    unmatched_closes: List[FormatToken] = []
    parse_errors: List[str] = []
    index = 0

    while index < len(value):
        if value.startswith("\\n", index):
            _append_token(tokens, "runtime", "\\n", index, index + 2, len(open_stack))
            index += 2
            continue

        char = value[index]
        if char == "$":
            close = value.find("$", index + 1)
            if close < 0:
                parse_errors.append(f"unterminated_dollar:{index}")
                _append_token(tokens, "runtime", value[index:], index, len(value), len(open_stack))
                break
            raw = value[index : close + 1]
            _append_token(tokens, "runtime", raw, index, close + 1, len(open_stack))
            index = close + 1
            continue

        if char == "[":
            end, closed = _read_balanced_bracket(value, index)
            raw = value[index:end]
            if not closed:
                parse_errors.append(f"unterminated_bracket:{index}")
            _append_token(
                tokens,
                "runtime",
                raw,
                index,
                end,
                len(open_stack),
                _canonical_runtime(normalized_game_id, raw),
            )
            index = end
            continue

        if contract.icon_family == "at_bang" and char == "@":
            match = re.match(r"@[A-Za-z0-9_.-]+!", value[index:])
            if match:
                raw = match.group(0)
                _append_token(tokens, "runtime", raw, index, index + len(raw), len(open_stack))
                index += len(raw)
                continue

        if contract.flag_family == "at_bare" and char == "@":
            match = re.match(r"@[A-Z0-9]{3}", value[index:])
            if match:
                raw = match.group(0)
                _append_token(tokens, "runtime", raw, index, index + len(raw), len(open_stack))
                index += len(raw)
                continue

        if char == "£" and contract.icon_family == "pound":
            match = re.match(r"£[^£\s]+£", value[index:])
            if match:
                raw = match.group(0)
                _append_token(tokens, "runtime", raw, index, index + len(raw), len(open_stack))
                index += len(raw)
                continue
            parse_errors.append(f"unterminated_pound_icon:{index}")
            _append_token(tokens, "runtime", value[index:], index, len(value), len(open_stack))
            break

        if value.startswith(contract.format_close, index):
            close_token = _append_token(
                tokens,
                "format_close",
                contract.format_close,
                index,
                index + len(contract.format_close),
                max(0, len(open_stack) - 1),
            )
            if not open_stack:
                unmatched_closes.append(close_token)
            else:
                opener = open_stack.pop()
                protected = tuple(
                    token.canonical
                    for token in tokens
                    if opener.end <= token.start < close_token.start and token.kind == "runtime"
                )
                spans.append(FormatSpan(opener, close_token, protected))
            index += len(contract.format_close)
            continue

        opener_end: Optional[int] = None
        if contract.format_family == "hash" and char == "#":
            opener_end = _read_hash_opener(value, index)
        elif contract.format_family == "section" and char == "§":
            opener_end = _read_section_opener(value, index)

        if opener_end is not None and opener_end > index:
            raw = value[index:opener_end]
            opener = _append_token(
                tokens,
                "format_open",
                raw,
                index,
                opener_end,
                len(open_stack),
            )
            open_stack.append(opener)
            index = opener_end
            continue

        index += 1

    return tokens, spans, unmatched_closes, open_stack, parse_errors


def parse_format_structure(text: str, game_id: str) -> ParsedFormatStructure:
    """Parse supported runtime and formatting tokens without changing text."""
    contract = get_game_format_contract(game_id)
    normalized_game_id = normalize_game_id(game_id)
    value = text or ""
    if contract is None:
        return ParsedFormatStructure(normalized_game_id, value, (), ())

    tokens, spans, unmatched_closes, unclosed_openers, parse_errors = _scan_format_tokens(
        value,
        contract,
        normalized_game_id,
    )
    return ParsedFormatStructure(
        game_id=normalized_game_id,
        text=value,
        tokens=tuple(tokens),
        spans=tuple(sorted(spans, key=lambda span: span.opener.start)),
        unmatched_closes=tuple(unmatched_closes),
        unclosed_openers=tuple(unclosed_openers),
        parse_errors=tuple(parse_errors),
    )


def _sequence_diff(
    source: Sequence[FormatToken],
    target: Sequence[FormatToken],
) -> Tuple[List[str], List[str], List[Dict[str, Any]], bool]:
    source_keys = [token.canonical for token in source]
    target_keys = [token.canonical for token in target]
    missing: List[str] = []
    extra: List[str] = []
    changed: List[Dict[str, Any]] = []
    order_changed = False
    matcher = SequenceMatcher(None, source_keys, target_keys, autojunk=False)
    for opcode, source_start, source_end, target_start, target_end in matcher.get_opcodes():
        if opcode == "delete":
            missing.extend(token.raw for token in source[source_start:source_end])
        elif opcode == "insert":
            extra.extend(token.raw for token in target[target_start:target_end])
        elif opcode == "replace":
            source_part = source[source_start:source_end]
            target_part = target[target_start:target_end]
            if len(source_part) == len(target_part):
                for source_token, target_token in zip(source_part, target_part):
                    changed.append(
                        {
                            "source": source_token.raw,
                            "target": target_token.raw,
                            "source_start": source_token.start,
                            "target_start": target_token.start,
                            "kind": source_token.kind,
                        }
                    )
            else:
                missing.extend(token.raw for token in source_part)
                extra.extend(token.raw for token in target_part)
        elif opcode == "equal":
            continue
    if Counter(source_keys) == Counter(target_keys) and source_keys != target_keys:
        order_changed = True
    return missing, extra, changed, order_changed


def _runtime_token_reduction_variations(
    source: ParsedFormatStructure,
    target: ParsedFormatStructure,
) -> List[Dict[str, Any]]:
    """Find conservative review-only reductions of repeated runtime tokens."""
    if not source.balanced or not target.balanced:
        return []
    if [
        (token.kind, token.raw) for token in source.format_tokens
    ] != [
        (token.kind, token.raw) for token in target.format_tokens
    ]:
        return []

    source_keys = [token.canonical for token in source.runtime_tokens]
    target_keys = [token.canonical for token in target.runtime_tokens]
    source_counts = Counter(source_keys)
    target_counts = Counter(target_keys)
    missing_counts = source_counts - target_counts
    extra_counts = target_counts - source_counts
    if not missing_counts or extra_counts:
        return []
    if any(source_counts[key] < 2 or target_counts[key] < 1 for key in missing_counts):
        return []

    target_index = 0
    for source_key in source_keys:
        if target_index < len(target_keys) and source_key == target_keys[target_index]:
            target_index += 1
    if target_index != len(target_keys):
        return []

    return [{
        "kind": "runtime_token_occurrence_delta",
        "source_tokens": dict(source_counts),
        "target_tokens": dict(target_counts),
        "missing_repeated_tokens": dict(missing_counts),
        "reason": "duplicate_runtime_token_reduced_for_target_language_wording",
    }]


def _compare_format_tokens(
    source: ParsedFormatStructure,
    target: ParsedFormatStructure,
) -> Tuple[List[Dict[str, Any]], bool, List[Dict[str, Any]]]:
    source_tokens = source.format_tokens
    target_tokens = target.format_tokens
    source_keys = [(token.kind, token.raw) for token in source_tokens]
    target_keys = [(token.kind, token.raw) for token in target_tokens]
    identity_changes: List[Dict[str, Any]] = []
    order_changed = False

    if source_keys == target_keys:
        return identity_changes, order_changed, []

    source_opens = [token.raw for token in source_tokens if token.kind == "format_open"]
    target_opens = [token.raw for token in target_tokens if token.kind == "format_open"]
    source_shape = [token.kind for token in source_tokens]
    target_shape = [token.kind for token in target_tokens]

    if len(source_tokens) == len(target_tokens) and source_shape == target_shape:
        for source_token, target_token in zip(source_tokens, target_tokens):
            if source_token.raw != target_token.raw or source_token.kind != target_token.kind:
                identity_changes.append(
                    {
                        "source": source_token.raw,
                        "target": target_token.raw,
                        "source_start": source_token.start,
                        "target_start": target_token.start,
                        "kind": source_token.kind,
                    }
                )
        return identity_changes, order_changed, []

    if Counter(source_keys) == Counter(target_keys):
        order_changed = True
        return identity_changes, order_changed, []

    source_open_counts = Counter(source_opens)
    target_open_counts = Counter(target_opens)
    if source_tokens and not target_tokens:
        identity_changes.extend(
            {
                "source": token.raw,
                "target": None,
                "source_start": token.start,
                "kind": token.kind,
                "reason": "source_format_removed_from_target",
            }
            for token in source_tokens
        )
        return identity_changes, order_changed, []
    novel_openers = list((target_open_counts - source_open_counts).elements())
    if novel_openers:
        identity_changes.extend(
            {
                "source": None,
                "target": opener,
                "target_start": next(
                    token.start for token in target_tokens if token.raw == opener
                ),
                "kind": "format_open",
                "reason": "target_added_format_absent_from_source",
            }
            for opener in novel_openers
        )
        return identity_changes, order_changed, []

    variation = [
        {
            "kind": "format_occurrence_delta",
            "source_openers": dict(source_open_counts),
            "target_openers": dict(target_open_counts),
            "source_marker_count": len(source_tokens),
            "target_marker_count": len(target_tokens),
            "reason": "known_format_identity_with_occurrence_delta",
        }
    ]
    return identity_changes, order_changed, variation


def _compare_boundaries(
    source: ParsedFormatStructure,
    target: ParsedFormatStructure,
) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    if len(source.spans) != len(target.spans):
        return changes
    for source_span, target_span in zip(source.spans, target.spans):
        if source_span.opener.raw != target_span.opener.raw:
            continue
        if source_span.protected_tokens != target_span.protected_tokens:
            changes.append(
                {
                    "source_opener": source_span.opener.raw,
                    "target_opener": target_span.opener.raw,
                    "source_protected": list(source_span.protected_tokens),
                    "target_protected": list(target_span.protected_tokens),
                    "source_start": source_span.opener.start,
                    "target_start": target_span.opener.start,
                }
            )
    return changes


def compare_format_structure(source: str, target: str, game_id: str) -> FormatStructureDiff:
    """Compare source/target while keeping semantic variation explicit."""
    normalized_game_id = normalize_game_id(game_id)
    source_parsed = parse_format_structure(source or "", normalized_game_id)
    target_parsed = parse_format_structure(target or "", normalized_game_id)
    diff = FormatStructureDiff(normalized_game_id, source_parsed, target_parsed)

    # Source syntax is a separate diagnostic. Never make a target repair chase
    # a missing source close marker, but retain independent target diagnostics.
    if not diff.source_issue:
        source_runtime = source_parsed.runtime_tokens
        target_runtime = target_parsed.runtime_tokens
        (
            diff.missing_protected,
            diff.extra_protected,
            diff.protected_identity_changes,
            diff.protected_order_changed,
        ) = _sequence_diff(source_runtime, target_runtime)

        (
            diff.format_identity_changes,
            diff.format_order_changed,
            format_variations,
        ) = _compare_format_tokens(source_parsed, target_parsed)
        diff.possible_variations.extend(format_variations)
        diff.boundary_changes.extend(_compare_boundaries(source_parsed, target_parsed))
        diff.runtime_variations.extend(
            _runtime_token_reduction_variations(source_parsed, target_parsed)
        )
        diff.possible_variations.extend(diff.runtime_variations)

        source_depths = [(token.kind, token.depth) for token in source_parsed.format_tokens]
        target_depths = [(token.kind, token.depth) for token in target_parsed.format_tokens]
        source_raws = [token.raw for token in source_parsed.format_tokens]
        target_raws = [token.raw for token in target_parsed.format_tokens]
        if source_raws == target_raws and source_depths != target_depths:
            diff.nesting_changes.append(
                {
                    "source": source_depths,
                    "target": target_depths,
                    "reason": "same_format_identity_different_nesting",
                }
            )

    # A count delta is only a review candidate when the target did not invent a
    # new format identity and no protected/runtime structure was damaged.
    if diff.hard_issues:
        diff.possible_variations.clear()
    return diff


def format_structure_signature(text: str, game_id: str) -> Dict[str, Any]:
    """Return a compact signature for prompt example selection."""
    parsed = parse_format_structure(text or "", game_id)
    return {
        "game_id": parsed.game_id,
        "balanced": parsed.balanced,
        "format_openers": [token.raw for token in parsed.tokens if token.kind == "format_open"],
        "format_closers": [token.raw for token in parsed.tokens if token.kind == "format_close"],
        "protected_tokens": [token.raw for token in parsed.runtime_tokens],
        "has_nested_formatting": any(token.depth > 0 for token in parsed.format_tokens),
    }


__all__ = [
    "FormatSpan",
    "FormatStructureDiff",
    "FormatToken",
    "GameFormatContract",
    "GAME_FORMAT_CONTRACTS",
    "compare_format_structure",
    "format_structure_signature",
    "get_game_format_contract",
    "normalize_game_id",
    "parse_format_structure",
]
