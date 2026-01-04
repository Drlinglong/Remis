
import sqlite3
import os
from scripts.app_settings import MODS_CACHE_DB_PATH

def check_stellaris_cache_completeness():
    print(f"Checking Cache DB for Stellaris files at: {MODS_CACHE_DB_PATH}")
    conn = sqlite3.connect(MODS_CACHE_DB_PATH)
    cursor = conn.cursor()
    
    # Stellaris Mod ID = 3 (from previous check)
    MOD_ID = 3
    
    # Get latest version
    cursor.execute("SELECT version_id FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1", (MOD_ID,))
    vid = cursor.fetchone()[0]
    
    # List all files for this version
    cursor.execute("SELECT DISTINCT file_path FROM source_entries WHERE version_id = ?", (vid,))
    files = cursor.fetchall()
    print("Files in Cache:")
    for f in files:
        print(f"  - {f[0]}")
        
    conn.close()

if __name__ == "__main__":
    check_stellaris_cache_completeness()
