"""Secure, source-preserving XML parsing helpers for RimWorld language and Def files."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
from pathlib import Path

from .contracts import Diagnostic, Document, Entry

_DOCTYPE_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_RULE_LIST_RE = re.compile(r"(?:^|\.)rulesStrings\.\d+$")


def _element_spans(text: str) -> dict[str, list[tuple[int, int]]]:
    """Return raw text spans for text-only elements, without normalizing XML."""
    parser = expat.ParserCreate()
    stack: list[dict] = []
    spans: dict[str, list[tuple[int, int] | None]] = {}
    raw = text.encode("utf-8")

    def find_tag_end(start: int) -> int:
        quote = 0
        index = start
        while index < len(raw):
            char = raw[index]
            if quote:
                if char == quote:
                    quote = 0
            elif char in (34, 39):
                quote = char
            elif char == 62:
                return index + 1
            index += 1
        raise ValueError("unterminated XML tag")

    def start_element(name: str, attrs: dict[str, str]) -> None:
        byte_index = parser.CurrentByteIndex
        stack.append({"name": name, "start": find_tag_end(byte_index), "children": False, "markup": False})
        if len(stack) > 1:
            stack[-2]["children"] = True

    def end_element(name: str) -> None:
        item = stack.pop()
        end = parser.CurrentByteIndex
        if not item["children"]:
            spans.setdefault(name, []).append(None if item["markup"] else (item["start"], end))

    def mark_markup(*_args) -> None:
        if stack:
            stack[-1]["markup"] = True

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CommentHandler = mark_markup
    parser.ProcessingInstructionHandler = mark_markup
    parser.StartCdataSectionHandler = mark_markup
    parser.Parse(raw, True)
    return spans


def _safe_root(text: str) -> ET.Element:
    if _DOCTYPE_RE.search(text):
        raise ValueError("DTD and entity declarations are not supported")
    return ET.fromstring(text)


def parse_language_xml(text: str, path: Path, metadata: dict | None = None) -> Document:
    info = dict(metadata or {})
    diagnostics: list[dict[str, str]] = []
    try:
        root = _safe_root(text)
        spans = _element_spans(text)
    except (ET.ParseError, expat.ExpatError, ValueError) as exc:
        info["diagnostics"] = [Diagnostic("invalid_xml", str(exc), str(path), "error").as_dict()]
        return Document(path, text, (), info)
    kind = info.get("kind") or infer_kind(path)
    def_type = info.get("def_type") or _def_type_from_path(path)
    entries: list[Entry] = []
    span_counts: dict[str, int] = {}
    seen_keys: set[str] = set()
    line_offsets = [0]
    line_offsets.extend(match.end() for match in re.finditer("\n", text))

    def line_number(position: int) -> int:
        import bisect
        return bisect.bisect_right(line_offsets, position)

    def visit(element: ET.Element, ancestors: tuple[str, ...]) -> None:
        tag = str(element.tag)
        if len(element):
            if not ancestors:
                diagnostics.append(Diagnostic("mixed_xml_content", f"Nested markup under {tag} is left for review", str(path)).as_dict())
                return
            for child in element:
                visit(child, ancestors + (tag,))
            return
        value = element.text or ""
        grammar_prefix = ""
        grammar_suffix = ""
        if kind == "definjected" and _RULE_LIST_RE.search(tag):
            rule = _split_rule(value)
            if rule is None:
                diagnostics.append(Diagnostic("unknown_grammar_rule", f"Cannot split the rulesStrings value for {tag}", str(path)).as_dict())
                return
            grammar_prefix, value, grammar_suffix = rule
        if kind == "keyed":
            key = tag
            output_path = f"Languages/{info.get('source_language', 'English')}/Keyed"
            field_path = tag
        elif kind == "definjected":
            field_path = tag
            key = f"{def_type}::{tag}"
            output_path = f"Languages/{{target}}/DefInjected/{def_type}"
        else:
            return
        if key in seen_keys:
            diagnostics.append(Diagnostic("duplicate_key", f"Duplicate localization key {key!r}", str(path), "error").as_dict())
        seen_keys.add(key)
        span_index = span_counts.get(tag, 0)
        span_counts[tag] = span_index + 1
        tag_spans = spans.get(tag, [])
        span = tag_spans[span_index] if span_index < len(tag_spans) else None
        if span:
            start = len(text.encode("utf-8")[:span[0]].decode("utf-8", errors="ignore"))
            line = line_number(start)
        else:
            diagnostics.append(Diagnostic("mixed_xml_content", f"Cannot safely replace mixed markup in {tag}; left for review", str(path)).as_dict())
            return
        entries.append(Entry(key, value, line, {
            "kind": kind, "def_type": def_type, "field_path": field_path,
            "output_path": output_path, "xml_tag": tag, "span_index": span_index,
            "grammar_prefix": grammar_prefix, "grammar_suffix": grammar_suffix,
        }))

    if root.tag != "LanguageData" and kind in {"keyed", "definjected"}:
        diagnostics.append(Diagnostic("unexpected_root", f"Expected LanguageData, found {root.tag}", str(path)).as_dict())
    if root.tag == "LanguageData":
        for child in root:
            visit(child, ())
    else:
        visit(root, ())
    info.update({"kind": kind, "def_type": def_type, "diagnostics": diagnostics})
    return Document(path, text, tuple(entries), info)


def infer_kind(path: Path) -> str:
    lowered = [part.casefold() for part in path.parts]
    if "keyed" in lowered:
        return "keyed"
    if "definjected" in lowered:
        return "definjected"
    if "defs" in lowered:
        return "defs"
    return "unknown"


def _def_type_from_path(path: Path) -> str:
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part.casefold() == "definjected" and index + 1 < len(parts):
            return parts[index + 1]
    return "UnknownDef"


def parse_defs(text: str, path: Path, metadata: dict | None = None,
               supported_fields: frozenset[str] = frozenset()) -> Document:
    info = dict(metadata or {})
    info["kind"] = "defs"
    diagnostics: list[dict[str, str]] = []
    try:
        root = _safe_root(text)
    except (ET.ParseError, ValueError) as exc:
        info["diagnostics"] = [Diagnostic("invalid_xml", str(exc), str(path), "error").as_dict()]
        return Document(path, text, (), info)
    entries: list[Entry] = []
    seen_keys: set[str] = set()
    version = info.get("game_version")
    if version is None or not re.match(r"^1\.6(?:\.|$)", str(version)):
        diagnostics.append(Diagnostic("def_field_catalog_reused", f"Applying known string field rules without game-version-specific runtime confirmation ({version!r})", str(path)).as_dict())
    def walk(def_element: ET.Element) -> None:
        def_name_node = def_element.find("defName")
        if def_name_node is None or not (def_name_node.text or "").strip():
            diagnostics.append(Diagnostic("missing_def_name", f"{def_element.tag} has no literal defName", str(path)).as_dict())
            return
        def_name = (def_name_node.text or "").strip()
        def_type = str(def_element.tag)
        if def_element.get("ParentName"):
            diagnostics.append(Diagnostic("inheritance_unresolved", f"{def_name} inherits ParentName={def_element.get('ParentName')}; only explicit local fields are extracted", str(path)).as_dict())
        def descend(node: ET.Element, parents: tuple[str, ...]) -> None:
            for child_index, child in enumerate(node):
                name = str(child.tag)
                if name == "li":
                    segment = str(child_index)
                else:
                    index = sum(1 for prior in list(node)[:child_index] if prior.tag == child.tag)
                    segment = name if index == 0 else f"{name}.{index}"
                field_path = ".".join((*parents, segment))
                if len(child):
                    descend(child, (*parents, segment))
                elif field_path in {"label", "description"} or _supported_field(def_type, field_path, supported_fields):
                    value = child.text or ""
                    tag = f"{def_name}.{field_path}"
                    grammar_prefix = ""
                    grammar_suffix = ""
                    if _RULE_LIST_RE.search(field_path):
                        rule = _split_rule(value)
                        if rule is None:
                            diagnostics.append(Diagnostic("unknown_grammar_rule", f"Cannot split the rulesStrings value for {tag}", str(path)).as_dict())
                            continue
                        grammar_prefix, value, grammar_suffix = rule
                    key = f"{def_type}::{tag}"
                    if key in seen_keys:
                        diagnostics.append(Diagnostic("duplicate_key", f"Duplicate localization key {key!r}", str(path), "error").as_dict())
                        continue
                    if key in set(info.get("excluded_keys", [])):
                        continue
                    seen_keys.add(key)
                    entries.append(Entry(key, value, 1, {
                        "kind": "defs", "def_type": def_type, "field_path": field_path,
                        "xml_tag": tag, "output_path": f"Languages/{{target}}/DefInjected/{def_type}",
                        "source_def": def_name, "grammar_prefix": grammar_prefix,
                        "grammar_suffix": grammar_suffix,
                    }))
        descend(def_element, ())
    if root.tag == "Defs":
        for definition in root:
            walk(definition)
    else:
        walk(root)
    info["diagnostics"] = diagnostics
    return Document(path, text, tuple(entries), info)


def _supported_field(def_type: str, field_path: str, catalog: frozenset[str]) -> bool:
    prefix = f"{def_type}::"
    if prefix + field_path in catalog:
        return True
    for item in catalog:
        if not item.startswith(prefix):
            continue
        rule_path = item[len(prefix):]
        if rule_path.endswith("rulesStrings") and field_path.startswith(rule_path + "."):
            if field_path[len(rule_path) + 1:].isdigit():
                return True
        pattern = "^" + re.escape(rule_path).replace(r"\*", r"\d+") + "$"
        if re.fullmatch(pattern, field_path):
            return True
    return False


def _split_rule(value: str) -> tuple[str, str, str] | None:
    match = re.search(r"(?<!-)->", value)
    if match is None:
        return None
    start = match.end()
    while start < len(value) and value[start] in " \t":
        start += 1
    end = len(value)
    while end > start and value[end - 1] in " \t":
        end -= 1
    return value[:start], value[start:end], value[end:]


def render_xml(document: Document, translations: dict[str, str], target_lang: dict) -> dict[str, str]:
    """Patch only text-only element payloads in a captured LanguageData snapshot."""
    if document.metadata.get("kind") not in {"keyed", "definjected"}:
        return {}
    _reject_error_document(document)
    try:
        _safe_root(document.source_text)
        spans = _element_spans(document.source_text)
    except (ET.ParseError, expat.ExpatError, ValueError):
        return {}
    replacements: list[tuple[int, int, str]] = []
    raw_bytes = document.source_text.encode("utf-8")
    span_counts: dict[str, int] = {}
    for entry in document.entries:
        if entry.key not in translations:
            continue
        if str(translations[entry.key]) == entry.value:
            continue
        tag = entry.metadata.get("xml_tag", "")
        span_index = entry.metadata.get("span_index", span_counts.get(tag, 0))
        span_counts[tag] = max(span_counts.get(tag, 0), span_index + 1)
        tag_spans = spans.get(tag, [])
        span = tag_spans[span_index] if span_index < len(tag_spans) else None
        if span is None:
            continue
        translated = entry.metadata.get("grammar_prefix", "") + str(translations[entry.key]) + entry.metadata.get("grammar_suffix", "")
        escaped = html.escape(translated, quote=False)
        replacements.append((span[0], span[1], escaped))
    for start, end, replacement in reversed(replacements):
        raw_bytes = raw_bytes[:start] + replacement.encode("utf-8") + raw_bytes[end:]
    lang_folder = language_folder(target_lang)
    destination = str(document.metadata.get("relative_output_path", document.path.name))
    if document.metadata.get("kind") == "keyed":
        destination = re.sub(r"(^|/)Languages/[^/]+/", rf"\1Languages/{lang_folder}/", destination, flags=re.I)
    elif document.metadata.get("kind") == "definjected":
        destination = re.sub(r"(^|/)Languages/[^/]+/", rf"\1Languages/{lang_folder}/", destination, flags=re.I)
    return {destination: raw_bytes.decode("utf-8")}


def _reject_error_document(document: Document) -> None:
    diagnostics = document.metadata.get("diagnostics", [])
    if any(item.get("severity") == "error" for item in diagnostics if isinstance(item, dict)):
        raise ValueError(f"Cannot render invalid RimWorld document: {document.path}")


def language_folder(language: dict) -> str:
    if isinstance(language, str):
        raw = language.strip()
    else:
        raw = ""
        if isinstance(language, dict):
            raw = next((str(language.get(key)).strip() for key in
                        ("code", "key", "name_en", "folder", "language_folder", "name", "id")
                        if language.get(key)), "")
    normalized = re.sub(r"[^a-z]", "", raw.casefold())
    folders = {
        "en": "English", "english": "English", "lenglish": "English",
        "zhcn": "ChineseSimplified", "zhsg": "ChineseSimplified",
        "simplifiedchinese": "ChineseSimplified", "chinesesimplified": "ChineseSimplified",
        "lsimpchinese": "ChineseSimplified",
        "fr": "French", "french": "French", "lfrench": "French",
        "de": "German", "german": "German", "lgerman": "German",
        "es": "Spanish", "spanish": "Spanish", "lspanish": "Spanish",
        "ja": "Japanese", "japanese": "Japanese", "ljapanese": "Japanese",
        "ko": "Korean", "korean": "Korean", "lkorean": "Korean",
        "pl": "Polish", "polish": "Polish", "lpolish": "Polish",
        "ptbr": "PortugueseBrazilian", "brazilianportuguese": "PortugueseBrazilian",
        "portuguesebrazilian": "PortugueseBrazilian", "lbrazpor": "PortugueseBrazilian",
        "ru": "Russian", "russian": "Russian", "lrussian": "Russian",
        "tr": "Turkish", "turkish": "Turkish", "lturkish": "Turkish",
    }
    return folders.get(normalized, raw or "English")
