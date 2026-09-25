"""Static discovery of Lua ``Untranslated`` calls.

This module tokenizes Lua source without executing it. It deliberately does not
attempt to evaluate expressions or resolve runtime scopes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from bisect import bisect_right
import hashlib
import os
from pathlib import Path
import re


DEFAULT_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_CANDIDATES = 2000
_LONG_BRACKET_OPEN = re.compile(r"\[(=*)\[")


@dataclass(frozen=True)
class UntranslatedCandidate:
    source_path: str
    line: int
    start_offset: int
    end_offset: int
    text: str | None
    source_sha256: str
    call_sha256: str
    classification: str
    candidate_key: str | None
    manual_review: bool
    review_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation for preview APIs."""
        return {
            "source_path": self.source_path,
            "line": self.line,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "text": self.text,
            "source_sha256": self.source_sha256,
            "call_sha256": self.call_sha256,
            "classification": self.classification,
            "candidate_key": self.candidate_key,
            "manual_review": self.manual_review,
            "review_reason": self.review_reason,
        }


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    start: int
    end: int


def _long_bracket_open(source: str, index: int) -> tuple[int, int] | None:
    if index >= len(source) or source[index] != "[":
        return None
    match = _LONG_BRACKET_OPEN.match(source, index)
    if not match:
        return None
    return len(match.group(0)), len(match.group(1))


def _skip_long_bracket(source: str, index: int, opening: int, equals: int) -> int:
    closer = "]" + ("=" * equals) + "]"
    end = source.find(closer, index + opening)
    if end < 0:
        raise ValueError(f"unterminated Lua long string or comment at offset {index}")
    return end + len(closer)


def _decode_short_string(raw: str) -> str:
    """Decode Lua short-string escapes; reject malformed sequences."""
    out = bytearray()
    i = 1
    limit = len(raw) - 1
    simple = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\", '"': '"', "'": "'"}
    while i < limit:
        char = raw[i]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            i += 1
            continue
        i += 1
        if i >= limit:
            raise ValueError("trailing escape in Lua string")
        esc = raw[i]
        if esc in simple:
            out.extend(simple[esc].encode("utf-8"))
            i += 1
        elif esc == "z":
            i += 1
            while i < limit and raw[i].isspace():
                i += 1
        elif esc == "x" and i + 2 < limit:
            digits = raw[i + 1:i + 3]
            if not re.fullmatch(r"[0-9a-fA-F]{2}", digits):
                raise ValueError("invalid hexadecimal escape in Lua string")
            out.append(int(digits, 16))
            i += 3
        elif esc == "u" and i + 1 < limit and raw[i + 1] == "{":
            close = raw.find("}", i + 2, limit)
            digits = raw[i + 2:close] if close >= 0 else ""
            if not digits or not re.fullmatch(r"[0-9a-fA-F]+", digits):
                raise ValueError("invalid Unicode escape in Lua string")
            try:
                out.extend(chr(int(digits, 16)).encode("utf-8"))
            except (ValueError, UnicodeEncodeError) as exc:
                raise ValueError("invalid Unicode escape in Lua string") from exc
            i = close + 1
        elif esc in "0123456789":
            match = re.match(r"[0-9]{1,3}", raw[i:limit])
            if match is None:
                raise ValueError("invalid decimal escape in Lua string")
            value = int(match.group(0))
            if value > 255:
                raise ValueError("decimal escape out of range in Lua string")
            out.append(value)
            i += len(match.group(0))
        elif esc in "\r\n":
            if esc == "\r" and i + 1 < limit and raw[i + 1] == "\n":
                i += 1
            out.append(10)
            i += 1
        else:
            raise ValueError(f"unsupported Lua escape \\{esc}")
    try:
        return bytes(out).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("escaped Lua bytes are not valid UTF-8") from exc


