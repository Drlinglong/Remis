"""Analyze and prepare Surviving Mars Lua localization without running Lua."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from scripts.core import surviving_mars_csv
from scripts.core.services import mars_lua_discovery
from scripts.core.services.mars_mod_metadata import MetadataParseError, top_mod_fields
from scripts.core.mars_pipeline.lua_expressions import classify_argument, render_rewrite


SCHEMA_VERSION = 1
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_ENTRY_ID = 999_999_999_999
MIN_GENERATED_ID = 900_000_000_000
_NUMERIC_T = re.compile(r"\bT\s*[\({]\s*(\d+)\b")
_SHARED_GAME_IDS = {"9702", "7767", "12553"}


def _read_utf8(path: Path) -> bytes:
    absolute = path.absolute()
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise ValueError("symlinked source paths are not allowed")
        try:
            attrs = part.stat(follow_symlinks=False).st_file_attributes
            if attrs & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("reparse-point source paths are not allowed")
        except AttributeError:
            pass
    if not path.is_file():
        raise ValueError(f"source is not a regular file: {path}")
    with path.open("rb") as handle:
        data = handle.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} byte limit: {path}")
    data.decode("utf-8-sig", errors="strict")
    return data


def _lua_paths(root: Path) -> list[Path]:
    result = []
    for path in root.rglob("*.lua"):
        if path.is_symlink():
            raise ValueError("symlinked Lua source paths are not allowed")
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix().casefold())


def _source_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().casefold()):
        if path.is_symlink():
            raise ValueError("symlinked source paths are not allowed")
        for part in (path.absolute(), *path.absolute().parents):
            try:
                attributes = part.stat(follow_symlinks=False).st_file_attributes
                if attributes & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise ValueError("reparse-point source paths are not allowed")
            except AttributeError:
                pass
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def _mod_id(root: Path, files: list[Path]) -> str:
    for path in files:
        if path.name.casefold() == "metadata.lua":
            text = _read_utf8(path).decode("utf-8-sig")
            try:
                mod_id = top_mod_fields(text).get("id", "").strip()
            except MetadataParseError as exc:
                raise ValueError(f"invalid top-level ModDef metadata: {exc}") from exc
            if mod_id:
                return mod_id
            raise ValueError("metadata.lua must provide a literal top-level ModDef id")
    raise ValueError("source root is missing metadata.lua; cannot assign stable localization IDs")


def _context(source: str, offset: int) -> str:
    before = source[:offset]
    lines = before.splitlines()
    for line in reversed(lines[-4:]):
        if "=" in line:
            left = line.rsplit("=", 1)[0].strip()
            if left:
                return re.sub(r"\s+", " ", left)
        match = re.search(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*,\s*$", line)
        if match:
            return match.group(1)
    return "Lua UI text"


def _scope(source: str, offset: int) -> str:
    """Name the closest declared function to provide a semantic source scope."""
    declarations = list(re.finditer(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_:.]*)\s*\(", source[:offset]))
    return declarations[-1].group(1) if declarations else "module"


def _option_item_name(tokens: list[Any], table_start: int, before: int) -> str:
    for index in range(table_start + 1, before - 2):
        if tokens[index].kind not in {"string", "long_string"} or tokens[index + 1].value != ",":
            continue
        try:
            if mars_lua_discovery._literal_text(tokens[index]) == "name":
                value = tokens[index + 2]
                if value.kind in {"string", "long_string"}:
                    return mars_lua_discovery._literal_text(value)
        except ValueError:
            continue
    return "unnamed-option"


def _option_texts(source: str, relative: str, source_hash: str) -> list[dict[str, Any]]:
    """Return literal ModItemOptionChoice DisplayName/Help fields for review."""
    tokens = mars_lua_discovery._tokens(source)
    pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    found: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.kind != "ident" or token.value != "PlaceObj" or index + 3 >= len(tokens):
            continue
        if tokens[index + 1].value != "(":
            continue
        close = pairs.get(index + 1)
        if close is None or tokens[index + 2].kind not in {"string", "long_string"}:
            continue
        try:
            item_type = mars_lua_discovery._literal_text(tokens[index + 2])
        except ValueError:
            continue
        if item_type != "ModItemOptionChoice":
            continue
        table_start = index + 4
        if table_start >= close or tokens[table_start].value != "{":
            continue
        table_end = pairs.get(table_start)
        if table_end is None:
            continue
        cursor = table_start + 1
        while cursor + 2 < table_end:
            key_token = tokens[cursor]
            if key_token.kind in {"string", "long_string"} and tokens[cursor + 1].value == ",":
                try:
                    field = mars_lua_discovery._literal_text(key_token)
                    value_token = tokens[cursor + 2]
                    if field in {"DisplayName", "Help"} and value_token.kind in {"string", "long_string"}:
                        text = mars_lua_discovery._literal_text(value_token)
                        found.append({"text": text, "field": field,
                                      "item_name": _option_item_name(tokens, table_start, cursor),
                                      "offset": value_token.start, "end": value_token.end})
                except ValueError:
                    pass
            cursor += 1
    return [{
        "identity": f"option\0{item['item_name']}\0{item['field']}",
        "text": item["text"],
        "context": f"ModItemOptionChoice {item['field']}",
        "kind": "manual",
        "params": {},
        "reason": "plain ModItemOptionChoice string requires explicit source-copy approval",
        "manual": True,
        "ref": {"path": relative, "line": source.count("\n", 0, item["offset"]) + 1,
                "start_offset": item["offset"], "end_offset": item["end"],
                "source_sha256": source_hash,
                "call_sha256": hashlib.sha256(source[item["offset"]:item["end"]].encode("utf-8")).hexdigest()},
    } for item in found]


def _plain_text_aliases(source: str, relative: str, source_hash: str) -> list[dict[str, Any]]:
    """Expose local text-like string aliases for review instead of silently skipping them."""
    tokens = mars_lua_discovery._tokens(source)
    found: list[dict[str, Any]] = []
    text_name = re.compile(r"(?:TEXT|LABEL|TITLE|DESC|DESCRIPTION|TOOLTIP|DISPLAY_NAME|HELP)\Z", re.I)
    for index in range(len(tokens) - 3):
        if tokens[index].value != "local" or tokens[index + 1].kind != "ident":
            continue
        name, equals, literal = tokens[index + 1:index + 4]
        if (not text_name.search(name.value) and name.value != "EXOTIC_TRAIT_NAME") or equals.value != "=" or literal.kind not in {"string", "long_string"}:
            continue
        try:
            value = mars_lua_discovery._literal_text(literal)
        except ValueError:
            continue
        found.append({"identity": f"alias\0{Path(relative).stem.casefold()}\0{name.value.casefold()}",
            "alias_name": name.value, "text": value, "context": f"Lua text alias {name.value}", "kind": "manual", "params": {},
            "reason": "plain UI-text alias needs source review", "manual": True,
            "ref": {"path": relative, "line": source.count("\n", 0, literal.start) + 1,
                    "start_offset": literal.start, "end_offset": literal.end,
                    "source_sha256": source_hash,
                    "call_sha256": hashlib.sha256(source[literal.start:literal.end].encode("utf-8")).hexdigest()}})
    return found


def _shuttle_dedup_profile(source: str, relative: str) -> dict[str, Any] | None:
    """Locate exact semantic edits needed when localizing the shuttle UI label."""
    if Path(relative).name.casefold() != "exotics_shuttlehubupgrade.lua":
        return None
    anchors = {
        "signature": ("local function InsertLineBeforeThresholds(base_text, line_text)",
                      "local function InsertLineBeforeThresholds(base_text, line_text, shuttle_label)"),
        "marker": ('"From Shuttles"', "shuttle_label"),
        "call": ("InsertLineBeforeThresholds(base, line)",
                 'InsertLineBeforeThresholds(base, line, TranslateToString(T({id}, "Shuttles"), self))'),
    }
    rewrites: list[dict[str, Any]] = []
    for name, (original, replacement) in anchors.items():
        positions = [match.start() for match in re.finditer(re.escape(original), source)]
        if len(positions) != 1:
            return {"name": "localized_shuttle_dedup", "supported": False,
                    "reason": f"expected one {name} anchor; found {len(positions)}"}
        start = positions[0]
        end = start + len(original)
        rewrites.append({"path": relative, "start_offset": start, "end_offset": end,
            "source_sha256": "", "call_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "replacement_template": replacement})
    return {"name": "localized_shuttle_dedup", "supported": True, "rewrites": rewrites}


def _existing_t_records(source: str, relative: str, source_hash: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read already-keyed T(id, text) records without changing their calls."""
    tokens = mars_lua_discovery._tokens(source)
    pairs = mars_lua_discovery._delimiter_pair_map(tokens)
    found: list[dict[str, Any]] = []
    shared: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.kind != "ident" or token.value != "T" or index + 1 >= len(tokens):
            continue
        if index and tokens[index - 1].value in {".", ":"}:
            continue
        opening = index + 1
        if tokens[opening].value not in {"(", "{"}:
            continue
        closing = pairs.get(opening)
        if closing is None or index + 3 >= closing:
            continue
        digit_tokens: list[Any] = []
        cursor = opening + 1
        while cursor < closing and tokens[cursor].kind == "punct" and tokens[cursor].value.isascii() and tokens[cursor].value.isdigit():
            digit_tokens.append(tokens[cursor])
            cursor += 1
        if not digit_tokens or (len(digit_tokens) > 1 and any(a.end != b.start for a, b in zip(digit_tokens, digit_tokens[1:]))):
            continue
        entry_id = "".join(token.value for token in digit_tokens)
        if len(entry_id) > 16 or int(entry_id) > MAX_ENTRY_ID or cursor >= closing or tokens[cursor].value != ",":
            continue
        if cursor + 1 >= closing or tokens[cursor + 1].kind not in {"string", "long_string"}:
            continue
        try:
            text = mars_lua_discovery._literal_text(tokens[cursor + 1])
        except ValueError:
            continue
        ref = {"path": relative, "line": source.count("\n", 0, token.start) + 1,
               "start_offset": token.start, "end_offset": tokens[closing].end,
               "source_sha256": source_hash,
               "call_sha256": hashlib.sha256(source[token.start:tokens[closing].end].encode("utf-8")).hexdigest()}
        if entry_id in _SHARED_GAME_IDS:
            shared.append({"id": entry_id, "text": text, "ref": ref})
        else:
            found.append({"identity": f"existing-t\0{entry_id}", "explicit_id": entry_id,
                "text": text, "context": "Existing numeric T localization", "kind": "existing_t",
                "params": {}, "reason": None, "manual": False, "ref": ref})
    return found, shared


