"""Build editable, translation-only Surviving Mars Mod packages.

This module reads Mod metadata as inert text and CSV localization tables only.
It never imports or executes Mod Lua and never copies source code or assets.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from typing import Any

from scripts.core import surviving_mars_csv
from scripts.core.services.mars_mod_metadata import MetadataParseError, top_mod_fields


LANGUAGE_NAMES = {
    "en": "English",
    "zh-CN": "Schinese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Koreana",
    "pl": "Polish",
    "pt-BR": "Brazilian",
    "ru": "Russian",
    "tr": "Turkish",
    "ar-SA": "Arabic",
    "bg-BG": "Bulgarian",
    "cs-CZ": "Czech",
    "da-DK": "Danish",
    "nl-NL": "Dutch",
    "en-US": "English",
    "fi-FI": "Finnish",
    "fr-FR": "French",
    "de-DE": "German",
    "el-GR": "Greek",
    "hu-HU": "Hungarian",
    "id-ID": "Indonesian",
    "it-IT": "Italian",
    "ja-JP": "Japanese",
    "ko-KR": "Koreana",
    "nb-NO": "Norwegian",
    "pl-PL": "Polish",
    "pt-PT": "Portuguese",
    "ro-RO": "Romanian",
    "ru-RU": "Russian",
    "es-ES": "Spanish",
    "es-MX": "Latam",
    "sv-SE": "Swedish",
    "zh-TW": "Tchinese",
    "th-TH": "Thai",
    "tr-TR": "Turkish",
    "uk-UA": "Ukrainian",
    "vi-VN": "Vietnamese",
}

# These are the language packs present in the inspected Relaunched install.
# Other SDK language tokens remain exportable but are explicitly unverified.
INSTALLED_LANGUAGE_CODES = frozenset(
    {
        "pt-BR", "en", "fr", "de", "es", "pl", "ru", "tr", "zh-CN",
        "en-US", "fr-FR", "de-DE", "pl-PL", "ru-RU", "es-ES", "tr-TR",
    }
)
MIN_LUA_REVISION = 350453
MAX_METADATA_BYTES = 2_000_000
MAX_CSV_BYTES = 32_000_000
MAX_CSV_FILES = 500
_SAFE_SOURCE_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_OUTPUT_ID_SLUG = re.compile(r"[^A-Za-z0-9]+")


class TranslationPackageError(ValueError):
    """Raised when an input cannot safely produce a translation-only package."""


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _assert_input_root(path: Path, label: str) -> Path:
    if _is_reparse(path) or not path.is_dir():
        raise TranslationPackageError(f"{label} must be an existing, non-linked directory.")
    return path.resolve(strict=True)


def _walk_csv_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        names[:] = sorted(
            name for name in names
            if not name.startswith(".") and not _is_reparse(base / name)
        )
        for name in sorted(files):
            candidate = base / name
            if candidate.suffix.lower() == ".csv" and not _is_reparse(candidate):
                paths.append(candidate)
                if len(paths) > MAX_CSV_FILES:
                    raise TranslationPackageError("CSV resource scan limit reached.")
    return paths


def _safe_relative_csv(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    parts = relative.parts
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(char in part for char in '<>:"|?*')
                or part.split(".", 1)[0].upper() in reserved):
            raise TranslationPackageError(f"Unsafe CSV resource path: {relative}")
    return PurePosixPath(*parts).as_posix()


def _read_bytes(path: Path, maximum: int) -> bytes:
    data = path.read_bytes()
    if len(data) > maximum:
        raise TranslationPackageError(f"Input file exceeds size limit: {path.name}")
    return data


def read_source_metadata(source_root: Path) -> dict[str, str]:
    """Read literal top-level source ID/title without evaluating Lua."""
    root = _assert_input_root(Path(source_root), "Source Mod")
    path = root / "metadata.lua"
    if not path.exists():
        return {"id": "", "title": ""}
    if _is_reparse(path) or not path.is_file():
        raise TranslationPackageError("metadata.lua must be a regular, non-linked file.")
    data = _read_bytes(path, MAX_METADATA_BYTES)
    try:
        source = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TranslationPackageError("metadata.lua must be valid UTF-8.") from exc
    try:
        return top_mod_fields(source)
    except MetadataParseError as exc:
        raise TranslationPackageError(str(exc)) from exc


def _source_identity(
    source_root: Path,
    source_mod_id: str | None,
    source_mod_title: str | None,
) -> tuple[str, str, str]:
    root = _assert_input_root(Path(source_root), "Source Mod")
    metadata_path = root / "metadata.lua"
    metadata_bytes = b""
    if metadata_path.exists():
        if _is_reparse(metadata_path) or not metadata_path.is_file():
            raise TranslationPackageError("metadata.lua must be a regular, non-linked file.")
        metadata_bytes = _read_bytes(metadata_path, MAX_METADATA_BYTES)
        try:
            fields = top_mod_fields(metadata_bytes.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise TranslationPackageError("metadata.lua must be valid UTF-8.") from exc
        except MetadataParseError as exc:
            raise TranslationPackageError(str(exc)) from exc
    else:
        fields = {"id": "", "title": ""}
    parsed_id = fields.get("id", "").strip()
    selected_id = (source_mod_id or parsed_id).strip()
    if not selected_id:
        raise TranslationPackageError("The original Mod ID is required to declare a dependency.")
    if not _SAFE_SOURCE_ID.fullmatch(selected_id):
        raise TranslationPackageError("The original Mod ID contains unsupported characters.")
    if parsed_id and source_mod_id and parsed_id != source_mod_id:
        raise TranslationPackageError("The selected original Mod ID does not match metadata.lua.")
    title = (source_mod_title if source_mod_title is not None else fields.get("title", "")).strip()
    return selected_id, title, hashlib.sha256(metadata_bytes).hexdigest()


def _language(language_code: str) -> str:
    if not isinstance(language_code, str) or language_code not in LANGUAGE_NAMES:
        raise TranslationPackageError(f"Unsupported Surviving Mars target language: {language_code!r}")
    return LANGUAGE_NAMES[language_code]


def _stable_mod_id(source_mod_id: str, language_code: str) -> str:
    slug = _OUTPUT_ID_SLUG.sub("", source_mod_id)[:10] or "Source"
    digest = hashlib.sha256(
        f"{source_mod_id}\0{language_code}".encode("utf-8")
    ).hexdigest()[:10]
    result = f"RemisTr{slug}{digest}"
    if result == source_mod_id:
        result = f"RemisTr{digest}{slug}"
    return result


def _lua_string(value: str) -> str:
    if "\x00" in value:
        raise TranslationPackageError("Lua metadata values cannot contain NUL characters.")
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t"))
    return f'"{escaped}"'


def _display_title(source_title: str, language: str) -> str:
    clean_title = " ".join(source_title.split()) or "Mod"
    result = f"[{language}] {clean_title}"
    return result[:60]


def _csv_rows(document: surviving_mars_csv.CsvDocument) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in document.rows[document.header_row_index + 1:]:
        if not row:
            continue
        result[row[0]] = list(row)
    return result


def _localized_csv(
    source_doc: surviving_mars_csv.CsvDocument,
    translation_doc: surviving_mars_csv.CsvDocument,
    relative_path: str,
) -> tuple[str, dict[str, str], int]:
    source_rows = _csv_rows(source_doc)
    target_rows = _csv_rows(translation_doc)
    if source_rows.keys() != target_rows.keys():
        missing = sorted(source_rows.keys() - target_rows.keys())
        extra = sorted(target_rows.keys() - source_rows.keys())
        raise TranslationPackageError(
            f"CSV IDs differ for {relative_path}; missing={missing[:3]}, extra={extra[:3]}"
        )
    translated_by_id: dict[str, str] = {}
    changed = 0
    empty_ids: list[str] = []
    for key, source_row in source_rows.items():
        target_row = target_rows[key]
        if any(source_row[index] != target_row[index] for index in (0, 1, 3, 4)):
            raise TranslationPackageError(
                f"Source columns changed for ID {key} in {relative_path}."
            )
        translated = target_row[2]
        if surviving_mars_csv.compare_newlines(source_row[1], translated).is_mismatch:
            raise TranslationPackageError(
                f"CSV line breaks differ for ID {key} in {relative_path}; "
                "preserve real line breaks instead of literal backslash-n text."
            )
        if translated.strip():
            tag_mismatch = surviving_mars_csv.compare_tags(source_row[1], translated)
            if tag_mismatch.is_mismatch:
                raise TranslationPackageError(
                    f"Tag mismatch for localization ID {key} in {relative_path}: "
                    f"missing={list(tag_mismatch.missing)}, unexpected={list(tag_mismatch.unexpected)}"
                )
            changed += 1
        else:
            empty_ids.append(key)
        translated_by_id[key] = translated

    if empty_ids:
        raise TranslationPackageError(
            f"Missing translations for {len(empty_ids)} IDs in {relative_path}: {empty_ids[:5]}"
        )
    if changed == 0:
        raise TranslationPackageError(f"No translated entries found in {relative_path}.")

    rows = [list(row) for row in source_doc.rows]
    for row in rows[source_doc.header_row_index + 1:]:
        if row:
            row[2] = translated_by_id[row[0]]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=source_doc.line_ending)
    writer.writerows(rows)
    result = output.getvalue()
    surviving_mars_csv.parse_text(result)
    conflicts = {key: value for key, value in translated_by_id.items() if value.strip()}
    return result, conflicts, changed


def _discover_source_tables(
    source: Path,
) -> dict[str, tuple[Path, bytes, surviving_mars_csv.CsvDocument]]:
    result: dict[str, tuple[Path, bytes, surviving_mars_csv.CsvDocument]] = {}
    for path in _walk_csv_files(source):
        if not surviving_mars_csv.is_table_file(path):
            continue
        relative = _safe_relative_csv(path, source)
        folded = relative.casefold()
        if folded in result:
            raise TranslationPackageError(f"Ambiguous source CSV paths differ only by case: {relative}")
        try:
            raw = _read_bytes(path, MAX_CSV_BYTES)
            document = surviving_mars_csv.parse_text(raw.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise TranslationPackageError(f"CSV must be valid UTF-8: {path.name}") from exc
        except OSError as exc:
            raise TranslationPackageError(f"Unable to read source CSV {path.name}: {exc}") from exc
        result[folded] = (path, raw, document)
    if not result:
        raise TranslationPackageError(
            "No recognized Surviving Mars localization CSVs were found in the source Mod."
        )
    return result


def _discover_translation_tables(root: Path) -> dict[str, tuple[Path, bytes]]:
    result: dict[str, tuple[Path, bytes]] = {}
    for path in _walk_csv_files(root):
        if not surviving_mars_csv.is_table_file(path):
            continue
        relative = _safe_relative_csv(path, root)
        folded = relative.casefold()
        if folded in result:
            raise TranslationPackageError(f"Ambiguous translation CSV paths differ only by case: {relative}")
        result[folded] = (path, _read_bytes(path, MAX_CSV_BYTES))
    return result


def _localize_tables(
    source: Path,
    translation_root: Path,
    translations: dict[str, tuple[Path, bytes]],
    source_files: dict[str, tuple[Path, bytes, surviving_mars_csv.CsvDocument]],
    language: str,
    metadata_hash: str,
) -> tuple[dict[str, str], list[dict[str, str]], dict[str, str], dict[str, str], list[str], int]:
    warnings: list[str] = []
    output_texts: dict[str, str] = {}
    source_hashes = {"metadata.lua": metadata_hash}
    translation_hashes: dict[str, str] = {}
    all_translations: dict[str, str] = {}
    localized_tables: list[dict[str, str]] = []
    translated_entries = 0
    for folded, (source_path, source_raw, source_doc) in sorted(source_files.items()):
        source_relative = _safe_relative_csv(source_path, source)
        source_hashes[source_relative] = hashlib.sha256(source_raw).hexdigest()
        target_match = translations.get(folded)
        if target_match is None:
            warnings.append(f"No matching translation CSV for source table {source_relative}; table omitted.")
            continue
        target_path, target_raw = target_match
        target_relative = _safe_relative_csv(target_path, translation_root)
        try:
            target_doc = surviving_mars_csv.parse_text(target_raw.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise TranslationPackageError(f"Translation CSV must be valid UTF-8: {target_relative}") from exc
        localized, translated_by_id, count = _localized_csv(source_doc, target_doc, source_relative)
        for key, text in translated_by_id.items():
            previous = all_translations.get(key)
            if previous is not None and previous != text:
                raise TranslationPackageError(
                    f"Conflicting translations for localization ID {key} across source tables."
                )
            all_translations[key] = text
        translation_hashes[source_relative] = hashlib.sha256(target_raw).hexdigest()
        translated_entries += count
        output_relative = f"Localization/{language}/{source_relative}"
        output_texts[output_relative] = localized
        localized_tables.append({"filename": output_relative, "language": language})
    if not output_texts:
        raise TranslationPackageError("No recognized source CSV has matching translated entries.")
    return output_texts, localized_tables, source_hashes, translation_hashes, warnings, translated_entries


def _lua_metadata_files(
    localized_tables: list[dict[str, str]],
    title: str,
    mod_id: str,
    source_mod_id: str,
    source_mod_title: str,
    author: str,
) -> dict[str, str]:
    metadata_lua = [
        "return PlaceObj('ModDef', {",
        f"    'title', {_lua_string(title)},",
        f"    'id', {_lua_string(mod_id)},",
        f"    'author', {_lua_string(author)},",
        f"    'lua_revision', {MIN_LUA_REVISION},",
        "    'optional_mod', true,",
        "    'dependencies', {",
        "        PlaceObj('ModDependency', {",
        f"            'id', {_lua_string(source_mod_id)},",
        f"            'title', {_lua_string(source_mod_title or source_mod_id)},",
        "            'required', true,",
        "        }),",
        "    },",
        "    'loctables', {",
    ]
    for table in localized_tables:
        mounted_filename = f"Mod/{mod_id}/{table['filename']}"
        metadata_lua.append(
            "        { filename = " + _lua_string(mounted_filename)
            + ", language = " + _lua_string(table["language"]) + " },"
        )
    metadata_lua.extend(["    },", "})", ""])
    items_lua = ["return {"]
    for table in localized_tables:
        mounted_filename = f"Mod/{mod_id}/{table['filename']}"
        items_lua.extend([
            "    PlaceObj('ModItemLocTable', {",
            f"        'language', {_lua_string(table['language'])},",
            f"        'filename', {_lua_string(mounted_filename)},",
            "    }),",
        ])
    items_lua.extend(["}", ""])
    return {"metadata.lua": "\n".join(metadata_lua), "items.lua": "\n".join(items_lua)}


def _facts_and_files(
    output_texts: dict[str, str],
    localized_tables: list[dict[str, str]],
    *,
    source_hashes: dict[str, str],
    translation_hashes: dict[str, str],
    language_code: str,
    language: str,
    source_mod_id: str,
    source_mod_title: str,
    mod_id: str,
    title: str,
    author: str,
    warnings: list[str],
    translated_entries: int,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    output_texts.update(_lua_metadata_files(
        localized_tables, title, mod_id, source_mod_id, source_mod_title, author,
    ))
    rendered = {path: value.encode("utf-8") for path, value in output_texts.items()}
    input_record = {
        "output_hashes": {path: hashlib.sha256(content).hexdigest()
                          for path, content in rendered.items()},
        "source_hashes": source_hashes,
        "translation_hashes": translation_hashes,
        "language_code": language_code,
        "game_language": language,
        "source_mod_id": source_mod_id,
        "source_mod_title": source_mod_title,
        "mod_id": mod_id,
        "title": title,
        "author": author,
    }
    fingerprint = hashlib.sha256(
        json.dumps(input_record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    file_list = [
        {"path": path, "size_bytes": len(contents)}
        for path, contents in sorted(rendered.items())
    ]
    total_size = sum(item["size_bytes"] for item in file_list)
    installation_steps = [
        f"Keep the original Mod {source_mod_id} installed and enabled; this translation Mod requires it.",
        "Copy this package folder into the game's user Mods folder, then enable the separate translation Mod.",
        f"The localization table is registered for {language}; in-game loading has not been verified.",
    ]
    facts = {
        "package": {
            "mod_id": mod_id,
            "title": title,
            "language": language_code,
            "game_language": language,
            "source_mod_id": source_mod_id,
            "files": file_list,
            "total_size_bytes": total_size,
        },
        "fingerprint": fingerprint,
        "warnings": warnings,
        "installation_steps": installation_steps,
        "source_hashes": source_hashes,
        "translation_hashes": translation_hashes,
        "translated_entry_count": translated_entries,
        "runtime_verified": False,
    }
    return facts, rendered


def _translation_plan(
    source_root: Path,
    translation_root: Path,
    language_code: str,
    source_mod_id: str | None,
    source_mod_title: str | None,
    author: str | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    source = _assert_input_root(Path(source_root), "Source Mod")
    translations_root = _assert_input_root(Path(translation_root), "Translation output")
    if source == translations_root:
        raise TranslationPackageError("Source Mod and translation output must be separate directories.")
    language = _language(language_code)
    original_id, original_title, metadata_hash = _source_identity(
        source, source_mod_id, source_mod_title
    )
    if author is not None and (not isinstance(author, str) or "\x00" in author):
        raise TranslationPackageError("Author must be plain text without NUL characters.")
    author_text = " ".join((author or "Remis").split())[:100] or "Remis"
    mod_id = _stable_mod_id(original_id, language_code)
    if mod_id == original_id:
        raise TranslationPackageError("Generated translation Mod ID collides with the source Mod ID.")
    source_files = _discover_source_tables(source)
    target_files = _discover_translation_tables(translations_root)
    localized = _localize_tables(
        source, translations_root, target_files, source_files, language, metadata_hash
    )
    output_texts, tables, source_hashes, target_hashes, warnings, count = localized
    if language_code not in INSTALLED_LANGUAGE_CODES:
        warnings.insert(0, f"SDK language token {language} is recognized, but no matching language FPK was present in the inspected local installation; runtime language availability is unverified.")
    title = _display_title(original_title, language)
    return _facts_and_files(
        output_texts,
        tables,
        source_hashes=source_hashes,
        translation_hashes=target_hashes,
        language_code=language_code,
        language=language,
        source_mod_id=original_id,
        source_mod_title=original_title,
        mod_id=mod_id,
        title=title,
        author=author_text,
        warnings=warnings,
        translated_entries=count,
    )


def inspect_package_inputs(
    source_root: Path,
    translation_root: Path,
    language_code: str,
    source_mod_id: str | None = None,
    source_mod_title: str | None = None,
    author: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe package preview without writing any files."""
    facts, _ = _translation_plan(
        source_root, translation_root, language_code,
        source_mod_id, source_mod_title, author,
    )
    return facts


