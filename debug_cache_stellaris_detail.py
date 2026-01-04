
import sqlite3
import os
from scripts.app_settings import MODS_CACHE_DB_PATH

def check_stellaris_translations_detail():
    print(f"Checking Translations Detail for Stellaris at: {MODS_CACHE_DB_PATH}")
    conn = sqlite3.connect(MODS_CACHE_DB_PATH)
    cursor = conn.cursor()
    
    MOD_ID = 3
    
    # Get version
    cursor.execute("SELECT version_id FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1", (MOD_ID,))
    vid = cursor.fetchone()[0]
    
    # Check per file
    cursor.execute("SELECT DISTINCT file_path FROM source_entries WHERE version_id = ?", (vid,))
    files = cursor.fetchall()
    
    for row in files:
        fname = row[0]
        # Count source entries
        cursor.execute("SELECT count(*) FROM source_entries WHERE version_id = ? AND file_path = ?", (vid, fname))
        src_count = cursor.fetchone()[0]
        
        # Count translated entries (zh-CN)
        cursor.execute("""
            SELECT count(*) 
            FROM translated_entries t 
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id 
            WHERE s.version_id = ? AND s.file_path = ? AND t.language_code = 'zh-CN'
        """, (vid, fname))
        trans_count = cursor.fetchone()[0]
        
        print(f"File: {fname}")
        print(f"  Source Entries: {src_count}")
        print(f"  zh-CN Translations: {trans_count}")
        
    conn.close()

if __name__ == "__main__":
    check_stellaris_translations_detail()
