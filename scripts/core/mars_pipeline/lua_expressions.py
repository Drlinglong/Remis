"""Small, non-executing Lua helpers for Remis Surviving Mars preparation."""

from __future__ import annotations

import re
from typing import Any

from scripts.core.services import mars_lua_discovery as lexer


def _split_top_level(tokens: list[Any], start: int, end: int, separator: str) -> list[list[Any]]:
    pairs = lexer._delimiter_pair_map(tokens)
    result: list[list[Any]] = []
    current: list[Any] = []
    index = start
    while index < end:
        token = tokens[index]
        if token.kind == "punct" and token.value == separator:
            result.append(current)
            current = []
            index += 1
            continue
        current.append(token)
        if token.kind == "punct" and token.value in "({[" and index in pairs:
            closing = pairs[index]
            if closing < end:
                current.extend(tokens[index + 1:closing + 1])
                index = closing + 1
                continue
        index += 1
    result.append(current)
    return result


def _decode_atom(tokens: list[Any]) -> str | None:
    if len(tokens) != 1 or tokens[0].kind not in {"string", "long_string"}:
        return None
    try:
        return lexer._literal_text(tokens[0])
    except ValueError:
        return None


def _tostring_binding(tokens: list[Any]) -> tuple[str, str] | None:
    if len(tokens) < 4 or tokens[0].value != "tostring" or tokens[1].value != "(":
        return None
    if tokens[-1].value != ")":
        return None
    inner = tokens[2:-1]
    if len(inner) == 1 and inner[0].kind == "ident":
        return inner[0].value, inner[0].value
    # Preserve a simple function call as a runtime parameter without evaluating it.
    if (len(inner) >= 3 and inner[0].kind == "ident"
            and inner[0].value == "GetTelepathsCreatedCount" and inner[1].value == "("):
        depth = 0
        for index, token in enumerate(inner[1:], 1):
            if token.value == "(":
                depth += 1
            elif token.value == ")":
                depth -= 1
                if depth == 0 and index != len(inner) - 1:
                    return None
        if depth == 0 and all(t.kind in {"ident", "string", "long_string", "punct"} for t in inner):
            binding = "".join(t.value for t in inner)
            return inner[0].value, binding
    return None


def _dynamic(reason: str) -> dict[str, Any]:
    return {"kind": "dynamic", "text": None, "template": None, "params": {}, "reason": reason}


def _concat_segments(expr: list[Any]) -> list[list[Any]]:
    segments: list[list[Any]] = []
    current: list[Any] = []
    index = 0
    while index < len(expr):
        if index + 1 < len(expr) and expr[index].value == "." and expr[index + 1].value == ".":
            segments.append(current)
            current = []
            index += 2
        else:
            current.append(expr[index])
            index += 1
    segments.append(current)
    return segments


def _classify_concat(expr: list[Any]) -> dict[str, Any] | None:
    segments = _concat_segments(expr)
    if len(segments) > 1:
        template = ""
        params: dict[str, str] = {}
        for segment in segments:
            text = _decode_atom(segment)
            if text is not None:
                template += text
                continue
            binding = _tostring_binding(segment)
            if not binding:
                return _dynamic("non-static concatenation requires review")
            name, expression = binding
            if name == "GetTelepathsCreatedCount":
                name = "count"
            param = re.sub(r"[^A-Za-z0-9_]", "_", name).lower() or "value"
            suffix = 2
            base = param
            while param in params:
                param = f"{base}{suffix}"
                suffix += 1
            params[param] = expression
            template += f"<{param}>"
        return {"kind": "template", "text": template, "template": template, "params": params, "reason": None}
    return None