def _previous_entries(manifest: dict[str, Any] | None) -> dict[str, str]:
    entries = (manifest or {}).get("entries", {})
    result: dict[str, str] = {}
    if isinstance(entries, dict):
        for key, item in entries.items():
            if isinstance(item, dict) and item.get("identity"):
                result[str(item["identity"])] = str(key)
    elif isinstance(entries, list):
        for item in entries:
            if isinstance(item, dict) and item.get("identity"):
                result[str(item["identity"])] = str(item.get("id"))
    return result


def _stable_id(mod_id: str, identity: str, reserved: set[int]) -> str:
    raw = hashlib.sha256(f"remis-mars-lua-v1\0{mod_id}\0{identity}".encode("utf-8")).digest()
    candidate = int.from_bytes(raw[:8], "big") % (MAX_ENTRY_ID - MIN_GENERATED_ID + 1) + MIN_GENERATED_ID
    while candidate in reserved:
        candidate += 1
        if candidate > MAX_ENTRY_ID:
            candidate = MIN_GENERATED_ID
    reserved.add(candidate)
    return str(candidate)


def _scan_one_file(root: Path, path: Path, mod_id: str) -> dict[str, Any]:
    data = _read_utf8(path)
    source = data.decode("utf-8-sig", errors="strict")
    relative = path.relative_to(root).as_posix()
    source_hash = hashlib.sha256(data).hexdigest()
    result: dict[str, Any] = {"candidates": [], "shared": [], "profiles": [], "diagnostics": [], "reserved": set()}
    result["reserved"].update(int(value) for value in _NUMERIC_T.findall(source) if int(value) <= MAX_ENTRY_ID)
    try:
        candidates = mars_lua_discovery.scan_lua_text(source, relative, max_candidates=None)
    except ValueError as exc:
        result["diagnostics"].append({"code": "lua_scan_failed", "path": relative, "message": str(exc)})
        return result
    existing_t, shared = _existing_t_records(source, relative, source_hash)
    result["candidates"].extend(existing_t)
    result["shared"].extend(shared)
    for match in candidates:
        parsed = classify_argument(source, match.start_offset, match.end_offset)
        context = _context(source, match.start_offset)
        role = Path(relative).stem.casefold()
        identity = f"lua\0{role}\0{_scope(source, match.start_offset)}\0{context}"
        params = dict(parsed["params"])
        trait_profile = (mod_id == "kz4dEz" and relative.casefold() == "code/exotics_sanatoriumupgrade.lua"
                         and "EXOTIC_TRAIT_NAME" in params.values())
        if trait_profile:
            for name, expression in params.items():
                if expression == "EXOTIC_TRAIT_NAME":
                    params[name] = 'T(645893661115, "Telepath")'
            result["profiles"].append({"name": "telepath_trait_name", "supported": True,
                "reason": "UI parameter reuses existing ID 645893661115; the log-only alias stays unchanged."})
        result["candidates"].append({
            "identity": identity, "text": parsed["text"], "context": context,
            "kind": parsed["kind"], "params": params,
            "table_arguments": parsed.get("table_arguments", ""), "reason": parsed["reason"],
            "ref": {"path": relative, "line": match.line, "start_offset": match.start_offset,
                    "end_offset": match.end_offset, "source_sha256": source_hash,
                    "call_sha256": match.call_sha256},
        })
    result["candidates"].extend(_option_texts(source, relative, source_hash))
    for alias in _plain_text_aliases(source, relative, source_hash):
        if mod_id == "kz4dEz" and relative.casefold() == "code/exotics_sanatoriumupgrade.lua" and alias.get("alias_name") == "EXOTIC_TRAIT_NAME":
            result["diagnostics"].append({"code": "profiled_log_only_alias", "path": relative,
                "message": "EXOTIC_TRAIT_NAME is translated at its UI binding with existing ID 645893661115; its log use stays English."})
        else:
            result["candidates"].append(alias)
    shuttle_profile = _shuttle_dedup_profile(source, relative) if mod_id == "kz4dEz" else None
    if shuttle_profile is not None:
        for rewrite in shuttle_profile.get("rewrites", []):
            rewrite["source_sha256"] = source_hash
        result["profiles"].append(shuttle_profile)
    if "ModItemOptionChoice" in source:
        result["diagnostics"].append({"code": "plain_mod_option_strings", "path": relative,
            "message": "DisplayName/Help are extracted for review; ChoiceList values remain internal enum values."})
    return result


