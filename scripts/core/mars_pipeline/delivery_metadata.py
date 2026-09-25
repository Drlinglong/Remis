"""Rendering helpers for safe localization registration in Lua Mod metadata."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scripts.core.services import mars_translation_package as package
from scripts.core.services import mars_lua_discovery

MAX_SOURCE_FILE_BYTES = 128 * 1024 * 1024


class DeliveryMetadataError(ValueError):
    """A Lua registration structure is outside the supported safe profile."""


def _append_loc_items(items_raw: bytes, source_id: str, tables: list[dict[str, str]]) -> bytes:
    bom = items_raw.startswith(b"\xef\xbb\xbf")
    try:
        source = items_raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DeliveryMetadataError("items.lua is not valid UTF-8.") from error
    try:
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    except (ValueError, IndexError) as error:
        raise DeliveryMetadataError("items.lua cannot be safely extended by the delivery builder.") from error
    if len(tokens) < 3 or tokens[0].value != "return" or tokens[1].value != "{":
        raise DeliveryMetadataError("items.lua must return a table before localization registrations can be added.")
    close = pairs.get(1)
    if close is None or tokens[close + 1:]:
        raise DeliveryMetadataError("items.lua return table is not a single safe top-level expression.")
    close_offset = tokens[close].start
    before = source[:close_offset].rstrip()
    ending = "\r\n" if "\r\n" in source else "\n"
    additions: list[str] = []
    for table in tables:
        language = table["language"]
        mounted = f"Mod/{source_id}/{table['path']}"
        additions.extend(["\tPlaceObj('ModItemLocTable', {", f"\t\t'language', {package._lua_string(language)},",
                          f"\t\t'filename', {package._lua_string(mounted)},", "\t}),"])
    separator = "" if before.endswith((",", "{")) else ","
    rendered = before + separator + ending + ending.join(additions) + ending + source[close_offset:]
    data = rendered.encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data
def _append_metadata_loctables(metadata_raw: bytes, source_id: str,
                               tables: list[dict[str, str]]) -> bytes:
    bom = metadata_raw.startswith(b"\xef\xbb\xbf")
    try:
        source = metadata_raw.decode("utf-8-sig")
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    except (UnicodeDecodeError, ValueError, IndexError) as error:
        raise DeliveryMetadataError("metadata.lua cannot be safely extended with localization registrations.") from error
    if (len(tokens) < 6 or tokens[0].value != "return" or tokens[1].value != "PlaceObj"
            or tokens[2].value != "(" or tokens[3].kind not in {"string", "long_string"}
            or mars_lua_discovery._literal_text(tokens[3]) != "ModDef"
            or tokens[4].value != "," or tokens[5].value != "{"):
        raise DeliveryMetadataError("metadata.lua does not use the supported literal ModDef table form.")
    close_index = pairs.get(5)
    call_close = pairs.get(2)
    if (close_index is None or call_close != close_index + 1
            or call_close + 1 != len(tokens) or tokens[call_close].value != ")"):
        raise DeliveryMetadataError("metadata.lua ModDef table is not a single safe return expression.")
    cursor = 6
    while cursor + 1 < close_index:
        if tokens[cursor].kind not in {"string", "long_string"} or tokens[cursor + 1].value != ",":
            raise DeliveryMetadataError("metadata.lua top-level fields are outside the supported literal format.")
        try:
            field = mars_lua_discovery._literal_text(tokens[cursor])
        except ValueError as error:
            raise DeliveryMetadataError("metadata.lua contains an unreadable top-level field.") from error
        if field == "loctables":
            raise DeliveryMetadataError("metadata.lua already defines loctables; merge requires a reviewed adapter.")
        value_cursor = cursor + 2
        while value_cursor < close_index and tokens[value_cursor].value != ",":
            if tokens[value_cursor].value in {"{", "[", "("}:
                value_close = pairs.get(value_cursor)
                if value_close is None or value_close >= close_index:
                    raise DeliveryMetadataError("metadata.lua contains an unbalanced top-level field value.")
                value_cursor = value_close + 1
            else:
                value_cursor += 1
        if value_cursor >= close_index:
            raise DeliveryMetadataError("metadata.lua top-level field lacks a separator.")
        cursor = value_cursor + 1
    close_offset = tokens[close_index].start
    before = source[:close_offset].rstrip()
    ending = "\r\n" if "\r\n" in source else "\n"
    rows = ["\t'loctables', {"]
    for table in tables:
        mounted = f"Mod/{source_id}/{table['path']}"
        rows.append(
            f"\t\t{{ filename = {package._lua_string(mounted)}, language = {package._lua_string(table['language'])} }},"
        )
    rows.append("\t},")
    separator = "" if before.endswith((",", "{")) else ","
    rendered = before + separator + ending + ending.join(rows) + ending + source[close_offset:]
    result = rendered.encode("utf-8")
    return (b"\xef\xbb\xbf" + result) if bom else result
def _overlay_metadata_items(
    overlay_id: str, source_id: str, title: str, tables: list[dict[str, str]]
) -> tuple[str, str]:
    meta = ["return PlaceObj('ModDef', {", f"  'title', {package._lua_string(title)},",
            f"  'id', {package._lua_string(overlay_id)},", "  'lua_revision', 350453,",
            "  'optional_mod', true,", "  'dependencies', {",
            "    PlaceObj('ModDependency', {", f"      'id', {package._lua_string(source_id)},",
            f"      'title', {package._lua_string(source_id)},", "      'required', true,",
            "    }),", "  },", "  'loctables', {"]
    items = ["return {", "  PlaceObj('ModItemCode', {", "    'name', \"RemisOverlay\",",
             "    'CodeFileName', \"Code/RemisOverlay.lua\",", "  }),"]
    for table in tables:
        mounted = f"Mod/{overlay_id}/{table['filename']}"
        meta.append(f"    {{ filename = {package._lua_string(mounted)}, language = {package._lua_string(table['language'])} }},")
        items.extend(["  PlaceObj('ModItemLocTable', {", f"    'language', {package._lua_string(table['language'])},",
                      f"    'filename', {package._lua_string(mounted)},", "  }),"])
    meta.extend(["  },", "})", ""])
    items.extend(["}", ""])
    return "\n".join(meta), "\n".join(items)


def _text_only_metadata_items(
    translation_id: str, source_id: str, title: str, tables: list[dict[str, str]]
) -> tuple[str, str]:
    """Register CSV tables in a separate Mod that depends on the source Mod."""
    meta = ["return PlaceObj('ModDef', {", f"  'title', {package._lua_string(title)},",
            f"  'id', {package._lua_string(translation_id)},", "  'lua_revision', 350453,",
            "  'optional_mod', true,", "  'dependencies', {", "    PlaceObj('ModDependency', {",
            f"      'id', {package._lua_string(source_id)},",
            f"      'title', {package._lua_string(source_id)},", "      'required', true,",
            "    }),", "  },", "  'loctables', {"]
    items = ["return {"]
    for table in tables:
        mounted = f"Mod/{translation_id}/{table['path']}"
        meta.append(f"    {{ filename = {package._lua_string(mounted)}, language = {package._lua_string(table['language'])} }},")
        items.extend(["  PlaceObj('ModItemLocTable', {", f"    'language', {package._lua_string(table['language'])},",
                      f"    'filename', {package._lua_string(mounted)},", "  }),"])
    meta.extend(["  },", "})", ""])
    items.extend(["}", ""])
    return "\n".join(meta), "\n".join(items)
def _prefix_source_copy_title(metadata_raw: bytes) -> bytes:
    """Mark the copied Mod in the game UI while retaining the author's text."""
    bom = metadata_raw.startswith(b"\xef\xbb\xbf")
    try:
        source = metadata_raw.decode("utf-8-sig")
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    except (UnicodeDecodeError, ValueError, IndexError) as error:
        raise DeliveryMetadataError("metadata.lua title cannot be safely labeled for the source copy.") from error
    if len(tokens) < 6 or tokens[0].value != "return" or tokens[1].value != "PlaceObj" or tokens[5].value != "{":
        raise DeliveryMetadataError("metadata.lua does not use the supported literal ModDef form.")
    close_index = pairs.get(5)
    if close_index is None:
        raise DeliveryMetadataError("metadata.lua ModDef table is unbalanced.")
    cursor = 6
    title_token = None
    while cursor + 1 < close_index:
        if tokens[cursor].kind not in {"string", "long_string"} or tokens[cursor + 1].value != ",":
            raise DeliveryMetadataError("metadata.lua has an unsupported top-level field while labeling the copy.")
        field = mars_lua_discovery._literal_text(tokens[cursor])
        value_index = cursor + 2
        if field == "title":
            if title_token is not None or value_index >= close_index or tokens[value_index].kind not in {"string", "long_string"}:
                raise DeliveryMetadataError("metadata.lua title must be one literal string.")
            title_token = tokens[value_index]
        while value_index < close_index and tokens[value_index].value != ",":
            if tokens[value_index].value in {"{", "[", "("}:
                value_close = pairs.get(value_index)
                if value_close is None or value_close >= close_index:
                    raise DeliveryMetadataError("metadata.lua has an unbalanced top-level field value.")
                value_index = value_close + 1
            else:
                value_index += 1
        cursor = value_index + 1
    if title_token is None:
        raise DeliveryMetadataError("metadata.lua has no literal title field to label the source copy.")
    title = mars_lua_discovery._literal_text(title_token)
    replacement = package._lua_string(f"[Remis i18n] {title}")
    rendered = source[:title_token.start] + replacement + source[title_token.end:]
    result = rendered.encode("utf-8")
    return (b"\xef\xbb\xbf" + result) if bom else result


