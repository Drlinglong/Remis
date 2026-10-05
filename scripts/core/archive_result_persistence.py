"""Persist matched translations atomically and surface archive failures."""
import logging
from typing import Any, Dict, List
from scripts.utils import i18n


class ArchivePersistenceError(RuntimeError):
    """Raised when translation results cannot be committed to the archive."""


def persist_archive_results(manager, version_id: int, file_results: Dict[str, Any], all_files_data: List[Dict], target_lang_code: str):
    """阶段三: 将指定语言的翻译结果存入或更新到数据库"""
    if not manager.connection or not version_id:
        raise ArchivePersistenceError("Translation archive database or source version is unavailable")

    cursor = manager.connection.cursor()
    try:
        upsert_data = []

        for filename, translated_texts in file_results.items():
            normalized_filename = manager._normalize_archive_file_path(filename)
            file_data = next(
                (
                    fd for fd in all_files_data
                    if manager._normalize_archive_file_path(fd.get('file_path') or fd.get('filename')) == normalized_filename
                    or manager._normalize_archive_file_path(fd.get('filename')) == normalized_filename
                ),
                None
            )
            if not translated_texts:
                continue
            if not file_data:
                raise LookupError(f"Archive source file not found: {filename}")

            km = file_data.get('archive_key_map', file_data.get('key_map', {}))
            archive_file_path = manager._normalize_archive_file_path(
                file_data.get('file_path') or file_data.get('filename', '')
            )
            for idx, translated_text in enumerate(translated_texts):
                if isinstance(km, dict):
                    key_info = km.get(idx)
                elif isinstance(km, list) and idx < len(km):
                    key_info = km[idx]
                else:
                    key_info = None

                # Extract the actual key string
                entry_key = key_info.get('key_part', '').strip() if isinstance(key_info, dict) else str(key_info if key_info is not None else idx)

                # Normalize: ensure no trailing colon (consistency)
                if entry_key.endswith(":"):
                    entry_key = entry_key[:-1].strip()

                # Find source entry
                file_path_candidates = manager._build_file_path_candidates(archive_file_path)
                row = manager._find_source_entry_id(cursor, version_id, entry_key, file_path_candidates)

                # [FALLBACK] If not found and key has :version, try without version (for legacy compatibility)
                if not row and ":" in entry_key:
                    pure_key = entry_key.split(':')[0]
                    row = manager._find_source_entry_id(cursor, version_id, pure_key, file_path_candidates)

                if not row:
                    raise LookupError(f'Archive source entry not found: {entry_key}')
                upsert_data.append((row['source_entry_id'], target_lang_code, translated_text))

        if not upsert_data:
            return 0

        cursor.executemany("""
            INSERT INTO translated_entries (source_entry_id, language_code, translated_text)
            VALUES (?, ?, ?)
            ON CONFLICT(source_entry_id, language_code) DO UPDATE SET
            translated_text = excluded.translated_text,
            last_translated_at = CURRENT_TIMESTAMP
        """, upsert_data)

        manager.connection.commit()
        logging.info(i18n.t("log_info_archived_updated_translations", count=len(upsert_data), lang_code=target_lang_code))
        return len(upsert_data)

    except Exception as e:
        logging.error(i18n.t("log_error_db_archive_results", lang_code=target_lang_code, error=e))
        manager.connection.rollback()
        raise ArchivePersistenceError("Translation archive write failed") from e
