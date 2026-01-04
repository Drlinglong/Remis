# scripts/utils/migrate_to_sqlite.py
import sqlite3
import os
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define project root and database path relative to the script location
# The script is in scripts/utils/, so we need to go up two levels
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'database.sqlite')
GLOSSARY_DIR = os.path.join(PROJECT_ROOT, 'data', 'glossary')

def create_database_schema(cursor: sqlite3.Cursor):
    """Creates the database schema (tables and indexes)."""
    logging.info("Creating database schema...")

    # Drop existing tables to ensure a fresh start
    cursor.execute("DROP TABLE IF EXISTS entries")
    cursor.execute("DROP TABLE IF EXISTS glossaries")

    # Create glossaries table
    cursor.execute("""
    CREATE TABLE glossaries (
        glossary_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        version TEXT,
        is_main INTEGER NOT NULL DEFAULT 0,
        sources TEXT,
        raw_metadata TEXT
    )
    """)

    # Create entries table
    cursor.execute("""
    CREATE TABLE entries (
        entry_id TEXT PRIMARY KEY,
        glossary_id INTEGER,
        translations TEXT NOT NULL,
        abbreviations TEXT,
        variants TEXT,
        raw_metadata TEXT,
        FOREIGN KEY (glossary_id) REFERENCES glossaries (glossary_id)
    )
    """)

    # Create index
    cursor.execute("CREATE INDEX idx_entry_lookup ON entries (glossary_id, entry_id)")

    logging.info("Database schema and index created successfully.")

def migrate_json_to_sqlite():
    """Scans the glossary directory and migrates all JSON data to the SQLite database."""
    if os.path.exists(DB_PATH):
        logging.info(f"Database file found at {DB_PATH}. It will be overwritten.")
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    create_database_schema(cursor)

    logging.info(f"Scanning for game glossaries in: {GLOSSARY_DIR}")

    game_ids = [d for d in os.listdir(GLOSSARY_DIR) if os.path.isdir(os.path.join(GLOSSARY_DIR, d))]

    total_glossaries = 0
    total_entries = 0

    for game_id in game_ids:
        game_dir = os.path.join(GLOSSARY_DIR, game_id)
        logging.info(f"Processing game: {game_id}")

        for filename in os.listdir(game_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(game_dir, filename)

                try:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                except Exception as e:
                    logging.error(f"Failed to read or parse {file_path}: {e}")
                    continue

                metadata = data.get('metadata', {})
                entries = data.get('entries', [])

                if not entries:
                    logging.warning(f"No entries found in {file_path}. Skipping.")
                    continue

                # Insert into glossaries table
                is_main = 1 if filename == 'glossary.json' else 0

                # Determine glossary name
                glossary_name = metadata.get('name')
                if not glossary_name:
                    if is_main:
                        glossary_name = f"{game_id.capitalize()} Main Glossary"
                    else:
                        glossary_name = filename.replace('.json', '')

                cursor.execute("""
                INSERT INTO glossaries (game_id, name, description, version, is_main, sources, raw_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id,
                    glossary_name,
                    metadata.get('description'),
                    metadata.get('version'),
                    is_main,
                    json.dumps(metadata.get('sources', [])),
                    json.dumps(metadata)
                ))

                glossary_id = cursor.lastrowid
                total_glossaries += 1

                # Insert into entries table
                entries_to_insert = []
                for entry in entries:
                    entry_id = entry.get('id')
                    if not entry_id:
                        logging.warning(f"Skipping entry with no ID in {file_path}: {entry}")
                        continue

                    entries_to_insert.append((
                        entry_id,
                        glossary_id,
                        json.dumps(entry.get('translations', {})),
                        json.dumps(entry.get('abbreviations', {})),
                        json.dumps(entry.get('variants', {})),
                        json.dumps(entry.get('metadata', {}))
                    ))

                cursor.executemany("""
                INSERT OR REPLACE INTO entries (entry_id, glossary_id, translations, abbreviations, variants, raw_metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """, entries_to_insert)

                logging.info(f"Migrated {len(entries_to_insert)} entries from {filename} for game {game_id}.")
                total_entries += len(entries_to_insert)

    conn.commit()
    conn.close()

    logging.info(f"--- Migration Complete ---")
    logging.info(f"Total glossaries migrated: {total_glossaries}")
    logging.info(f"Total entries migrated: {total_entries}")
    logging.info(f"Database saved to: {DB_PATH}")

if __name__ == '__main__':
    migrate_json_to_sqlite()
