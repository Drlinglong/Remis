"""Install the reviewed release resources as optional, editable game glossaries."""
import json
import logging
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from scripts.build_glossary_resources import JSON_FILES, PROBABLY_STOLEN_RESOURCE, RESOURCE_PATH, read_resources
from scripts.core.db_models import GlossaryEntry
from scripts.core.glossary_terminology_entry import terminology_entry, terminology_import_fingerprint
from scripts.schemas.glossary_terminology import TerminologyGlossaryImport

logger = logging.getLogger("remis_init")

MARS_SEEDS = dict(zip(JSON_FILES, ("glossary:surviving_mars:zh-CN", "glossary:surviving_mars:zh-TW")))
STOLEN_SEED = "glossary:probably_stolen"
SEED_KEYS = (*MARS_SEEDS.values(), STOLEN_SEED)


def _insert_glossary(conn, game_id, name, description, version, sources, metadata):
    return conn.execute("""
        INSERT INTO glossaries (game_id, name, description, version, is_main, sources, raw_metadata)
        VALUES (?, ?, ?, ?, 0, ?, ?)
    """, (game_id, name, description, version, json.dumps(sources), json.dumps(metadata))).lastrowid


def _insert_entries(conn, entries):
    conn.executemany("""
        INSERT INTO entries (entry_id, glossary_id, translations, abbreviations, variants, raw_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ((row.entry_id, row.glossary_id, json.dumps(row.translations), json.dumps(row.abbreviations),
           json.dumps(row.variants), json.dumps(row.raw_metadata)) for row in entries))


def _already_imported(conn, game_id, metadata_field, expected):
    return conn.execute("""
        SELECT 1 FROM glossaries
        WHERE game_id = ? AND CASE WHEN json_valid(raw_metadata)
            THEN json_extract(raw_metadata, ?) END = ?
        LIMIT 1
    """, (game_id, metadata_field, expected)).fetchone() is not None


def _load_mars(conn, root, missing):
    manifest, contents = read_resources(root)
    sources = json.loads(contents["SOURCES.json"].decode("utf-8"))["sources"]
    for filename in missing:
        payload = TerminologyGlossaryImport.model_validate(json.loads(contents[filename].decode("utf-8"))["import_payload"])
        if _already_imported(conn, payload.game_id, "$.terminology_import_key", payload.import_key):
            continue
        metadata = {
            "kind": "standard", "bundled_resource": MARS_SEEDS[filename],
            "terminology_locale": payload.locale, "terminology_scope_id": payload.scope_id,
            "terminology_import_key": payload.import_key,
            "terminology_import_fingerprint": terminology_import_fingerprint(payload),
            "source_details": sources,
        }
        glossary_id = _insert_glossary(
            conn, payload.game_id, payload.name, payload.description, manifest["resource_version"],
            [source["role"] for source in sources], metadata,
        )
        _insert_entries(conn, (terminology_entry(glossary_id, payload.locale, term) for term in payload.terms))


def _stolen_entry(glossary_id, entry):
    metadata = {**entry["metadata"], "source_lang": "en", "source_text": entry["translations"]["en"],
                "review_state": "candidate"}
    if entry["metadata"].get("review_note"):
        metadata["remarks"] = entry["metadata"]["review_note"]
    return GlossaryEntry(
        entry_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:{glossary_id}:{entry['id']}")),
        glossary_id=glossary_id, translations=entry["translations"], variants=entry["variants"],
        abbreviations=entry["abbreviations"], raw_metadata=metadata,
    )


def _load_probably_stolen(conn, root):
    document = json.loads((root / PROBABLY_STOLEN_RESOURCE).read_text(encoding="utf-8"))
    metadata, entries = document["metadata"], document["entries"]
    if metadata["game_id"] != "probably_stolen" or not entries:
        raise ValueError("Invalid Probably Stolen glossary resource")
    original_name, version = metadata["name"], metadata["version"]
    imported = conn.execute("""
        SELECT 1 FROM glossaries WHERE game_id = 'probably_stolen' AND version = ?
        AND CASE WHEN json_valid(raw_metadata) THEN json_extract(raw_metadata, '$.name') END = ?
        LIMIT 1
    """, (version, original_name)).fetchone()
    if imported:
        return
    glossary_id = _insert_glossary(
        conn, "probably_stolen", "深空当铺 / Probably Stolen - multilingual terminology",
        "Selected names and game terms from official localization, provided as reference candidates.",
        version, metadata["sources"],
        {**metadata, "kind": "standard", "bundled_resource": STOLEN_SEED,
         "default_distribution_status": "bundled_optional"},
    )
    _insert_entries(conn, (_stolen_entry(glossary_id, row) for row in entries))


def install_bundled_glossaries(db_path, resource_dir):
    """Import once per database, keeping existing imports, edits and bindings."""
    root = Path(resource_dir)
    if not (root / RESOURCE_PATH.parent).is_dir():
        return
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        applied = {row[0] for row in conn.execute(
            "SELECT seed_key FROM bundled_seed_state WHERE status = 'applied'"
        )}
        missing = [key for key in SEED_KEYS if key not in applied]
        if not missing:
            return
        mars_missing = [name for name, key in MARS_SEEDS.items() if key in missing]
        if mars_missing:
            _load_mars(conn, root, mars_missing)
        if STOLEN_SEED in missing:
            _load_probably_stolen(conn, root)
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany("""
            INSERT INTO bundled_seed_state (seed_key, seed_version, applied_at)
            VALUES (?, 1, ?)
        """, ((key, now) for key in missing))
    logger.info("[SEED] Installed %s bundled glossary resources.", len(missing))


def try_install_bundled_glossaries(db_path, resource_dir):
    """Leave startup running after a failed transaction so the next start can retry."""
    try:
        install_bundled_glossaries(db_path, resource_dir)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        logger.exception("[SEED] Failed to install bundled glossaries")