def _assert_destination_safe(destination: Path, inputs: tuple[Path, Path]) -> None:
    absolute = Path(os.path.abspath(destination))
    for input_root in inputs:
        resolved = input_root.resolve(strict=True)
        try:
            absolute.resolve(strict=False).relative_to(resolved)
        except ValueError:
            continue
        raise TranslationPackageError("Package destination cannot be inside a source or translation directory.")
    cursor = absolute.parent
    while cursor != cursor.parent:
        if _is_reparse(cursor):
            raise TranslationPackageError("Package destination cannot pass through a symbolic link or junction.")
        cursor = cursor.parent


def build_package(
    source_root: Path,
    translation_root: Path,
    language_code: str,
    destination_root: Path,
    *,
    source_mod_id: str | None = None,
    source_mod_title: str | None = None,
    author: str | None = None,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Atomically write a new package directory and refuse existing targets."""
    source = _assert_input_root(Path(source_root), "Source Mod")
    translations = _assert_input_root(Path(translation_root), "Translation output")
    facts, rendered = _translation_plan(
        source, translations, language_code,
        source_mod_id, source_mod_title, author,
    )
    if expected_fingerprint and facts["fingerprint"] != expected_fingerprint:
        raise TranslationPackageError("Package inputs changed after preview; inspect them again before export.")
    destination = Path(os.path.abspath(destination_root))
    _assert_destination_safe(destination, (source, translations))
    if destination.exists() or _is_reparse(destination):
        raise FileExistsError(f"Package destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _is_reparse(destination.parent):
        raise TranslationPackageError("Package destination parent cannot be a link or junction.")
    temp_path = Path(tempfile.mkdtemp(prefix=".mars-package-", dir=destination.parent))
    try:
        for relative, content in rendered.items():
            relative_path = PurePosixPath(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise TranslationPackageError("Generated package path escaped its root.")
            target = temp_path.joinpath(*relative_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if _is_reparse(target) or _is_reparse(target.parent):
                raise TranslationPackageError("Generated package contains an unsafe linked path.")
            with target.open("xb") as handle:
                handle.write(content)
        for relative, expected in rendered.items():
            actual = temp_path.joinpath(*PurePosixPath(relative).parts).read_bytes()
            if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
                raise TranslationPackageError("Package file changed during write.")
        os.rename(temp_path, destination)
    except Exception:
        if (temp_path.exists() and not _is_reparse(temp_path)
                and temp_path.resolve().parent == destination.parent.resolve()):
            shutil.rmtree(temp_path, ignore_errors=True)
        raise
    return {
        "package_path": str(destination),
        "files": facts["package"]["files"],
        "size_bytes": facts["package"]["total_size_bytes"],
        "installation_steps": facts["installation_steps"],
        "runtime_verified": False,
        "fingerprint": facts["fingerprint"],
    }
