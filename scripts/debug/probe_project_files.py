
import sys
import os
import sqlite3
import asyncio
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scripts import app_settings
from scripts.core.db_manager import DatabaseConnectionManager
from sqlalchemy import text  # Import text for SQL queries

async def probe_project_files():
    db_path = app_settings.PROJECTS_DB_PATH
    print(f"Checking Projects DB at: {db_path}")
    
    if not os.path.exists(db_path):
        print("DB file not found!")
        return

    # Use the async DB manager logic but synchronously for this quick script if possible? 
    # Or just use sqlite3 directly since it's a file.
    # Let's use sqlite3 for simplicity to avoid async loop issues in a script if unnecessary.
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. List all projects
        print("\n--- Projects ---")
        cursor.execute("SELECT project_id, name, status, notes FROM projects ORDER BY last_modified DESC LIMIT 5")
        projects = cursor.fetchall()
        for p in projects:
            print(f"Project: {p[1]} (ID: {p[0]}) - Status: {p[2]}")
            print(f"  Notes: {p[3]}")
            
            # 2. Check files for this project
            cursor.execute("SELECT COUNT(*) FROM project_files WHERE project_id = ?", (p[0],))
            count = cursor.fetchone()[0]
            print(f"  File Count: {count}")
            
            if count > 0:
                cursor.execute("SELECT file_path, status FROM project_files WHERE project_id = ? LIMIT 3", (p[0],))
                files = cursor.fetchall()
                for f in files:
                    print(f"    - {f[0]} ({f[1]})")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(probe_project_files())