def _named_format_parameters(fmt: str, args: list[list[Any]]) -> tuple[str, dict[str, str]] | None:
    pattern = re.compile(r"%%|%([-+ #0]*\d*(?:\.\d+)?[sdif])")
    matches = list(pattern.finditer(fmt))
    placeholders = [match for match in matches if match.group(0) != "%%"]
    if len(placeholders) != len(args):
        return None
    output: list[str] = []
    params: dict[str, str] = {}
    cursor = 0
    arg_index = 0
    for match in matches:
        output.append(fmt[cursor:match.start()])
        if match.group(0) == "%%":
            output.append("%")
        else:
            arg = args[arg_index]
            if len(arg) != 1 or arg[0].kind != "ident":
                return None
            name = arg[0].value
            param = f"value{arg_index + 1}"
            output.append(f"<{param}>")
            params[param] = f"string.format({quote_lua(match.group(0))}, {name})"
            arg_index += 1
        cursor = match.end()
    output.append(fmt[cursor:])
    if "%" in pattern.sub("", fmt):
        return None
    return "".join(output), params


def _classify_format(values: list[Any]) -> dict[str, Any] | None:
    if len(values) >= 3 and values[0].value == "string" and values[1].value == "." and values[2].value == "format":
        fmt_open = next((i for i, t in enumerate(values) if t.value == "("), None)
        if fmt_open is not None and values[-1].value == ")":
            fmt_args = _split_top_level(values, fmt_open + 1, len(values) - 1, ",")
            fmt = _decode_atom(fmt_args[0]) if fmt_args else None
            if fmt is not None:
                result = _named_format_parameters(fmt, fmt_args[1:])
                if result is None:
                    return _dynamic("string.format placeholders or arguments require manual review")
                template, params = result
                return {"kind": "template", "text": template, "template": template, "params": params, "reason": None}
    return None


def _classify_expression(expr: list[Any]) -> dict[str, Any]:
    literal = _decode_atom(expr)
    if literal is not None:
        return {"kind": "literal", "text": literal, "template": literal, "params": {}, "reason": None}
    result = _classify_concat(expr)
    if result is not None:
        return result
    result = _classify_format(expr)
    return result if result is not None else _dynamic("expression requires reviewed binding metadata")


def classify_argument(source: str, call_start: int, call_end: int) -> dict[str, Any]:
    """Classify an Untranslated call expression; only fold proven literals."""
    tokens = lexer._tokens(source)
    start = next((i for i, t in enumerate(tokens) if t.start == call_start), None)
    if start is None:
        return _dynamic("call token not found")
    opening = start + 1
    while opening < len(tokens) and tokens[opening].start < tokens[start].end:
        opening += 1
    if opening >= len(tokens) or tokens[opening].value not in {"(", "{"}:
        return _dynamic("unsupported call form")
    end = next((i for i, t in enumerate(tokens) if t.end == call_end), None)
    if end is None:
        return _dynamic("call end not found")
    if tokens[opening].value == "{":
        args = tokens[opening + 1:end]
        if args and args[0].kind in {"string", "long_string"}:
            try:
                text = lexer._literal_text(args[0])
                return {"kind": "table_template", "text": text, "template": text, "params": {},
                        "table_arguments": source[tokens[opening].end:tokens[end].start], "reason": None}
            except ValueError:
                pass
        return _dynamic("table expression requires review")
    parts = _split_top_level(tokens, opening + 1, end, ",")
    if len(parts) != 1:
        return _dynamic("multiple arguments require review")
    return _classify_expression(parts[0])


def quote_lua(value: str) -> str:
    """Encode text as a deterministic Lua double-quoted literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{escaped}"'


def render_rewrite(entry: dict[str, Any]) -> str | None:
    """Render supported Untranslated replacement preserving dynamic bindings."""
    kind = entry.get("kind")
    entry_id = entry["id"]
    text = entry.get("text", "")
    if kind == "literal":
        return f"T({entry_id}, {quote_lua(text)})"
    if kind == "table_template":
        return f"T{{ {entry_id},{entry.get('table_arguments', '')} }}"
    if kind == "template":
        params = entry.get("params") or {}
        if kind == "table_template":
            return f"T{{ {entry_id}, {quote_lua(text)} }}"
        fields = ", ".join(f"{key} = {value}" for key, value in params.items())
        suffix = f", {fields}" if fields else ""
        return f"T{{ {entry_id}, {quote_lua(text)}{suffix} }}"
    return None
