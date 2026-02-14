import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scripts import app_settings

def probe():
    db_path = app_settings.REMIS_DB_PATH
    print(f"Probing database at: {db_path}")
    
    if not os.path.exists(db_path):
        print("Database file does not exist!")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Projects
        cursor.execute("SELECT count(*) FROM projects")
        print(f"Total Projects: {cursor.fetchone()[0]}")

        # 1b. Project Files
        cursor.execute("SELECT count(*) FROM project_files")
        print(f"Total Project Files: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT project_id, name, game_id FROM projects LIMIT 5")
        print("Sample Projects:")
        for row in cursor.fetchall():
            print(f"  - {row}")
            
        # 2. Project History
        cursor.execute("SELECT count(*) FROM project_history")
        print(f"Total History Entries: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT history_id, project_id, action_type, timestamp FROM project_history LIMIT 5")
        print("Sample History:")
        for row in cursor.fetchall():
            print(f"  - {row}")
            
        # 3. Glossary
        cursor.execute("SELECT count(*) FROM glossaries")
        print(f"Total Glossaries: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT glossary_id, name, game_id FROM glossaries LIMIT 5")
        print("Sample Glossaries:")
        for row in cursor.fetchall():
            print(f"  - {row}")

        # 4. Check for orphaned history
        cursor.execute("SELECT count(*) FROM project_history WHERE project_id NOT IN (SELECT project_id FROM projects)")
        print(f"History entries with missing projects: {cursor.fetchone()[0]}")

        # 5. Check game distribution
        cursor.execute("SELECT game_id, count(*) FROM projects GROUP BY game_id")
        print("Project Game Distribution (Raw):")
        dist = cursor.fetchall()
        for row in dist:
            print(f"  - {row}")

        # 6. Check Project IDs
        cursor.execute("SELECT project_id, name FROM projects")
        print("Project IDs in DB:")
        p_ids = set()
        for row in cursor.fetchall():
            print(f"  - {row}")
            p_ids.add(row[0])

        # 7. Check History Project IDs
        cursor.execute("SELECT DISTINCT project_id FROM project_history")
        print("Distinct Project IDs in History:")
        for row in cursor.fetchall():
            h_pid = row[0]
            exists = "EXISTS" if h_pid in p_ids else "MISSING"
            print(f"  - {h_pid} ({exists})")

        conn.close()
    except Exception as e:
        print(f"Error probing database: {e}")

if __name__ == "__main__":
    probe()
