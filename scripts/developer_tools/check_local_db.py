
import sqlite3
import os

# Explicitly check the project root data folder, NOT AppData
db_path = os.path.join(os.getcwd(), "data", "projects.sqlite")

print(f"Checking DB at: {db_path}")

if not os.path.exists(db_path):
    print("DB file not found!")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, name, source_path FROM projects")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} projects:")
    for row in rows:
        print(f"ID: {row[0]} | Name: {row[1]} | Path: {row[2]}")
    conn.close()
