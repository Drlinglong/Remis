"""Proofreading operations for Surviving Mars ModItemLocTable CSV files."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from scripts.core import surviving_mars_csv
from scripts.schemas.common import LanguageCode


def _revision(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: str | Path, content: str) -> None:
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8",
            newline="",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as handle:
            temporary = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _source_file(project: Dict[str, Any], target_path: str | Path) -> Optional[Path]:
    source_root = Path(project.get("source_path", ""))
    if not source_root.is_dir():
        return None
    target = Path(target_path)
    candidates: List[Path] = []
    try:
        candidates.append(source_root / target.resolve().relative_to(source_root.resolve()))
    except (OSError, ValueError):
        pass
    candidates.extend(source_root.rglob(target.name))
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file() and surviving_mars_csv.is_table_file(candidate):
            return candidate
    return None


def _target_language(target_path: str | Path, fallback: str = "zh-CN") -> str:
    codes = sorted((language.value for language in LanguageCode), key=len, reverse=True)
    for part in reversed(Path(target_path).parts):
        try:
            return LanguageCode.from_str(part).value
        except ValueError:
            # Initial translation owns roots such as fr-prepared / pt-BR-prepared.
            # Match the entire language prefix so German edits never sync into Chinese.
            for code in codes:
                if part.casefold().startswith(code.casefold() + "-"):
                    return code
    return fallback


def _archive_translation_map(
    service: Any,
    project: Dict[str, Any],
    source_file: Path,
    language: str,
) -> Dict[str, str]:
    try:
        records = service.archive_manager.get_entries(
            mod_name=project.get("name"),
            file_path=str(source_file),
            language=language,
        )
        if not records:
            records = service.archive_manager.get_entries(
                mod_name=Path(project["source_path"]).name,
                file_path=str(source_file),
                language=language,
            )
    except Exception:
        return {}
    return {
        str(record["key"]): str(record["translation"])
        for record in records
        if record.get("translation")
    }


def _lookup(mapping: Dict[str, str], key: str) -> Optional[str]:
    if key in mapping:
        return mapping[key]
    base_key = key.split(":", 1)[0]
    return mapping.get(base_key) or mapping.get(f"{base_key}:0")


def _row_key_map(document: surviving_mars_csv.CsvDocument) -> Dict[int, Dict[str, Any]]:
    return {
        index: {"key_part": entry.key, "row_index": entry.row_index}
        for index, entry in enumerate(document.entries)
    }


def _build_values(
    source_entries: Iterable[surviving_mars_csv.CsvEntry],
    target_values: Dict[str, str],
    archive_values: Dict[str, str],
) -> tuple[List[Dict[str, Any]], List[str], List[str]]:
    rows: List[Dict[str, Any]] = []
    ai_values: List[str] = []
    final_values: List[str] = []
    for entry in source_entries:
        ai_value = _lookup(archive_values, entry.key)
        if ai_value is None:
            ai_value = f"⚠️ [DB_MISSING] {entry.value}"
        final_value = target_values.get(entry.key) or ai_value
        ai_values.append(ai_value)
        final_values.append(final_value)
        rows.append({
            "entry_id": f"entry-{len(rows)}",
            "row_type": "translation",
            "line_number": entry.line_number,
            "key": entry.key,
            "source_value": entry.value,
            "ai_value": ai_value,
            "final_value": final_value,
            "editable": True,
            "issues": [],
        })
    return rows, ai_values, final_values


async def get_proofread_data(
    service: Any,
    project: Dict[str, Any],
    target_file_path: str,
    file_id: str,
) -> Dict[str, Any]:
    """Build the existing proofreading response shape from CSV columns."""
    target_document = surviving_mars_csv.parse_file(Path(target_file_path))
    source_file = _source_file(project, target_file_path) or Path(target_file_path)
    source_document = surviving_mars_csv.parse_file(source_file)
    target_values = {
        entry.key: entry.value
        for entry in surviving_mars_csv.entries(target_file_path, "Translation")
    }
    language = _target_language(target_file_path)
    archive_values = _archive_translation_map(service, project, source_file, language)
    rows, ai_values, final_values = _build_values(
        source_document.entries,
        target_values,
        archive_values,
    )
    key_map = _row_key_map(source_document)
    ai_content = surviving_mars_csv.rewrite_text(
        target_document.source_text,
        ai_values,
        key_map,
    )
    final_content = surviving_mars_csv.rewrite_text(
        target_document.source_text,
        final_values,
        key_map,
    )
    return {
        "file_id": file_id,
        "file_path": target_file_path,
        "mod_name": project.get("name", ""),
        "entries": [
            {
                "key": row["key"],
                "original": row["source_value"],
                "translation": row["final_value"],
                "line_number": row["line_number"],
            }
            for row in rows
        ],
        "rows": rows,
        "file_content": target_document.source_text,
        "ai_content": ai_content,
        "final_content": final_content,
        "document_revision": _revision(target_file_path),
    }


async def save_proofread_data(
    service: Any,
    project: Dict[str, Any],
    target_file_path: str,
    file_id: str,
    entries_list: List[Dict[str, Any]],
    structure_patches: Optional[List[Dict[str, Any]]] = None,
    target_language: str = "zh-CN",
) -> Dict[str, Any] | bool:
    """Persist user edits to only the CSV Translation column."""
    if structure_patches:
        raise ValueError("Surviving Mars CSV files do not have editable structure rows.")
    target_document = surviving_mars_csv.parse_file(Path(target_file_path))
    source_file = _source_file(project, target_file_path) or Path(target_file_path)
    source_document = surviving_mars_csv.parse_file(source_file)
    target_values = {
        entry.key: entry.value
        for entry in surviving_mars_csv.entries(target_file_path, "Translation")
    }
    user_values = {
        str(entry.get("key", "")): str(entry.get("translation", ""))
        for entry in entries_list
    }
    translated_values = [
        user_values.get(entry.key, target_values.get(entry.key, entry.value))
        for entry in source_document.entries
    ]
    rewritten = surviving_mars_csv.rewrite_text(
        target_document.source_text,
        translated_values,
        _row_key_map(source_document),
    )
    original_content = target_document.source_text
    _atomic_write(target_file_path, rewritten)
    try:
        language = _target_language(target_file_path, target_language)
        updated_count = service.archive_manager.update_translations(
            project.get("name", ""),
            str(source_file),
            entries_list,
            language,
            project_id=project.get("project_id"),
        )
        if updated_count != len(entries_list):
            raise RuntimeError("Proofreading archive update did not persist every entry.")
    except Exception:
        _atomic_write(target_file_path, original_content)
        raise
    await service.project_manager.update_file_status_with_kanban_sync(
        project.get("project_id", ""),
        file_id,
        "done",
    )
    return {
        "status": "success",
        "document_revision": _revision(target_file_path),
    }
