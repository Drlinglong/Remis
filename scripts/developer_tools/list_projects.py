
import sqlite3
import os

db_path = os.path.join("data", "projects.sqlite")
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    # Try AppData
    import sys
    sys.path.append(os.getcwd())
    from scripts import app_settings
    db_path = app_settings.REMIS_DB_PATH
    print(f"Trying AppData: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT project_id, name, source_path FROM projects")
for row in cursor.fetchall():
    print(f"ID: {row[0]} | Name: {row[1]} | Path: {row[2]}")
conn.close()
