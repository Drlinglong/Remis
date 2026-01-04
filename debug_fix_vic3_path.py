
import sqlite3
import os
from scripts.app_settings import REMIS_DB_PATH

PROJECT_ID = 'a525f596-6c71-43fe-ade2-52c9205a2720'

def check_vic3_path():
    print(f"Checking database at: {REMIS_DB_PATH}")
    conn = sqlite3.connect(REMIS_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT target_path FROM projects WHERE project_id = ?", (PROJECT_ID,))
    result = cursor.fetchone()
    
    if result:
        print(f"Current Vic3 Target Path: {result[0]}")
    else:
        print("Project not found!")
        
    conn.close()

if __name__ == "__main__":
    check_vic3_path()
