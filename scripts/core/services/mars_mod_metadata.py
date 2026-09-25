"""Inert reader for literal identity fields in Surviving Mars metadata.lua."""

from __future__ import annotations

import re


class MetadataParseError(ValueError):
    """Raised when metadata is outside the supported literal subset."""


_PUNCTUATION = set("(){}[],=")
_LONG_BRACKET = re.compile(r"\[(=*)\[")


def _decode_string(source: str, start: int) -> tuple[str, int]:
    quote = source[start]
    result: list[str] = []
    index = start + 1
    escapes = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"'}
    while index < len(source):
        char = source[index]
        if char == quote:
            return "".join(result), index + 1
        if char in "\r\n":
            raise MetadataParseError("Malformed Lua quoted string in metadata.lua.")
        if char != "\\":
            result.append(char)
            index += 1
            continue
        index += 1
        if index >= len(source):
            break
        escaped = source[index]
        if escaped == "z":
            index += 1
            while index < len(source) and source[index].isspace():
                index += 1
        elif escaped in escapes:
            result.append(escapes[escaped])
            index += 1
        elif escaped == "x" and index + 2 < len(source) and re.fullmatch(r"[0-9A-Fa-f]{2}", source[index + 1:index + 3]):
            result.append(chr(int(source[index + 1:index + 3], 16)))
            index += 3
        elif escaped.isdigit():
            end = index
            while end < min(index + 3, len(source)) and source[end].isdigit():
                end += 1
            result.append(chr(int(source[index:end]) % 256))
            index = end
        elif escaped in "\r\n":
            if escaped == "\r" and source[index:index + 2] == "\r\n":
                index += 1
            result.append("\n")
            index += 1
        else:
            raise MetadataParseError("Unsupported Lua escape in metadata.lua.")
    raise MetadataParseError("Unterminated Lua string in metadata.lua.")


def _long_bracket_end(source: str, start: int) -> tuple[int, str] | None:
    match = _LONG_BRACKET.match(source, start)
    if not match:
        return None
    close = "]" + match.group(1) + "]"
    end = source.find(close, match.end())
    if end < 0:
        raise MetadataParseError("Unterminated Lua long string/comment in metadata.lua.")
    value_start = match.end()
    if source.startswith("\r\n", value_start):
        value_start += 2
    elif source.startswith("\n", value_start):
        value_start += 1
    return end + len(close), source[value_start:end]


def _tokens(source: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(source):
        if source[index].isspace():
            index += 1
        elif source.startswith("--", index):
            comment = _long_bracket_end(source, index + 2)
            newline = source.find("\n", index + 2)
            index = comment[0] if comment else (len(source) if newline < 0 else newline + 1)
        elif source[index] in "'\"":
            value, index = _decode_string(source, index)
            tokens.append(("STRING", value))
        elif long_string := _long_bracket_end(source, index):
            index, value = long_string
            tokens.append(("STRING", value))
        elif source[index] in _PUNCTUATION:
            char = source[index]
            tokens.append((char, char))
            index += 1
        else:
            end = index + 1
            while (end < len(source) and not source[end].isspace()
                   and source[end] not in _PUNCTUATION
                   and source[end] not in "'\""
                   and not source.startswith("--", end)):
                end += 1
            tokens.append(("ATOM", source[index:end]))
            index = end
    return tokens


def _value_end(tokens: list[tuple[str, str]], start: int) -> int:
    matching = {"{": "}", "[": "]", "(": ")"}
    stack: list[str] = []
    for index in range(start, len(tokens)):
        kind = tokens[index][0]
        if not stack and kind in {",", "}"}:
            return index
        if kind in matching:
            stack.append(matching[kind])
        elif kind in {"}", "]", ")"}:
            if not stack or stack.pop() != kind:
                raise MetadataParseError("Malformed Lua table in metadata.lua.")
    if stack:
        raise MetadataParseError("Unclosed Lua value in metadata.lua.")
    return len(tokens)


def top_mod_fields(source: str) -> dict[str, str]:
    """Extract literal top-level id/title; never execute Lua expressions."""
    tokens = _tokens(source.removeprefix("\ufeff"))
    prefix = [("ATOM", "return"), ("ATOM", "PlaceObj"), ("(", "("), ("STRING", "ModDef"), (",", ","), ("{", "{")]
    if tokens[:len(prefix)] != prefix:
        raise MetadataParseError("metadata.lua must begin with return PlaceObj('ModDef', {...}).")
    fields: dict[str, str] = {}
    index = len(prefix)
    while index < len(tokens) and tokens[index][0] != "}":
        if tokens[index][0] != "STRING" or index + 1 >= len(tokens) or tokens[index + 1][0] != ",":
            raise MetadataParseError("Unsupported top-level Mod metadata syntax.")
        key = tokens[index][1]
        value_start = index + 2
        end = _value_end(tokens, value_start)
        if key in {"id", "title"}:
            if end != value_start + 1 or tokens[value_start][0] != "STRING":
                raise MetadataParseError(f"metadata.lua {key} must be a plain quoted string.")
            fields[key] = tokens[value_start][1]
        if end >= len(tokens):
            break
        index = end + (1 if tokens[end][0] == "," else 0)
    return fields
