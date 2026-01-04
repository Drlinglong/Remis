
import sqlite3
import os
import uuid
import datetime
import sys

# Ensure we can find app_settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from scripts import app_settings

EU5_PROJECT_ID = "DEMO-EU5-PROJECT-ID-001" # Fixed ID for stability
EU5_NAME = "Test Project Remis EU5"
EU5_GAME_ID = "eu5"
EU5_SOURCE_PATH = os.path.join(app_settings.PROJECT_ROOT, "source_mod", "Test_Project_Remis_EU5").replace("\\", "/")
EU5_LANG = "en"

def seed_eu5():
    db_path = app_settings.REMIS_DB_PATH
    print(f"Seeding to: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (EU5_PROJECT_ID,))
    if cursor.fetchone():
        print("EU5 Demo already exists. Updating path just in case.")
        cursor.execute("UPDATE projects SET source_path = ?, status='active' WHERE project_id = ?", (EU5_SOURCE_PATH, EU5_PROJECT_ID))
    else:
        print("Inserting EU5 Demo...")
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO projects (project_id, name, game_id, source_path, source_language, status, created_at, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (EU5_PROJECT_ID, EU5_NAME, EU5_GAME_ID, EU5_SOURCE_PATH, EU5_LANG, 'active', now, now))
        
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    seed_eu5()
