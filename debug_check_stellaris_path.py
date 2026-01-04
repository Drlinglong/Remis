
import sqlite3
import os
from scripts.app_settings import REMIS_DB_PATH

PROJECT_ID = '6049331a-433d-4d09-9205-165c3aad6010'

def check_stellaris_path():
    print(f"Checking database at: {REMIS_DB_PATH}")
    conn = sqlite3.connect(REMIS_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT target_path FROM projects WHERE project_id = ?", (PROJECT_ID,))
    result = cursor.fetchone()
    
    if result:
        print(f"Current Stellaris Target Path: {result[0]}")
    else:
        print("Project not found!")
        
    conn.close()

if __name__ == "__main__":
    check_stellaris_path()
