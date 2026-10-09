"""Archive bridge with full source identity and compare-and-set translation writes."""
import hashlib

from .batch_repository import BatchConflict


def source_files(snapshot):
    return [{"filename": file["relative_path"], "file_path": file["relative_path"],
             "texts_to_translate": [entry["source"] for entry in file["entries"]],
             "key_map": [{"key_part": entry["key"]} for entry in file["entries"]]} for file in snapshot["files"]]


def source_digest(snapshot):
    digest = hashlib.sha256()
    for file in sorted(snapshot["files"], key=lambda item: item["relative_path"]):
        for entry in file["entries"]:
            digest.update(entry["source"].encode("utf-8"))
    return digest.hexdigest()


def verify_version(manager, version_id, snapshot):
    rows = manager.connection.execute("SELECT source_entry_id,file_path,entry_key,source_text FROM source_entries WHERE version_id=?", (version_id,)).fetchall()
    actual = {(row["file_path"], row["entry_key"], row["source_text"]): row["source_entry_id"] for row in rows}
    expected = {(manager._normalize_archive_file_path(file["relative_path"]), entry["key"], entry["source"])
                for file in snapshot["files"] for entry in file["entries"]}
    if set(actual) != expected or len(rows) != len(expected):
        raise BatchConflict("archive_source_identity_conflict", "Archive source paths, keys or text differ from the frozen source snapshot.")
    return actual


def find_version(manager, snapshot):
    if not manager.connection:
        raise BatchConflict("archive_unavailable", "The translation archive is unavailable.")
    mod_id = manager.get_mod_id_by_remote_id(snapshot["project_id"])
    if mod_id is None:
        return None
    row = manager.connection.execute("SELECT version_id FROM source_versions WHERE mod_id=? AND snapshot_hash=?", (mod_id, source_digest(snapshot))).fetchone()
    if row:
        verify_version(manager, row["version_id"], snapshot)
        return row["version_id"]
    return None


def before_values(manager, snapshot, selected, locale):
    version = find_version(manager, snapshot)
    identities = verify_version(manager, version, snapshot) if version else {}
    values = {}
    for file in snapshot["files"]:
        if file["file_id"] not in selected:
            continue
        for entry in file["entries"]:
            identity = (manager._normalize_archive_file_path(file["relative_path"]), entry["key"], entry["source"])
            row = manager.connection.execute("SELECT translated_text FROM translated_entries WHERE source_entry_id=? AND language_code=?", (identities.get(identity, -1), locale)).fetchone()
            values[entry["id"]] = row["translated_text"] if row else None
    return values


def ensure_source_version(manager, snapshot):
    mod_id = manager.resolve_mod_entry(snapshot["project_name"], snapshot["project_id"])
    version = manager.create_source_version(mod_id, source_files(snapshot)) if mod_id else None
    if not version:
        raise BatchConflict("archive_source_write_failed", "The source archive could not be persisted.")
    verify_version(manager, version, snapshot)
    return version


def apply_archive(manager, snapshot, journal, translations):
    version = journal["archive_version_id"]
    identities = verify_version(manager, version, snapshot)
    connection = manager.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        upserts = []
        for file in snapshot["files"]:
            if file["file_id"] not in journal["file_ids"]:
                continue
            for entry in file["entries"]:
                identity = (manager._normalize_archive_file_path(file["relative_path"]), entry["key"], entry["source"])
                source_id = identities[identity]
                row = connection.execute("SELECT translated_text FROM translated_entries WHERE source_entry_id=? AND language_code=?", (source_id, journal["target_locale"])).fetchone()
                current = row["translated_text"] if row else None
                after = translations[entry["id"]]
                if current not in (journal["archive_before"][entry["id"]], after):
                    raise BatchConflict("archive_revision_conflict", "An archived translation changed while apply waited.")
                upserts.append((source_id, journal["target_locale"], after))
        connection.executemany("INSERT INTO translated_entries(source_entry_id,language_code,translated_text) VALUES(?,?,?) ON CONFLICT(source_entry_id,language_code) DO UPDATE SET translated_text=excluded.translated_text,last_translated_at=CURRENT_TIMESTAMP", upserts)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return len(upserts)
