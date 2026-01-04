
import sqlite3
import os

appdata = os.getenv('APPDATA')
paths = [
    os.path.join(appdata, "RemisModFactoryDev", "remis.sqlite"),
    os.path.join(appdata, "RemisModFactory", "remis.sqlite"),
    os.path.join(os.getcwd(), "data", "projects.sqlite")
]

for p in paths:
    print(f"--- Checking {p} ---")
    if not os.path.exists(p):
        print("Not found.")
        continue
        
    try:
        conn = sqlite3.connect(p)
        cursor = conn.cursor()
        cursor.execute("SELECT project_id, name, source_path FROM projects")
        rows = cursor.fetchall()
        for row in rows:
            print(f"[{row[1]}] ID: {row[0]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
