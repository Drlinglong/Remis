
import sqlite3
import os
from scripts.app_settings import REMIS_DB_PATH

PROJECT_ID = '6049331a-433d-4d09-9205-165c3aad6010' # Stellaris

def check_project_files():
    print(f"Checking Project Files DB at: {REMIS_DB_PATH}")
    conn = sqlite3.connect(REMIS_DB_PATH)
    cursor = conn.cursor()
    
    print(f"Files for Project {PROJECT_ID}:")
    cursor.execute("SELECT file_path, file_type FROM project_files WHERE project_id = ?", (PROJECT_ID,))
    files = cursor.fetchall()
    for f in files:
        print(f"  [{f[1]}] {os.path.basename(f[0])}  ({f[0]})")
            
    conn.close()

if __name__ == "__main__":
    check_project_files()
