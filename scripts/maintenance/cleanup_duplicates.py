import sqlite3
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts import app_settings

def cleanup_duplicates(game_id="ck3"):
    db_path = app_settings.DATABASE_PATH
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Get Glossary IDs for the game
        print(f"Finding glossaries for game: {game_id}...")
        cursor.execute("SELECT glossary_id, name FROM glossaries WHERE game_id = ?", (game_id,))
        glossaries = cursor.fetchall()
        
        if not glossaries:
            print(f"No glossaries found for game {game_id}")
            return

        total_deleted = 0

        for glossary in glossaries:
            g_id = glossary['glossary_id']
            g_name = glossary['name']
            print(f"\nProcessing glossary: {g_name} (ID: {g_id})")

            # 2. Get all entries
            cursor.execute("SELECT rowid, entry_id, translations FROM entries WHERE glossary_id = ?", (g_id,))
            entries = cursor.fetchall()

            # 3. Find duplicates
            # Map: source_text -> list of (rowid, entry_id)
            source_map = {}
            
            for entry in entries:
                row_id = entry['rowid']
                entry_id = entry['entry_id']
                translations_json = entry['translations']
                
                try:
                    translations = json.loads(translations_json)
                    source_text = translations.get('en', '').strip()
                except:
                    # If JSON fails or empty, skip or handle?
                    # If source is empty, we might not want to dedupe aggressively, skipping.
                    continue
                
                if not source_text:
                    continue

                if source_text not in source_map:
                    source_map[source_text] = []
                source_map[source_text].append((row_id, entry_id))

            # 4. Identify entries to delete
            entries_to_delete = []
            
            for source, occurrences in source_map.items():
                if len(occurrences) > 1:
                    # Sort by rowid ascending
                    occurrences.sort(key=lambda x: x[0])
                    
                    # Keep the LAST one (highest rowid/latest insertion)
                    # The bug was "edit -> save -> new entry". 
                    # The NEW entry (with edits) intersects last.
                    to_keep = occurrences[-1]
                    to_remove = occurrences[:-1]
                    
                    print(f"  Found duplicate '{source}': Keeping {to_keep[1]} (rowid {to_keep[0]}), Deleting {len(to_remove)} others.")
                    
                    for item in to_remove:
                        entries_to_delete.append(item[1]) # store entry_id

            # 5. Execute Deletion
            if entries_to_delete:
                # Chunk deletions to be safe with SQLite limits
                chunk_size = 900
                for i in range(0, len(entries_to_delete), chunk_size):
                    chunk = entries_to_delete[i:i + chunk_size]
                    placeholders = ','.join(['?'] * len(chunk))
                    cursor.execute(f"DELETE FROM entries WHERE entry_id IN ({placeholders})", chunk)
                    total_deleted += cursor.rowcount
                    print(f"  Deleted {cursor.rowcount} duplicate entries.")
            else:
                print("  No duplicates found.")

        conn.commit()
        print(f"\nCleanup complete. Total entries deleted: {total_deleted}")

    except Exception as e:
        print(f"Error during cleanup: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    game_arg = sys.argv[1] if len(sys.argv) > 1 else "ck3"
    cleanup_duplicates(game_arg)