def _override_source_copy_metadata(metadata_raw: bytes, fields: dict[str, str]) -> bytes:
    """Replace or append reviewed literal metadata fields without touching author data."""
    if not fields:
        return metadata_raw
    bom = metadata_raw.startswith(b"\xef\xbb\xbf")
    try:
        source = metadata_raw.decode("utf-8-sig")
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    except (UnicodeDecodeError, ValueError, IndexError) as error:
        raise DeliveryMetadataError("metadata.lua cannot be safely updated with publication metadata.") from error
    if len(tokens) < 6 or tokens[0].value != "return" or tokens[1].value != "PlaceObj" or tokens[5].value != "{":
        raise DeliveryMetadataError("metadata.lua does not use the supported literal ModDef form.")
    close_index = pairs.get(5)
    if close_index is None:
        raise DeliveryMetadataError("metadata.lua ModDef table is unbalanced.")
    wanted = set(fields)
    seen: dict[str, Any] = {}
    cursor = 6
    while cursor + 1 < close_index:
        if tokens[cursor].kind not in {"string", "long_string"} or tokens[cursor + 1].value != ",":
            raise DeliveryMetadataError("metadata.lua has an unsupported top-level field structure.")
        field = mars_lua_discovery._literal_text(tokens[cursor])
        value_index = cursor + 2
        value_end = value_index
        while value_end < close_index and tokens[value_end].value != ",":
            if tokens[value_end].value in {"{", "[", "("}:
                value_close = pairs.get(value_end)
                if value_close is None or value_close >= close_index:
                    raise DeliveryMetadataError("metadata.lua contains an unbalanced field value.")
                value_end = value_close + 1
            else:
                value_end += 1
        if value_end >= close_index:
            raise DeliveryMetadataError("metadata.lua top-level field lacks a separator.")
        if field in wanted:
            if field in seen or value_end != value_index + 1 or tokens[value_index].kind not in {"string", "long_string"}:
                raise DeliveryMetadataError(f"metadata.lua {field} field must be one literal string.")
            seen[field] = tokens[value_index]
        cursor = value_end + 1
    edits = [(token.start, token.end, package._lua_string(fields[field]))
             for field, token in seen.items()]
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    missing = [field for field in fields if field not in seen]
    if missing:
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
        close_index = pairs.get(5)
        if close_index is None:
            raise DeliveryMetadataError("metadata.lua ModDef table became unbalanced.")
        close_offset = tokens[close_index].start
        before = source[:close_offset].rstrip()
        ending = "\r\n" if "\r\n" in source else "\n"
        separator = "" if before.endswith((",", "{")) else ","
        additions = [f"\t{package._lua_string(field)}, {package._lua_string(fields[field])},"
                     for field in missing]
        source = before + separator + ending + ending.join(additions) + ending + source[close_offset:]
    result = source.encode("utf-8")
    return (b"\xef\xbb\xbf" + result) if bom else result


