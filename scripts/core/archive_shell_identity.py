"""Provenance for explicitly configured shell-language archive snapshots."""

import hashlib
import json

from scripts.core.archive_operation import archive_operation


def create_shell_identity_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS archive_shell_identities (
            version_id INTEGER PRIMARY KEY REFERENCES source_versions(version_id) ON DELETE CASCADE,
            language_name TEXT NOT NULL,
            shell_key TEXT NOT NULL
        )
    """)


def _identity(shell_config):
    if not shell_config:
        raise ValueError("Explicit shell-language configuration is required")
    return shell_config["name"].strip().casefold(), shell_config["key"]


def shell_snapshot_hash(source_hash, shell_config):
    payload = json.dumps([source_hash, *_identity(shell_config)], ensure_ascii=False).encode("utf-8")
    return "shell-v1:" + hashlib.sha256(payload).hexdigest()


def _saved_identity(cursor, version_id):
    row = cursor.execute(
        "SELECT language_name, shell_key FROM archive_shell_identities WHERE version_id = ?", (version_id,),
    ).fetchone()
    return tuple(row) if row else None


def bind_shell_identity(cursor, version_id, shell_config):
    """Bind the identity within the transaction that writes the translations."""
    saved = _saved_identity(cursor, version_id)
    if shell_config is None and saved is None:
        return
    expected = _identity(shell_config)
    if saved == expected:
        return
    if saved is not None:
        raise ValueError("The archive already belongs to a different shell-language configuration")
    if cursor.execute("""
        SELECT 1 FROM source_entries AS source
        JOIN translated_entries AS translation ON translation.source_entry_id = source.source_entry_id
        WHERE source.version_id = ? AND translation.language_code = 'custom' LIMIT 1
    """, (version_id,)).fetchone():
        raise ValueError("Existing custom archive has no verified shell-language identity")
    cursor.execute("INSERT INTO archive_shell_identities VALUES (?, ?, ?)", (version_id, *expected))


@archive_operation
def verified_shell_entries(manager, project_id, shell_config):
    expected = _identity(shell_config)
    baseline = manager.get_latest_version(project_id=project_id, language="custom")
    if not baseline or not baseline["translated_count"]:
        raise ValueError("Shell incremental updates require an existing custom-language baseline")
    saved = _saved_identity(manager.connection.cursor(), baseline["id"])
    if saved is None:
        raise ValueError("Existing custom archive has no verified shell-language identity")
    if saved != expected:
        raise ValueError("The existing archive belongs to a different shell-language configuration")
    return manager.get_entries(project_id=project_id, language="custom")
