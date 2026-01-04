import sys
import os
import logging

# Setup Path
sys.path.insert(0, os.getcwd())

from scripts.core.archive_manager import archive_manager

def debug_stellaris():
    mod_name = "Project Remis - Demo Mod - Stellaris"
    filename = "remis_demo_events_l_english.yml"
    # full path isn't strictly needed if get_entries only uses basename, but let's provide a dummy one
    dummy_path = f"J:/ignored/{filename}"
    
    print(f"Checking entries for Mod: {mod_name}, File: {filename}")
    
    entries = archive_manager.get_entries(mod_name, dummy_path, "zh-CN")
    print(f"Found {len(entries)} entries.")
    
    if entries:
        print("Sample Entry:", entries[0])
    else:
        # Dig deeper: Check DB directly
        print("No entries found via Manager. Checking DB tables...")
        conn = archive_manager.connection
        cursor = conn.cursor()
        
        cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name,))
        mod_row = cursor.fetchone()
        if not mod_row:
            print("Mod ID not found!")
            return
        mod_id = mod_row['mod_id']
        print(f"Mod ID: {mod_id}")
        
        cursor.execute("SELECT version_id, created_at FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC", (mod_id,))
        versions = cursor.fetchall()
        print(f"Found {len(versions)} versions.")
        for v in versions:
            print(f" - Version {v['version_id']} ({v['created_at']})")
            
            # Check file_path in source_entries
            cursor.execute("SELECT DISTINCT file_path FROM source_entries WHERE version_id = ?", (v['version_id'],))
            files = cursor.fetchall()
            print(f"   Files in version: {[f['file_path'] for f in files]}")

if __name__ == "__main__":
    debug_stellaris()
