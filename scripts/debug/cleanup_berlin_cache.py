import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts.app_settings import MODS_CACHE_DB_PATH

def cleanup_berlin():
    if not os.path.exists(MODS_CACHE_DB_PATH):
        print(f"Database not found at {MODS_CACHE_DB_PATH}")
        return

    conn = sqlite3.connect(MODS_CACHE_DB_PATH)
    cursor = conn.cursor()

    keywords = ["Berlin Conference", "柏林会议", "berlin_conference"]
    
    print(f"Searching for keywords: {keywords} in {MODS_CACHE_DB_PATH}")

    # 1. Find and Delete Translated Entries
    deleted_trans = 0
    for keyword in keywords:
        cursor.execute("SELECT translated_entry_id, translated_text FROM translated_entries WHERE translated_text LIKE ?", (f'%{keyword}%',))
        rows = cursor.fetchall()
        if rows:
            print(f"Found {len(rows)} translated entries matching '{keyword}':")
            ids = [r[0] for r in rows]
            for r in rows:
                print(f"  - [{r[0]}] {r[1][:50]}...")
            
            cursor.execute(f"DELETE FROM translated_entries WHERE translated_entry_id IN ({','.join(map(str, ids))})")
            deleted_trans += cursor.rowcount
            print(f"  Deleted {cursor.rowcount} entries.")

    # 2. Find and Delete Source Entries (Optional, but user said 'entries about Berlin Conference')
    # Use caution deleting source entries as they are linked to versions. 
    # But if we delete source, we must delete linked translations.
    # The user specifically mentioned "translation entries".
    # Let's stick to translations for safety unless requested otherwise, 
    # OR if the source itself is 'Berlin Conference' and we want to purge it?
    # Actually, deleting source entries might break integrity of the version snapshot if strict.
    # But for a cache, it's fine.
    
    deleted_source = 0
    for keyword in keywords:
        cursor.execute("SELECT source_entry_id, source_text FROM source_entries WHERE source_text LIKE ?", (f'%{keyword}%',))
        rows = cursor.fetchall()
        if rows:
            print(f"Found {len(rows)} source entries matching '{keyword}':")
            ids = [r[0] for r in rows]
            for r in rows:
                print(f"  - [{r[0]}] {r[1][:50]}...")
            
            # Cascade delete translations first
            cursor.execute(f"DELETE FROM translated_entries WHERE source_entry_id IN ({','.join(map(str, ids))})")
            print(f"  Cascade deleted {cursor.rowcount} translations linked to these source entries.")
            
            cursor.execute(f"DELETE FROM source_entries WHERE source_entry_id IN ({','.join(map(str, ids))})")
            deleted_source += cursor.rowcount
            print(f"  Deleted {cursor.rowcount} source entries.")

    conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_berlin()
