import os
import sys
import sqlite3
import logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.app_settings import PROJECTS_DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_CLEANER")

def wipe_db():
    print(f"Target DB: {PROJECTS_DB_PATH}")
    
    if not os.path.exists(PROJECTS_DB_PATH):
        print("Database not found. Nothing to clean.")
        return

    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check counts before
        cursor.execute("SELECT COUNT(*) FROM projects")
        p_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM project_files")
        f_count = cursor.fetchone()[0]
        
        print(f"Found {p_count} projects and {f_count} files.")
        
        # Delete
        print("Deleting all project files...")
        cursor.execute("DELETE FROM project_files")
        
        print("Deleting all projects...")
        cursor.execute("DELETE FROM projects")
        
        # Optional: Clear activity log if desired, but user focused on "projects".
        # Let's keep activity log for history unless implicitly requested. 
        # "删除所有的旧项目" usually implies just the project data.
        
        conn.commit()
        
        # Vacuum to reclaim space
        cursor.execute("VACUUM")
        
        print("Database wiped successfully.")
        
    except Exception as e:
        print(f"Error executing wipe: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    wipe_db()