def _metadata_source_id_token(tokens: list[Any], pairs: dict[int, int], source_id: str) -> Any:
    if (len(tokens) < 6 or tokens[0].value != "return" or tokens[1].value != "PlaceObj"
            or tokens[5].value != "{"):
        raise DeliveryMetadataError("metadata.lua does not use the supported literal ModDef form.")
    close_index = pairs.get(5)
    cursor = 6
    id_tokens = []
    while close_index is not None and cursor + 1 < close_index:
        if tokens[cursor].kind not in {"string", "long_string"} or tokens[cursor + 1].value != ",":
            raise DeliveryMetadataError("metadata.lua has an unsupported top-level field during identity rewrite.")
        field = mars_lua_discovery._literal_text(tokens[cursor])
        value_index = cursor + 2
        if field == "id":
            if value_index >= close_index or tokens[value_index].kind not in {"string", "long_string"}:
                raise DeliveryMetadataError("metadata.lua Mod ID must be a literal string.")
            id_tokens.append(tokens[value_index])
        while value_index < close_index and tokens[value_index].value != ",":
            if tokens[value_index].value in {"{", "[", "("}:
                value_close = pairs.get(value_index)
                if value_close is None or value_close >= close_index:
                    raise DeliveryMetadataError("metadata.lua contains an unbalanced field during identity rewrite.")
                value_index = value_close + 1
            else:
                value_index += 1
        cursor = value_index + 1
    if len(id_tokens) != 1 or mars_lua_discovery._literal_text(id_tokens[0]) != source_id:
        raise DeliveryMetadataError("metadata.lua must contain exactly one literal source Mod ID.")
    return id_tokens[0]


