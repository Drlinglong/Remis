
import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scripts import app_settings

def probe_db():
    db_path = app_settings.MODS_CACHE_DB_PATH
    print(f"Checking DB at: {db_path}")
    
    if not os.path.exists(db_path):
        print("DB file not found!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    key_pattern = '%berlin_conference_0_states%'
    print(f"\n--- Checking Source Entries for LIKE '{key_pattern}' ---")
    cursor.execute("SELECT source_entry_id, entry_key, source_text FROM source_entries WHERE entry_key LIKE ?", (key_pattern,))
    rows = cursor.fetchall()
    
    if not rows:
        print("[MISSING] No source entry found for this key pattern.")
    else:
        for row in rows:
            print(f"[FOUND SOURCE] ID: {row[0]}, Key: {row[1]}")
            # Check translation
            cursor.execute("SELECT * FROM translated_entries WHERE source_entry_id = ?", (row[0],))
            t_rows = cursor.fetchall()
            if not t_rows:
                print("    -> [NO TRANSLATIONS]")
            else:
                for t in t_rows:
                    print(f"    -> [TRANSLATED] {t['language_code']}: {t['translated_text'][:20]}...")

    conn.close()

if __name__ == "__main__":
    probe_db()