def _tokens(source: str) -> list[_Token]:
    result: list[_Token] = []
    i = 0
    size = len(source)
    while i < size:
        char = source[i]
        if char.isspace():
            i += 1
            continue
        if source.startswith("--", i):
            long_open = _long_bracket_open(source, i + 2)
            if long_open:
                i = _skip_long_bracket(source, i + 2, *long_open)
            else:
                endings = [index for index in (source.find("\n", i + 2), source.find("\r", i + 2)) if index >= 0]
                newline = min(endings) if endings else -1
                i = size if newline < 0 else newline + 1
                if newline >= 0 and source[newline] == "\r" and i < size and source[i] == "\n":
                    i += 1
            continue
        if char in "'\"":
            start = i
            quote = char
            i += 1
            closed = False
            while i < size:
                if source[i] == "\\":
                    if i + 1 < size and source[i + 1] == "z":
                        i += 2
                        while i < size and source[i].isspace():
                            i += 1
                    else:
                        i += 2
                        if i <= size and source[i - 1:i] == "\r" and i < size and source[i] == "\n":
                            i += 1
                elif source[i] == quote:
                    i += 1
                    closed = True
                    break
                elif source[i] in "\r\n":
                    raise ValueError(f"unescaped newline in Lua short string at offset {start}")
                else:
                    i += 1
            if not closed:
                raise ValueError(f"unterminated Lua short string at offset {start}")
            result.append(_Token("string", source[start:i], start, i))
            continue
        long_open = _long_bracket_open(source, i)
        if long_open:
            start = i
            i = _skip_long_bracket(source, i, *long_open)
            raw = source[start:i]
            opening = long_open[0]
            content = raw[opening:- (long_open[1] + 2)] if raw.endswith("]" + "=" * long_open[1] + "]") else ""
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            if content.startswith("\n"):
                content = content[1:]
            result.append(_Token("long_string", content, start, i))
            continue
        if char.isalpha() or char == "_":
            start = i
            i += 1
            while i < size and (source[i].isalnum() or source[i] == "_"):
                i += 1
            result.append(_Token("ident", source[start:i], start, i))
            continue
        result.append(_Token("punct", char, i, i + 1))
        i += 1
    return result


def _delimiter_pair_map(tokens: list[_Token]) -> dict[int, int]:
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {value: key for key, value in pairs.items()}
    stack: list[tuple[str, int]] = []
    matches: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.kind != "punct":
            continue
        if token.value in pairs:
            stack.append((token.value, index))
        elif token.value in closing:
            if not stack or stack[-1][0] != closing[token.value]:
                raise ValueError(f"unbalanced Lua delimiter at offset {token.start}")
            _, opening_index = stack.pop()
            matches[opening_index] = index
            matches[index] = opening_index
    if stack:
        raise ValueError(f"unterminated Lua delimiter at offset {tokens[stack[-1][1]].start}")
    return matches


def _literal_text(token: _Token) -> str:
    if token.kind == "long_string":
        return token.value
    return _decode_short_string(token.value)


def _binding_before(tokens: list[_Token], ident_index: int) -> str | None:
    """Return a nearby direct assignment name when the syntax is unambiguous."""
    if ident_index < 2 or tokens[ident_index - 1].value != "=":
        return None
    name = tokens[ident_index - 2]
    if name.kind != "ident":
        return None
    if ident_index >= 3 and tokens[ident_index - 3].value in {".", ":"}:
        return None
    if ident_index >= 3 and tokens[ident_index - 3].value == "local":
        return f"local:{name.value}"
    if ident_index >= 4 and tokens[ident_index - 4].value == "local" and tokens[ident_index - 3].value == ",":
        return f"local:{name.value}"
    # Table constructor field: { key = Untranslated(...) }
    if ident_index >= 3 and tokens[ident_index - 3].value in {"{", ","}:
        return f"field:{name.value}"
    return None


def _source_line_starts(source: str) -> list[int]:
    starts = [0]
    index = 0
    while index < len(source):
        if source[index] == "\r":
            index += 1
            if index < len(source) and source[index] == "\n":
                index += 1
            starts.append(index)
            continue
        if source[index] == "\n":
            starts.append(index + 1)
        index += 1
    return starts


def _call_descriptor(
    tokens: list[_Token], delimiter_pairs: dict[int, int], ident_index: int
) -> tuple[_Token, _Token | None, bool] | None:
    if ident_index + 1 >= len(tokens):
        return None
    following = tokens[ident_index + 1]
    if following.kind == "punct" and following.value in {"(", "{"}:
        end_index = delimiter_pairs[ident_index + 1]
        closing = tokens[end_index]
        if following.value == "{":
            return closing, None, False
        arg_token = tokens[ident_index + 2] if end_index == ident_index + 3 else None
        is_literal = arg_token is not None and arg_token.kind in {"string", "long_string"}
        return closing, arg_token, is_literal
    if following.kind in {"string", "long_string"}:
        return following, following, True
    return None


