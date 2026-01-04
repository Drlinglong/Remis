
import sqlite3
import os
from scripts.app_settings import REMIS_DB_PATH

PROJECT_IDS = [
    '6049331a-433d-4d09-9205-165c3aad6010', # Stellaris
    'ae507ae2-2a08-44e3-9c3d-caa4445911f2'  # EU5
]

def check_project_names():
    print(f"Checking Projects DB at: {REMIS_DB_PATH}")
    conn = sqlite3.connect(REMIS_DB_PATH)
    cursor = conn.cursor()
    
    for pid in PROJECT_IDS:
        cursor.execute("SELECT name FROM projects WHERE project_id = ?", (pid,))
        res = cursor.fetchone()
        if res:
            print(f"Project {pid}: Name = '{res[0]}'")
        else:
            print(f"Project {pid}: Not Found")
            
    conn.close()

if __name__ == "__main__":
    check_project_names()
