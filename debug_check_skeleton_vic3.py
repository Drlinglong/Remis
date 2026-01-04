
import sqlite3
import os

SKELETON_DB = "assets/skeleton.sqlite"
PROJECT_ID = 'a525f596-6c71-43fe-ade2-52c9205a2720'

def check_skeleton_path():
    print(f"Checking skeleton at: {SKELETON_DB}")
    if not os.path.exists(SKELETON_DB):
         print("Skeleton not found")
         return
         
    conn = sqlite3.connect(SKELETON_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT target_path FROM projects WHERE project_id = ?", (PROJECT_ID,))
    result = cursor.fetchone()
    
    if result:
        print(f"Skeleton Vic3 Target Path: {result[0]}")
    else:
        print("Project not found in skeleton!")
        
    conn.close()

if __name__ == "__main__":
    check_skeleton_path()
