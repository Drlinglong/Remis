import logging
from typing import Any, Dict, List


def update_archive_translations(
    archive_manager,
    mod_name: str,
    file_path: str,
    entries: List[Dict[str, Any]],
    language: str,
    project_id: str | None = None,
    allow_missing: bool = False,
) -> int:
    """Atomically update proofreading entries in the active archive baseline."""
    if not entries:
        return 0
    connection = archive_manager.connection
    if not connection:
        raise RuntimeError("Translation archive database is unavailable.")
    cursor = connection.cursor()

    try:
        mod_id = archive_manager.get_mod_id_by_remote_id(project_id) if project_id else None
        if mod_id is None:
            cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name.strip(),))
            mod_row = cursor.fetchone()
            mod_id = mod_row["mod_id"] if mod_row else None
        if mod_id is None:
            raise LookupError(f"Archive project not found: {mod_name}")

        version_row = archive_manager._get_latest_version_row(
            cursor,
            mod_id,
            language=language,
            require_translations=True,
        )
        if not version_row:
            version_row = archive_manager._get_latest_version_row(cursor, mod_id)
        if not version_row:
            raise LookupError(f"Archive baseline not found: {mod_name}")

        path_candidates = archive_manager._build_file_path_candidates(file_path)
        upserts = []
        missing_keys = []
        for entry in entries:
            key = entry["key"].strip()
            row = archive_manager._find_source_entry_id(
                cursor,
                version_row["version_id"],
                key,
                path_candidates,
            )
            if row:
                upserts.append((row["source_entry_id"], language, entry.get("translation", "")))
            else:
                missing_keys.append(key)

        if missing_keys and not allow_missing:
            raise LookupError(
                "Archive entries not found for proofreading keys: "
                + ", ".join(missing_keys[:5])
            )

        if missing_keys:
            logging.warning(
                "Skipping %s proofreading keys missing from the archive baseline: %s",
                len(missing_keys),
                ", ".join(missing_keys[:5]),
            )

        if upserts:
            cursor.executemany(
                """
                INSERT INTO translated_entries (source_entry_id, language_code, translated_text)
                VALUES (?, ?, ?)
                ON CONFLICT(source_entry_id, language_code) DO UPDATE SET
                    translated_text = excluded.translated_text,
                    last_translated_at = CURRENT_TIMESTAMP
                """,
                upserts,
            )
        connection.commit()
        return len(upserts)
    except Exception:
        connection.rollback()
        raise
