
import sqlite3
import os
from scripts.app_settings import MODS_CACHE_DB_PATH

def check_cache_db():
    print(f"Checking Cache DB at: {MODS_CACHE_DB_PATH}")
    if not os.path.exists(MODS_CACHE_DB_PATH):
        print("Cache DB not found!")
        return

    conn = sqlite3.connect(MODS_CACHE_DB_PATH)
    cursor = conn.cursor()
    
    # 1. List Mods
    print("\n--- MODS ---")
    cursor.execute("SELECT mod_id, name, last_updated FROM mods")
    mods = cursor.fetchall()
    for m in mods:
        print(f"ID: {m[0]}, Name: '{m[1]}', Updated: {m[2]}")
        
        # 2. Check latest version for this mod
        cursor.execute("SELECT version_id, created_at FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1", (m[0],))
        ver = cursor.fetchone()
        if ver:
            vid = ver[0]
            print(f"  Latest Version: {vid} (Created: {ver[1]})")
            
            # 3. Check source entries sample
            cursor.execute("SELECT count(*) FROM source_entries WHERE version_id = ?", (vid,))
            count = cursor.fetchone()[0]
            print(f"  Source Entries: {count}")
            
            cursor.execute("SELECT file_path FROM source_entries WHERE version_id = ? LIMIT 1", (vid,))
            sample_file = cursor.fetchone()
            if sample_file:
                 print(f"  Sample File Path: {sample_file[0]}")

            # 4. Check translations
            cursor.execute("""
                SELECT t.language_code, count(*) 
                FROM translated_entries t 
                JOIN source_entries s ON t.source_entry_id = s.source_entry_id 
                WHERE s.version_id = ? 
                GROUP BY t.language_code
            """, (vid,))
            trans_stats = cursor.fetchall()
            print("  Translations:")
            for lang, t_count in trans_stats:
                print(f"    {lang}: {t_count} entries")

    conn.close()

if __name__ == "__main__":
    check_cache_db()
