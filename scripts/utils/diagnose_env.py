import sys
import os
import sqlite3

# Add project root to path
# We need to add J:\V3_Mod_Localization_Factory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from scripts import app_settings

print(f"python executable: {sys.executable}")
print(f"sys.frozen: {getattr(sys, 'frozen', 'Not Set')}")
print(f"App Data Dir: {app_settings.get_app_data_dir()}")
print(f"Database Path: {app_settings.DATABASE_PATH}")

print("\n--- Projects in DB ---")
try:
    conn = sqlite3.connect(app_settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, name, source_path FROM projects")
    for row in cursor.fetchall():
        print(f"ID: {row[0]} | Name: {row[1]} | Path: {row[2]}")
    conn.close()
except Exception as e:
    print(f"Error querying DB: {e}")