def _remove_source_publication_ids(metadata_raw: bytes) -> bytes:
    """Drop top-level platform publication IDs so a copy cannot impersonate the source."""
    bom = metadata_raw.startswith(b"\xef\xbb\xbf")
    try:
        source = metadata_raw.decode("utf-8-sig")
        tokens = mars_lua_discovery._tokens(source)
        pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    except (UnicodeDecodeError, ValueError, IndexError) as error:
        raise DeliveryMetadataError("metadata.lua publication identifiers cannot be safely inspected.") from error
    if len(tokens) < 6 or tokens[0].value != "return" or tokens[1].value != "PlaceObj" or tokens[5].value != "{":
        raise DeliveryMetadataError("metadata.lua does not use the supported literal ModDef form.")
    close_index = pairs.get(5)
    cursor = 6
    removals: list[tuple[int, int]] = []
    while close_index is not None and cursor + 1 < close_index:
        if tokens[cursor].kind not in {"string", "long_string"} or tokens[cursor + 1].value != ",":
            raise DeliveryMetadataError("metadata.lua has an unsupported top-level field during publication-ID cleanup.")
        field = mars_lua_discovery._literal_text(tokens[cursor])
        value_index = cursor + 2
        while value_index < close_index and tokens[value_index].value != ",":
            if tokens[value_index].value in {"{", "[", "("}:
                value_close = pairs.get(value_index)
                if value_close is None or value_close >= close_index:
                    raise DeliveryMetadataError("metadata.lua has an unbalanced top-level value.")
                value_index = value_close + 1
            else:
                value_index += 1
        if value_index >= close_index:
            raise DeliveryMetadataError("metadata.lua top-level field is missing its comma separator.")
        if field in {"steam_id", "pdx_id"}:
            removals.append((tokens[cursor].start, tokens[value_index].end))
        cursor = value_index + 1
    for start, end in reversed(removals):
        source = source[:start] + source[end:]
    result = source.encode("utf-8")
    return (b"\xef\xbb\xbf" + result) if bom else result


def _rewrite_owned_lua_namespace(
    source_files: list[tuple[str, Path, int, str]], generated: dict[str, bytes],
    source_id: str, delivery_id: str,
) -> None:
    """Retarget literal Mod/<id> asset paths and metadata IDs in copied Lua files."""
    changed = 0
    for relative, path, size, digest in source_files:
        if not relative.casefold().endswith(".lua"):
            continue
        raw = generated.get(relative)
        if raw is None:
            with path.open("rb") as stream:
                raw = stream.read(MAX_SOURCE_FILE_BYTES + 1)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                raise DeliveryMetadataError(f"Source Lua changed during identity rewrite: {relative}")
        bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            source = raw.decode("utf-8-sig")
            tokens = mars_lua_discovery._tokens(source)
            pairs = mars_lua_discovery._delimiter_pair_map(tokens)
        except (UnicodeDecodeError, ValueError, IndexError) as error:
            raise DeliveryMetadataError(f"Lua file containing Mod identity is not safely readable: {relative}") from error
        edits: list[tuple[int, int, str]] = []
        namespace = f"Mod/{source_id}"
        for token in tokens:
            if token.kind not in {"string", "long_string"}:
                continue
            try:
                value = mars_lua_discovery._literal_text(token)
            except ValueError:
                continue
            if value == namespace or value.startswith(namespace + "/"):
                edits.append((token.start, token.end,
                              package._lua_string(f"Mod/{delivery_id}" + value[len(namespace):])))
        if relative.casefold() == "metadata.lua":
            id_token = _metadata_source_id_token(tokens, pairs, source_id)
            edits.append((id_token.start, id_token.end, package._lua_string(delivery_id)))
        if edits:
            for start, end, replacement in sorted(edits, reverse=True):
                source = source[:start] + replacement + source[end:]
            rewritten = source.encode("utf-8")
            generated[relative] = (b"\xef\xbb\xbf" + rewritten) if bom else rewritten
            changed += len(edits)
    if changed == 0:
        raise DeliveryMetadataError("No source Lua namespace references were found to retarget.")
def _source_copy_mod_id(source_id: str) -> str:
    """Give a full copy a deterministic identity distinct from its Workshop source."""
    suffix = hashlib.sha256(f"remis-source-copy\0{source_id}".encode("utf-8")).hexdigest()[:12]
    return f"Remis{suffix}"