def scan_lua_text(
    source: str,
    source_path: str = "<memory>",
    *,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
) -> list[UntranslatedCandidate]:
    """Find direct global calls and mark expressions requiring human review."""
    if not isinstance(source, str):
        raise TypeError("source must be text")
    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be non-negative or None")
    tokens = _tokens(source)
    delimiter_pairs = _delimiter_pair_map(tokens)
    source_hash = hashlib.sha256(source.encode("utf-8", errors="strict")).hexdigest()
    line_starts = _source_line_starts(source)
    pending: list[tuple[_Token, _Token, str | None, str | None, str | None]] = []
    for index, token in enumerate(tokens):
        if token.kind != "ident" or token.value != "Untranslated":
            continue
        if index and tokens[index - 1].kind == "punct" and tokens[index - 1].value in {".", ":"}:
            continue
        if index and tokens[index - 1].kind == "ident" and tokens[index - 1].value == "function":
            continue
        descriptor = _call_descriptor(tokens, delimiter_pairs, index)
        if descriptor is None:
            continue
        closing, arg_token, is_single_string = descriptor
        if max_candidates is not None and len(pending) >= max_candidates:
            raise ValueError(f"Lua candidate limit reached ({max_candidates}); coverage is partial.")
        literal = is_single_string
        text: str | None = None
        reason: str | None = None
        if literal:
            try:
                if arg_token is None:
                    raise ValueError("missing literal token in Untranslated call")
                text = _literal_text(arg_token)
            except ValueError as exc:
                literal = False
                reason = str(exc)
        if not literal and reason is None:
            reason = "argument is a table or expression, or the call has multiple arguments"
        binding = _binding_before(tokens, index)
        pending.append((token, closing, text, binding, reason))
    binding_counts = Counter(item[3] for item in pending if item[3])
    output: list[UntranslatedCandidate] = []
    for start, end, text, binding, reason in pending:
        raw_call = source[start.start:end.end]
        ambiguous = binding is None or binding_counts[binding] > 1
        key = None
        if not ambiguous:
            key_material = f"{source_path}\0{binding}".encode("utf-8")
            key = "lua-" + hashlib.sha256(key_material).hexdigest()[:24]
        if reason is None:
            reason = "literal candidate requires preview; runtime scope and intent are unresolved"
        if ambiguous and text is not None:
            reason = "no unique local or table-field binding could be established"
        output.append(UntranslatedCandidate(
            source_path=source_path,
            line=bisect_right(line_starts, start.start),
            start_offset=start.start,
            end_offset=end.end,
            text=text,
            source_sha256=source_hash,
            call_sha256=hashlib.sha256(raw_call.encode("utf-8")).hexdigest(),
            classification="literal" if text is not None else "dynamic",
            candidate_key=key,
            manual_review=True,
            review_reason=reason,
        ))
    return output


def scan_lua_file(
    path: str | os.PathLike[str],
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
    source_path: str | None = None,
) -> list[UntranslatedCandidate]:
    """Read one regular Lua file as strict UTF-8, rejecting links and oversize files."""
    candidate = Path(path)
    absolute = candidate.absolute()
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise ValueError("symlinked Lua source paths are not allowed")
        try:
            attributes = part.stat(follow_symlinks=False).st_file_attributes
            if attributes & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("reparse-point Lua source paths are not allowed")
        except AttributeError:
            pass
    if not candidate.is_file():
        raise ValueError("Lua source must be a regular file")
    with candidate.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Lua source exceeds {max_bytes} byte limit")
    source = data.decode("utf-8-sig", errors="strict")
    raw_hash = hashlib.sha256(data).hexdigest()
    return [
        replace(item, source_sha256=raw_hash)
        for item in scan_lua_text(
            source,
            source_path or candidate.as_posix(),
            max_candidates=max_candidates,
        )
    ]
