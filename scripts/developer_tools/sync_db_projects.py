
import sqlite3
import os
import shutil
import sys

# Ensure proper paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from scripts import app_settings

SOURCE_DB = os.path.join(app_settings.APP_DATA_DIR, "remis.sqlite")
TARGET_DB = os.path.join(os.getcwd(), "data", "projects.sqlite")

TARGET_IDS = [
    'a525f596-6c71-43fe-ade2-52c9205a2720',
    '6049331a-433d-4d09-9205-165c3aad6010',
    'ae507ae2-2a08-44e3-9c3d-caa4445911f2'
]

print(f"Syncing from {SOURCE_DB} to {TARGET_DB}")

if not os.path.exists(SOURCE_DB):
    print("Source DB not found!")
    sys.exit(1)

# Connect to both
src_conn = sqlite3.connect(SOURCE_DB)
tgt_conn = sqlite3.connect(TARGET_DB)

# Enable row factory for easy access
src_conn.row_factory = sqlite3.Row

# 1. Clear Target Tables
print("Clearing target tables...")
tgt_conn.execute("DELETE FROM projects")
tgt_conn.execute("DELETE FROM project_files")
tgt_conn.execute("DELETE FROM activity_log")

# 2. Copy Projects
print("Copying projects...")
projects = src_conn.execute(f"SELECT * FROM projects WHERE project_id IN ({','.join(['?']*len(TARGET_IDS))})", TARGET_IDS).fetchall()

for p in projects:
    cols = p.keys()
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO projects ({','.join(cols)}) VALUES ({placeholders})"
    tgt_conn.execute(sql, tuple(p))
    print(f"Copied Project: {p['name']}")

# 3. Copy Files
print("Copying files...")
files = src_conn.execute(f"SELECT * FROM project_files WHERE project_id IN ({','.join(['?']*len(TARGET_IDS))})", TARGET_IDS).fetchall()
for f in files:
    cols = f.keys()
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO project_files ({','.join(cols)}) VALUES ({placeholders})"
    tgt_conn.execute(sql, tuple(f))
print(f"Copied {len(files)} files.")

# 4. Copy Logs
print("Copying logs...")
logs = src_conn.execute(f"SELECT * FROM activity_log WHERE project_id IN ({','.join(['?']*len(TARGET_IDS))})", TARGET_IDS).fetchall()
tgt_conn.execute("CREATE TABLE IF NOT EXISTS activity_log (log_id TEXT PRIMARY KEY, project_id TEXT, type TEXT, description TEXT, timestamp TEXT)") # Ensure table exists

for l in logs:
    cols = l.keys()
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO activity_log ({','.join(cols)}) VALUES ({placeholders})"
    tgt_conn.execute(sql, tuple(l))
print(f"Copied {len(logs)} logs.")

tgt_conn.commit()
src_conn.close()
tgt_conn.close()
print("Sync Complete.")
