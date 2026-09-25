"""Conservative Project Zomboid localization adapter.

This adapter treats translation resources as data, never executes Lua, and
renders source-preserving translation overlays for explicit review/workflows.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

from .contracts import Diagnostic, Discovery, Document, Entry, Resource


class ProjectZomboidAdapter:
    id = "project_zomboid"
    game_id = "project_zomboid"

    def language_folder(self, language: dict) -> str:
        explicit = language.get("pz_folder") or language.get("folder")
        if explicit:
            return str(explicit)
        candidates = (language.get("code"), language.get("key"), language.get("id"))
        raw = next((str(item) for item in candidates if item), "")
        normalized = raw.lower().replace("-", "_")
        aliases = {
            "en": "EN", "english": "EN", "l_english": "EN",
            "ru": "RU", "russian": "RU", "l_russian": "RU",
            "zh": "CH", "zh_cn": "CH", "zh_sg": "CH",
            "l_simp_chinese": "CH", "chinese": "CH", "ch": "CH",
            "de": "DE", "german": "DE", "l_german": "DE",
            "fr": "FR", "french": "FR", "l_french": "FR",
            "es": "ES", "spanish": "ES", "l_spanish": "ES",
            "it": "IT", "italian": "IT", "l_italian": "IT",
            "pl": "PL", "polish": "PL", "l_polish": "PL", "pt_br": "PTBR",
            "l_braz_por": "PTBR", "ko": "KO", "korean": "KO",
            "l_korean": "KO", "ja": "JP", "japanese": "JP", "l_japanese": "JP",
            "tr": "TR", "turkish": "TR", "l_turkish": "TR",
        }
        if normalized in aliases:
            return aliases[normalized]
        # Remis language keys commonly use l_<name>; preserve the game-facing
        # suffix when no explicit PZ mapping is supplied.
        return normalized.removeprefix("l_").upper() or "EN"

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...] | None:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)*)\s*", value)
        # PZ mod folders are build.major[.minor]; the third component does not
        # affect which game build folder is loaded.
        return tuple(int(part) for part in match.group(1).split(".")[:2]) if match else None

    @staticmethod
    def _is_link(path: Path) -> bool:
        try:
            if path.is_symlink():
                return True
            is_junction = getattr(path, "is_junction", None)
            if is_junction and is_junction():
                return True
            attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
            reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            return bool(reparse_point and attributes & reparse_point)
        except (OSError, AttributeError):
            return True

    @classmethod
    def _looks_like_mod(cls, path: Path) -> bool:
        if cls._is_link(path) or not path.is_dir():
            return False
        try:
            return ((path / "media").is_dir() or (path / "common").is_dir()
                    or (path / "mod.info").is_file()
                    or any(p.is_dir() and cls._version_tuple(p.name) for p in path.iterdir()))
        except OSError:
            return False

    @classmethod
    def _resolve_mod_root(cls, root: Path) -> tuple[Path | None, Diagnostic | None]:
        root = Path(root)
        if cls._is_link(root):
            return None, Diagnostic("linked_mod_root", "Linked or junction roots are not scanned.", str(root), "error")
        if cls._looks_like_mod(root):
            return root, None
        containers = (root / "Contents" / "mods", root / "mods")
        found = []
        for container in containers:
            if cls._is_link(container) or not container.is_dir():
                continue
            found.extend(path for path in container.iterdir() if cls._looks_like_mod(path))
        unique = sorted(set(found))
        if len(unique) == 1:
            return unique[0], None
        if len(unique) > 1:
            return None, Diagnostic("multiple_mod_roots", "The selected folder contains multiple mods; choose one mod directory before scanning.", str(root), "error")
        return None, Diagnostic("mod_root_not_found", "No Project Zomboid mod root was found at this folder or its standard Workshop mod containers.", str(root), "error")

    @staticmethod
    def _branch_roots(root: Path, game_version: str | None,
                      diagnostics: list[Diagnostic]) -> list[tuple[Path, str]]:
        if ProjectZomboidAdapter._is_link(root):
            diagnostics.append(Diagnostic("linked_root_skipped", "Linked or junction mod roots are not traversed.", str(root), "error"))
            return []
        try:
            children = list(root.iterdir()) if root.is_dir() else []
        except OSError:
            return []
        common = next((p for p in children if p.is_dir() and p.name.lower() == "common" and not ProjectZomboidAdapter._is_link(p)), None)
        versions = [p for p in children if p.is_dir() and ProjectZomboidAdapter._version_tuple(p.name) and not ProjectZomboidAdapter._is_link(p)]
        runtime = ProjectZomboidAdapter._version_tuple(game_version or "")
        if runtime and runtime[0] < 42 and (root / "media").is_dir():
            return [(root, "legacy-root")]
        selected: Path | None = None
        if versions and runtime:
            applicable = [(ProjectZomboidAdapter._version_tuple(p.name), p) for p in versions]
            applicable = [(v, p) for v, p in applicable if v and v <= runtime]
            if applicable:
                selected = max(applicable, key=lambda pair: (pair[0], len(pair[0])))[1]
            else:
                diagnostics.append(Diagnostic("version_branch_unmatched", "No version folder is applicable to the supplied game version; common resources remain eligible.", str(root)))
        elif versions:
            selected = max(versions, key=lambda p: ProjectZomboidAdapter._version_tuple(p.name) or ())
            diagnostics.append(Diagnostic("version_selection_inferred", f"Game version is unknown; selected locally newest version folder {selected.name!r} with common fallback.", str(root)))
        branches: list[tuple[Path, str]] = []
        if common:
            branches.append((common, "common"))
        if selected:
            branches.append((selected, selected.name))
        if not common and not versions:
            branches.append((root, "legacy-root"))
        return branches

    def discover(self, root: Path, source_lang: dict,
                 game_version: str | None = None) -> Discovery:
        project_root = Path(root)
        root, root_diagnostic = self._resolve_mod_root(project_root)
        diagnostics: list[Diagnostic] = []
        if root_diagnostic:
            return Discovery((), (root_diagnostic,))
        assert root is not None
        lang = self.language_folder(source_lang)
        winners: dict[str, Resource] = {}
        branches = self._branch_roots(root, game_version, diagnostics)
        for branch, branch_name in branches:
            chain = [branch / part for part in ("media", "media/lua", "media/lua/shared", "media/lua/shared/Translate")]
            if any(self._is_link(path) for path in chain):
                continue
            translate_root = chain[-1]
            if not translate_root.is_dir():
                continue
            lang_dir = next((p for p in translate_root.iterdir() if p.is_dir() and p.name.casefold() == lang.casefold() and not self._is_link(p)), None)
            if not lang_dir:
                continue
            for path in self._walk_data_files(lang_dir):
                if path.suffix.lower() not in {".json", ".txt"}:
                    continue
                if path.suffix.lower() == ".txt" and not path.stem.upper().endswith("_" + lang.upper()):
                    continue
                relative = path.relative_to(root).as_posix()
                package_inside = path.relative_to(branch).as_posix()
                package_path = f"common/{package_inside}" if branch_name != "legacy-root" else package_inside
                category = re.sub(r"_" + re.escape(lang) + r"$", "", path.stem, flags=re.IGNORECASE)
                winners[package_inside] = Resource(path, relative, {
                    "source_root": str(root), "branch": branch_name,
                    "project_root": str(project_root),
                    "source_mod_id": _mod_info_value(root, "id", branches),
                    "language_folder": lang, "category": category,
                    "stable_relative_path": package_path,
                    "game_version": game_version,
                })
        resources = tuple(winners[key] for key in sorted(winners))
        return Discovery(resources, tuple(diagnostics), {
            "game_version": game_version, "source_language_folder": lang,
            "source_root": str(root), "project_root": str(project_root),
            "source_mod_id": _mod_info_value(root, "id", branches),
        })

    @classmethod
    def _walk_data_files(cls, root: Path):
        """Walk only ordinary directories; prune symlinks and Windows reparse points."""
        root = Path(root)
        if cls._is_link(root):
            return
        for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            if cls._is_link(current_path):
                directories[:] = []
                continue
            directories[:] = sorted(
                name for name in directories
                if not cls._is_link(current_path / name)
            )
            for filename in sorted(filenames):
                candidate = current_path / filename
                if cls._is_link(candidate) or not candidate.is_file():
                    continue
                try:
                    candidate.resolve().relative_to(root.resolve())
                except (OSError, RuntimeError, ValueError):
                    continue
                yield candidate

    def parse(self, path: Path, metadata: dict | None = None) -> Document:
        path = Path(path)
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        return self.parse_text(text, path, metadata)

    def parse_text(self, text: str, path: Path, metadata: dict | None = None) -> Document:
        path = Path(path)
        meta = dict(metadata or {})
        inferred_category = re.sub(r"_[A-Z]{2,5}$", "", path.stem)
        category = str(meta.get("category") or inferred_category)
        stable_path = str(meta.get("stable_relative_path") or "")
        namespace = str(meta.get("category") or category)
        if path.suffix.lower() == ".json":
            spans, duplicates = _json_entries(text)
            if duplicates:
                raise ValueError(f"Duplicate JSON localization keys in {path}: {', '.join(duplicates)}")
            entries = tuple(Entry(f"{namespace}::{key}", value, line,
                                  {"resource_key": key, "category": category,
                                   "value_start": start, "value_end": end,
                                   "format": "json"})
                            for key, value, line, start, end in spans)
            meta.update({"format": "json", "category": category, "namespace": namespace, "stable_relative_path": stable_path})
            return Document(path, text, entries, meta)
        spans = _lua_table_entries(text)
        header = _legacy_table_header(text)
        if header is None:
            raise ValueError(f"Legacy PZ translation requires a language-qualified table name: {path}")
        header_language = text[header[0]:header[1]].upper()
        filename_language = str(meta.get("language_folder") or _filename_language(path.name))
        if filename_language and header_language != filename_language.upper():
            raise ValueError(f"Legacy table language {header_language!r} does not match file language {filename_language!r}: {path}")
        entries = tuple(Entry(f"{namespace}::{key}", value, line,
                              {"resource_key": key, "category": category,
                               "value_start": start, "value_end": end,
                               "format": "lua_table_txt"})
                        for key, value, line, start, end in spans)
        meta.update({"format": "lua_table_txt", "category": category, "namespace": namespace, "stable_relative_path": stable_path,
                     "language_folder": filename_language,
                     "table_header_span": header})
        return Document(path, text, entries, meta)

    def render(self, document: Document, translations: dict[str, str],
               target_lang: dict) -> dict[str, str]:
        folder = self.language_folder(target_lang)
        rel = str(document.metadata.get("stable_relative_path") or document.path.name)
        rel = _replace_language_segment(rel, folder)
        if rel.lower().endswith(".txt"):
            rel = re.sub(r"_[A-Z]{2,5}(?=\.txt$)", f"_{folder}", rel, flags=re.IGNORECASE)
        text = document.source_text
        replacements = []
        for entry in document.entries:
            if entry.status != "eligible" or entry.key not in translations:
                continue
            value = str(translations[entry.key])
            if value == entry.value:
                continue
            start, end = entry.metadata["value_start"], entry.metadata["value_end"]
            encoded = json.dumps(value, ensure_ascii=False) if entry.metadata["format"] == "json" else _lua_quote(value)
            replacements.append((start, end, encoded))
        for start, end, value in sorted(replacements, reverse=True):
            text = text[:start] + value + text[end:]
        if document.metadata.get("format") == "lua_table_txt":
            source_lang = str(document.metadata.get("language_folder") or "")
            span = document.metadata.get("table_header_span")
            if span and source_lang and source_lang.casefold() != folder.casefold():
                start, end = span
                text = text[:start] + folder + text[end:]
        return {rel: text}

    def package_metadata(self, root: Path, target_lang: dict,
                         game_version: str | None = None) -> dict[str, str]:
        root, diagnostic = self._resolve_mod_root(Path(root))
        if diagnostic or root is None:
            raise ValueError(diagnostic.message if diagnostic else "Project Zomboid mod root is unavailable")
        lang = self.language_folder(target_lang)
        version_diagnostics: list[Diagnostic] = []
        branches = self._branch_roots(root, game_version, version_diagnostics)
        branch = "common/" if any(name != "legacy-root" for _, name in branches) else ""
        source_info = self._read_mod_info(root, branches)
        source_id = source_info.get("id", "").strip()
        if not source_id:
            raise ValueError(f"Source mod.info has no id field: {root}")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("_.-") or "mod"
        mod_id = f"remis_translation_{safe_id}_{lang.lower()}"
        if mod_id.casefold() == source_id.casefold():
            mod_id = "remis_overlay_" + mod_id
        source_name = source_info.get("name", source_id).strip() or source_id
        mod_name = self._single_line(f"{source_name} - Remis Translation [{lang}]")
        description = self._single_line(f"Translation overlay for {source_id}; requires the original mod.")
        info = (f"id={self._single_line(mod_id)}\nname={mod_name}\n"
                f"description={description}\nrequire={self._single_line(source_id)}\n")
        return {f"{branch}mod.info": info}

    @staticmethod
    def _single_line(value: str) -> str:
        return " ".join(value.replace("\r", " ").replace("\n", " ").split())

    @classmethod
    def _read_mod_info(cls, root: Path, branches: list[tuple[Path, str]]) -> dict[str, str]:
        candidates = [branch / "mod.info" for branch, _ in reversed(branches)]
        candidates.extend((root / "common" / "mod.info", root / "mod.info"))
        for path in dict.fromkeys(candidates):
            if cls._is_link(path) or not path.is_file():
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
            values: dict[str, str] = {}
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "--")) or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                values[key.strip().lower()] = value.strip()
            return values
        raise ValueError(f"No source mod.info found for {root}")

    def validate(self, source: str, target: str) -> list[Diagnostic]:
        source_tokens = _protected_tokens(source)
        target_tokens = _protected_tokens(target)
        if source_tokens != target_tokens:
            return [Diagnostic("placeholder_mismatch", "PZ substitution tokens or markup differ in identity or count.", severity="error")]
        return []


def _replace_language_segment(path: str, target: str) -> str:
    parts = path.replace("\\", "/").split("/")
    for index, part in enumerate(parts):
        if part.casefold() == "translate" and index + 1 < len(parts):
            parts[index + 1] = target
            return "/".join(parts)
    return path


def _mod_info_value(root: Path, wanted: str,
                    branches: list[tuple[Path, str]]) -> str:
    """Read one scalar mod.info field without interpreting mod code."""
    branch_candidates = [branch / "mod.info" for branch, _ in reversed(branches)]
    branch_candidates.extend((root / "common" / "mod.info", root / "mod.info"))
    for candidate in dict.fromkeys(branch_candidates):
        if ProjectZomboidAdapter._is_link(candidate) or not candidate.is_file():
            continue
        with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith(("#", "--")) and "=" in stripped:
                    key, value = stripped.split("=", 1)
                    if key.strip().casefold() == wanted.casefold():
                        return value.strip()
        return ""
    return ""


def _json_entries(text: str) -> tuple[list[tuple[str, str, int, int, int]], list[str]]:
    decoder = json.JSONDecoder()
    index = 1 if text.startswith("\ufeff") else 0
    index = _skip_space(text, index)
    if index >= len(text) or text[index] != "{":
        raise ValueError("PZ JSON translation must be an object")
    index += 1
    result: list[tuple[str, str, int, int, int]] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    while True:
        index = _skip_space_and_commas(text, index)
        if index >= len(text):
            raise ValueError("Unterminated PZ JSON translation object")
        if text[index] == "}":
            break
        key_start = index
        key, key_end = decoder.raw_decode(text, index)
        if not isinstance(key, str):
            raise ValueError("PZ JSON translation keys must be strings")
        index = _skip_space(text, key_end)
        if index >= len(text) or text[index] != ":":
            raise ValueError("Expected colon after PZ JSON key")
        value_start = _skip_space(text, index + 1)
        value, value_end = decoder.raw_decode(text, value_start)
        if not isinstance(value, str):
            shape = "nested object or array" if isinstance(value, (dict, list)) else type(value).__name__
            raise ValueError(f"Unsupported {shape} at PZ JSON translation key {key!r}; expected a string value")
        if key in seen:
            duplicates.append(key)
        seen.add(key)
        result.append((key, value, text.count("\n", 0, key_start) + 1, value_start, value_end))
        index = value_end
        index = _skip_space(text, index)
        if index < len(text) and text[index] == ",":
            index += 1
        elif index < len(text) and text[index] != "}":
            raise ValueError("Expected comma or object end in PZ JSON translation")
    # Let the standard parser enforce trailing syntax and reject NaN/constants.
    json.loads(text[1:] if text.startswith("\ufeff") else text,
               object_pairs_hook=list, parse_constant=_reject_json_constant)
    return result, duplicates


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _skip_space_and_commas(text: str, index: int) -> int:
    while index < len(text) and (text[index].isspace() or text[index] == ","):
        index += 1
    return index


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Unsupported JSON constant: {value}")


_LUA_TOKEN = re.compile(r"(?P<space>\s+)|(?P<blockcomment>--\[\[.*?\]\])|(?P<linecomment>--[^\r\n]*)|(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|(?P<ident>[A-Za-z_][A-Za-z0-9_.]*)|(?P<symbol>[{}=,;])|(?P<other>.)", re.S)


def _lua_table_entries(text: str) -> list[tuple[str, str, int, int, int]]:
    tokens = [(m.lastgroup, m.group(), m.start(), m.end()) for m in _LUA_TOKEN.finditer(text)
              if m.lastgroup not in {"space", "linecomment", "blockcomment"} and not (m.start() == 0 and m.group() == "\ufeff")]
    if len(tokens) < 3:
        raise ValueError("Empty or unsupported PZ Lua-table translation")
    cursor = 0
    if tokens[0][0] == "ident" and tokens[1][1] == "=":
        cursor = 2
    if tokens[cursor][1] != "{":
        raise ValueError("Expected a literal Lua table constructor")
    cursor += 1
    values: list[tuple[str, str, int, int, int]] = []
    seen: set[str] = set()
    while cursor < len(tokens) and tokens[cursor][1] != "}":
        key_token = tokens[cursor]
        if key_token[1] == "[" and cursor + 2 < len(tokens) and tokens[cursor + 1][0] == "string" and tokens[cursor + 2][1] == "]":
            key_token = tokens[cursor + 1]
            key = _decode_lua_string(key_token[1])
            cursor += 3
        elif key_token[0] == "string":
            key = _decode_lua_string(key_token[1])
            cursor += 1
        elif key_token[0] == "ident":
            key = key_token[1]
            cursor += 1
        else:
            raise ValueError("Only literal string or identifier keys are allowed")
        if cursor >= len(tokens) or tokens[cursor][1] != "=":
            raise ValueError("Expected equals after literal Lua table key")
        cursor += 1
        if cursor >= len(tokens) or tokens[cursor][0] != "string":
            raise ValueError(f"Value for {key!r} must be a literal string")
        value_token = tokens[cursor]
        value = _decode_lua_string(value_token[1])
        if key in seen:
            raise ValueError(f"Duplicate Lua-table translation key: {key}")
        seen.add(key)
        values.append((key, value, text.count("\n", 0, key_token[2]) + 1,
                       value_token[2], value_token[3]))
        cursor += 1
        if cursor < len(tokens) and tokens[cursor][1] in {",", ";"}:
            cursor += 1
        elif cursor < len(tokens) and tokens[cursor][1] != "}":
            raise ValueError("Expected comma or table end after Lua-table entry")
    if cursor >= len(tokens) or tokens[cursor][1] != "}" or cursor != len(tokens) - 1:
        raise ValueError("Unsupported trailing or malformed Lua-table syntax")
    return values


def _legacy_table_header(text: str) -> tuple[int, int] | None:
    tokens = [(m.lastgroup, m.group(), m.start(), m.end()) for m in _LUA_TOKEN.finditer(text)
              if m.lastgroup not in {"space", "linecomment", "blockcomment"} and not (m.start() == 0 and m.group() == "\ufeff")]
    if len(tokens) < 3 or tokens[0][0] != "ident" or tokens[1][1] != "=" or tokens[2][1] != "{":
        return None
    match = re.search(r"_([A-Z]{2,5})$", tokens[0][1])
    if not match:
        return None
    return tokens[0][2] + match.start(1), tokens[0][2] + match.end(1)


def _filename_language(filename: str) -> str:
    match = re.search(r"_([A-Z]{2,5})\.txt$", filename, re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _decode_lua_string(token: str) -> str:
    body = token[1:-1]
    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
    return re.sub(r"\\([nrt\\\"'])", lambda match: escapes[match.group(1)], body)


def _lua_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + '"'


_TOKEN_RE = re.compile(r"%\d+|%[sdif]|<[^<>\r\n]*>|\[[^\[\]\r\n]*\]")


def _protected_tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted(_TOKEN_RE.findall(text)))