def _collect_source(root: Path, files: list[Path], mod_id: str) -> dict[str, Any]:
    collected: dict[str, Any] = {"candidates": [], "shared": [], "profiles": [], "diagnostics": [], "reserved": set()}
    for path in files:
        found = _scan_one_file(root, path, mod_id)
        for key in ("candidates", "shared", "profiles", "diagnostics"):
            collected[key].extend(found[key])
        collected["reserved"].update(found["reserved"])
    return collected


def _allocate_entry_id(candidate: dict[str, Any], previous: dict[str, str], identities: dict[str, str], reserved: set[int], mod_id: str) -> str:
    identity = candidate["identity"]
    if identity in identities:
        return identities[identity]
    if candidate.get("explicit_id"):
        selected = candidate["explicit_id"]
        reserved.add(int(selected))
    else:
        old_id = previous.get(identity)
        valid_old = old_id and old_id.isascii() and old_id.isdecimal() and int(old_id) <= MAX_ENTRY_ID
        if valid_old and int(old_id) not in reserved:
            selected = old_id
            reserved.add(int(selected))
        else:
            selected = _stable_id(mod_id, identity, reserved)
    identities[identity] = selected
    return selected


def _build_entries(mod_id: str, candidates: list[dict[str, Any]], reserved: set[int], previous_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    previous = _previous_entries(previous_manifest)
    entries: dict[str, dict[str, Any]] = {}
    identities: dict[str, str] = {}
    for candidate in candidates:
        entry_id = _allocate_entry_id(candidate, previous, identities, reserved, mod_id)
        reason = candidate["reason"]
        review = candidate["kind"] == "dynamic" or candidate.get("manual", False)
        render_data = {"id": entry_id, **candidate, "kind": "literal" if candidate["kind"] == "manual" else candidate["kind"]}
        replacement = None if candidate["kind"] == "existing_t" else render_rewrite(render_data)
        if replacement is None and candidate["kind"] != "existing_t":
            review = True
        entry = entries.setdefault(entry_id, {
            "id": entry_id, "text": candidate["text"], "context": candidate["context"],
            "kind": candidate["kind"], "params": candidate["params"], "refs": [],
            "rewrites": [], "identity": candidate["identity"],
            "review_required": review, "review_reason": reason if review else None,
        })
        if entry.get("text") != candidate["text"]:
            entry["review_required"] = True
            entry["review_reason"] = "multiple source texts share one semantic identity; review the binding"
            entry.setdefault("candidate_texts", [entry.get("text")]).append(candidate["text"])
        reference = candidate["ref"]
        entry["refs"].append(reference)
        entry["rewrites"].append({**reference, "replacement": replacement})
    return entries


def _attach_profile_ids(mod_id: str, entries: dict[str, dict[str, Any]], profiles: list[dict[str, Any]]) -> None:
    if mod_id != "kz4dEz":
        return
    shuttle_id = next((key for key, entry in entries.items() if entry.get("text") == "Shuttles"
                       and any(ref["path"].casefold() == "code/exotics_shuttlehubupgrade.lua" for ref in entry["refs"])), None)
    for profile in profiles:
        if profile.get("name") == "localized_shuttle_dedup":
            profile["trigger_id"] = shuttle_id
            if not shuttle_id:
                profile["supported"] = False
                profile["reason"] = "the Shuttles localization entry was not found"


def analyze_source(source_root: str | os.PathLike[str], previous_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a stable, language-neutral manifest from a source mod directory."""
    root = Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source_root must be a directory")
    files = _lua_paths(root)
    mod_id = _mod_id(root, files)
    collected = _collect_source(root, files, mod_id)
    entries = _build_entries(mod_id, collected["candidates"], collected["reserved"], previous_manifest)
    _attach_profile_ids(mod_id, entries, collected["profiles"])
    source_files = _source_file_hashes(root)
    digest = hashlib.sha256("\n".join(f"{path}\0{value}" for path, value in sorted(source_files.items())).encode("utf-8")).hexdigest()
    review_items = [
        {"id": key, "reason": value["review_reason"], "refs": value["refs"]}
        for key, value in entries.items() if value["review_required"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mod_id": mod_id,
        "source_fingerprint": digest,
        "source_files": source_files,
        "entries": entries,
        "shared_references": collected["shared"],
        "source_profiles": collected["profiles"],
        "review_items": review_items,
        "diagnostics": collected["diagnostics"],
        "reserved_ids": sorted(collected["reserved"]),
    }


def rewrite_sources(source_root: str | os.PathLike[str], manifest: dict[str, Any], approved_ids: set[str] | list[str] | None = None) -> dict[str, bytes]:
    """Return rewritten Lua file bytes for approved, hash-matching calls only."""
    root = Path(source_root).resolve(strict=True)
    approved = {str(value) for value in approved_ids} if approved_ids is not None else set()
    result: dict[str, bytes] = {}
    grouped: dict[str, list[tuple[int, int, str, str, str]]] = {}
    for key, entry in manifest.get("entries", {}).items():
        if approved_ids is None or str(key) not in approved:
            continue
        for rewrite in entry.get("rewrites", []):
            if rewrite.get("replacement") is None:
                continue
            grouped.setdefault(rewrite["path"], []).append((rewrite["start_offset"], rewrite["end_offset"], rewrite["call_sha256"], rewrite["replacement"], rewrite["source_sha256"]))
    for profile in manifest.get("source_profiles", []):
        trigger_id = str(profile.get("trigger_id", ""))
        if not profile.get("supported") or trigger_id not in approved:
            continue
        for rewrite in _fresh_profile_rewrites(root, profile):
            replacement = rewrite["replacement_template"].replace("{id}", trigger_id)
            grouped.setdefault(rewrite["path"], []).append((rewrite["start_offset"], rewrite["end_offset"], rewrite["call_sha256"], replacement, rewrite["source_sha256"]))
    for relative, changes in grouped.items():
        path = root / relative
        data = _read_utf8(path)
        original = data.decode("utf-8-sig", errors="strict")
        expected_source_hashes = {change[4] for change in changes}
        if len(expected_source_hashes) != 1 or hashlib.sha256(data).hexdigest() not in expected_source_hashes:
            raise ValueError(f"stale Lua source file: {relative}")
        for start, end, expected_hash, replacement, _source_hash in changes:
            call = original[start:end]
            if hashlib.sha256(call.encode("utf-8")).hexdigest() != expected_hash:
                raise ValueError(f"stale Lua rewrite source: {relative}:{start}")
        transformed = original
        for start, end, _expected_hash, replacement, _source_hash in sorted(changes, reverse=True):
            transformed = transformed[:start] + replacement + transformed[end:]
        prefix = b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
        result[relative] = prefix + transformed.encode("utf-8")
    return result


def _render_csv(entries: dict[str, dict[str, Any]]) -> str:
    from io import StringIO
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(surviving_mars_csv.HEADER)
    for key, entry in sorted(entries.items(), key=lambda item: (int(item[0]), item[0])):
        writer.writerow([key, entry.get("text") or "", "", "", entry.get("context") or ""])
    return output.getvalue()


def _fresh_profile_rewrites(root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Recompile reviewed built-in rewrites from guarded current source bytes."""
    if profile.get("name") != "localized_shuttle_dedup":
        return profile.get("rewrites", [])
    stored = profile.get("rewrites", [])
    if not stored:
        raise ValueError("stale Lua profile: localized_shuttle_dedup has no source anchors")
    relative = stored[0]["path"]
    data = _read_utf8(root / relative)
    hashes = {item.get("source_sha256") for item in stored}
    if len(hashes) != 1 or hashlib.sha256(data).hexdigest() not in hashes:
        raise ValueError(f"stale Lua source profile: {relative}")
    source = data.decode("utf-8-sig", errors="strict")
    fresh = _shuttle_dedup_profile(source, relative)
    if not fresh or not fresh.get("supported"):
        raise ValueError(f"stale Lua profile: localized_shuttle_dedup anchors changed in {relative}")
    old_guards = [(item.get("start_offset"), item.get("end_offset"), item.get("call_sha256")) for item in stored]
    new_guards = [(item.get("start_offset"), item.get("end_offset"), item.get("call_sha256")) for item in fresh["rewrites"]]
    if old_guards != new_guards:
        raise ValueError(f"stale Lua profile guards: {relative}")
    for rewrite in fresh["rewrites"]:
        rewrite["source_sha256"] = hashlib.sha256(data).hexdigest()
    return fresh["rewrites"]


def prepare_source(
    source_root: str | os.PathLike[str],
    output_root: str | os.PathLike[str],
    previous_manifest: dict[str, Any] | None = None,
    mode: str = "overlay",
    approved_ids: set[str] | list[str] | None = None,
) -> dict[str, Any]:
    """Materialize a deterministic CSV and manifest without replacing existing files."""
    if mode not in {"overlay", "source_copy"}:
        raise ValueError("mode must be 'overlay' or 'source_copy'")
    if mode == "source_copy" and approved_ids is None:
        raise ValueError("source_copy requires an explicit approved_ids snapshot")
    manifest = analyze_source(source_root, previous_manifest)
    selected = set(manifest["entries"]) if approved_ids is None else {str(value) for value in approved_ids}
    unknown = selected.difference(manifest["entries"])
    if unknown:
        raise ValueError(f"approved_ids contains unknown localization IDs: {', '.join(sorted(unknown))}")
    if approved_ids is not None:
        manifest["approved_ids"] = sorted(selected, key=lambda value: (int(value), value))
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "ModTexts.csv"
    manifest_path = output / "mars_lua_manifest.json"
    if csv_path.exists() or manifest_path.exists():
        raise FileExistsError("prepared output already exists; refusing overwrite")
    selected_entries = {key: value for key, value in manifest["entries"].items() if key in selected}
    csv_bytes = _render_csv(selected_entries).encode("utf-8")
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    rewritten = rewrite_sources(source_root, manifest, approved_ids) if mode == "source_copy" else {}
    source_copy_blockers = [
        key for key in selected
        if manifest["entries"][key]["kind"] != "existing_t"
        and (manifest["entries"][key].get("candidate_texts")
             or not any(ref.get("replacement") for ref in manifest["entries"][key]["rewrites"]))
    ] if mode == "source_copy" else []
    if mode == "source_copy":
        source_copy_blockers.extend(
            f"profile:{profile['name']}" for profile in manifest.get("source_profiles", [])
            if not profile.get("supported") and profile.get("name")
        )
    for relative in rewritten:
        target = output / "source" / relative
        if target.exists():
            raise FileExistsError(f"prepared source already exists: {relative}")
    output.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(csv_bytes)
    manifest_path.write_bytes(manifest_bytes)
    for relative, data in rewritten.items():
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {**manifest, "source_copy_blockers": sorted(source_copy_blockers),
            "artifacts": {"csv_path": str(csv_path), "manifest_path": str(manifest_path),
                          "rewritten_files": sorted(rewritten), "source_copy_complete": not source_copy_blockers}}
