import os
import sqlite3
import shutil
import sys

# Define Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
from scripts import app_settings

DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
ASSETS_DIR = os.path.join(PROJECT_ROOT, 'assets')
GLOSSARY_DB = app_settings.DATABASE_PATH
PROJECTS_DB = app_settings.PROJECTS_DB_PATH
MODS_CACHE_DB = app_settings.MODS_CACHE_DB_PATH  # DEV mods_cache.sqlite
OUTPUT_DB = os.path.join(ASSETS_DIR, 'skeleton.sqlite')
OUTPUT_CACHE_DB = os.path.join(ASSETS_DIR, 'mods_cache_skeleton.sqlite')  # NEW

# Demo Projects to Keep
# 1. Project Remis Stellaris Demo Mod
# 2. 蕾姆丝计划演示mod：最后的罗马人 (Vic3)
KEEP_PROJECT_IDS = [
    '6049331a-433d-4d09-9205-165c3aad6010', 
    'a525f596-6c71-43fe-ade2-52c9205a2720',
    'ae507ae2-2a08-44e3-9c3d-caa4445911f2'
]

DEMO_ROOT_PLACEHOLDER = "{{BUNDLED_DEMO_ROOT}}"
TRANS_ROOT_PLACEHOLDER = "{{BUNDLED_TRANSLATION_ROOT}}"

# Hardcoded replacement logic:
# Map the DEV path to the PLACEHOLDER path relative structure.
# Dev Path 1: J:\V3_Mod_Localization_Factory\source_mod\Test_Project_Remis_stellaris
# Dev Path 2: J:\V3_Mod_Localization_Factory\source_mod\Test_Project_Remis_Vic3
# Dev Path 3: J:\V3_Mod_Localization_Factory\source_mod\Test_Project_Remis_EU5
#
# Target Structure in EXE:
# resources/demo_mod/
#   |-- Test_Project_Remis_stellaris
#   |-- Test_Project_Remis_Vic3
#   |-- Test_Project_Remis_EU5
#
# So we want:
# {{BUNDLED_DEMO_ROOT}}/Test_Project_Remis_stellaris
# {{BUNDLED_DEMO_ROOT}}/Test_Project_Remis_Vic3
# {{BUNDLED_DEMO_ROOT}}/Test_Project_Remis_EU5

def ensure_assets_dir():
    if not os.path.exists(ASSETS_DIR):
        print(f"[INFO] Creating assets directory: {ASSETS_DIR}")
        os.makedirs(ASSETS_DIR)

def create_skeleton():
    print(f"[INFO] Starting Skeleton Database Generation...")
    ensure_assets_dir()
    
    # 1. Start with Glossary DB (it's the biggest)
    if not os.path.exists(GLOSSARY_DB):
        print(f"[ERROR] Glossary DB not found at {GLOSSARY_DB}")
        sys.exit(1)
        
    print(f"[COPY] Copying {GLOSSARY_DB} -> {OUTPUT_DB}")
    shutil.copy2(GLOSSARY_DB, OUTPUT_DB)
    
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()
    
    # 2. Attach Projects DB
    if not os.path.exists(PROJECTS_DB):
        print(f"[ERROR] Projects DB not found at {PROJECTS_DB}")
        sys.exit(1)
        
    print(f"[ATTACH] Attaching {PROJECTS_DB}")
    cursor.execute("ATTACH DATABASE ? AS src", (PROJECTS_DB,))
    
    # 3. Create Tables (if not exist in Glossary DB, which they shouldn't)
    # Copied schema from db_initializer.py
    print("[SCHEMA] Creating Projects Schema...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            game_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            target_path TEXT,
            source_language TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            last_modified TEXT,
            last_activity_type TEXT,
            last_activity_desc TEXT,
            notes TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_files (
            file_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'todo',
            original_key_count INTEGER DEFAULT 0,
            line_count INTEGER DEFAULT 0,
            file_type TEXT DEFAULT 'source',
            FOREIGN KEY (project_id) REFERENCES projects (project_id),
            UNIQUE(project_id, file_path)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (project_id)
        )
    ''')
    
    # 4. Migrate Data
    print("[MIGRATE] Cleaning and Copying Project Data...")
    
    # NEW: Clear tables in main first (since they might have come from Glossary DB copy)
    cursor.execute("DELETE FROM main.projects")
    cursor.execute("DELETE FROM main.project_files")
    cursor.execute("DELETE FROM main.activity_log")
    
    # Projects
    # We need to handle potential missing columns in SRC by selecting literals if needed.
    
    # Check if columns exist in src
    src_columns = [row[1] for row in cursor.execute("PRAGMA src.table_info(projects)").fetchall()]
    
    cols_map = {
        'project_id': 'project_id',
        'name': 'name',
        'game_id': 'game_id',
        'source_path': 'source_path',
        'target_path': 'target_path' if 'target_path' in src_columns else "''",
        'source_language': "'english'" if 'source_language' not in src_columns else 'source_language',
        'status': 'status',
        'created_at': 'created_at',
        'last_modified': "'2025-01-01 00:00:00'" if 'last_modified' not in src_columns else 'last_modified',
        'last_activity_type': "'none'" if 'last_activity_type' not in src_columns else 'last_activity_type',
        'last_activity_desc': "''" if 'last_activity_desc' not in src_columns else 'last_activity_desc',
        'notes': "''" if 'notes' not in src_columns else 'notes'
    }
    
    select_clause = ", ".join([cols_map[c] for c in ['project_id', 'name', 'game_id', 'source_path', 'target_path', 'source_language', 'status', 'created_at', 'last_modified', 'last_activity_type', 'last_activity_desc', 'notes']])

    query = f"""
        INSERT INTO main.projects 
        (project_id, name, game_id, source_path, target_path, source_language, status, created_at, last_modified, last_activity_type, last_activity_desc, notes)
        SELECT 
            {select_clause}
        FROM src.projects
        WHERE project_id IN (?, ?, ?)
    """
    
    print(query)
    cursor.execute(query, (KEEP_PROJECT_IDS[0], KEEP_PROJECT_IDS[1], KEEP_PROJECT_IDS[2]))
    
    # Files
    cursor.execute("""
        INSERT INTO main.project_files
        SELECT * FROM src.project_files
        WHERE project_id IN (?, ?, ?)
    """, (KEEP_PROJECT_IDS[0], KEEP_PROJECT_IDS[1], KEEP_PROJECT_IDS[2]))
    
    # Logs - Do we keep them? Let's keep them for history or maybe clear them.
    # User said "Clean user data" - maybe clean logs?
    # Keeping logs for Demo might be nice to show "history". Let's keep them for these projects.
    
    # Check if activity_log exists in src
    src_tables = [row[0] for row in cursor.execute("SELECT name FROM src.sqlite_master WHERE type='table'").fetchall()]
    
    if 'activity_log' in src_tables:
        cursor.execute("""
            INSERT INTO main.activity_log
            SELECT * FROM src.activity_log
            WHERE project_id IN (?, ?, ?)
        """, (KEEP_PROJECT_IDS[0], KEEP_PROJECT_IDS[1], KEEP_PROJECT_IDS[2]))
    else:
        print("[WARN] activity_log table not found in source DB. Skipping logs.")

    conn.commit()
    
    # 5. Detach
    cursor.execute("DETACH DATABASE src")
    
    # 6. Apply Placeholders
    print("[SANITIZE] Applying path placeholders...")
    
    # Aggressive search: Any path containing demo folder names should be converted.
    demos_folders = {
        'Test_Project_Remis_stellaris': DEMO_ROOT_PLACEHOLDER,
        'Test_Project_Remis_Vic3': DEMO_ROOT_PLACEHOLDER,
        'Test_Project_Remis_EU5': DEMO_ROOT_PLACEHOLDER
    }
    
    for folder, placeholder in demos_folders.items():
        # Source Paths: Replaces anything before the folder name
        # Using a pattern like %/folder_name ensures we match regardless of parent
        pattern = f'%/{folder}'
        alt_pattern = f'%\\{folder}'
        
        cursor.execute(f"UPDATE projects SET source_path = ? || '/{folder}' WHERE source_path LIKE ?", (placeholder, pattern))
        cursor.execute(f"UPDATE projects SET source_path = ? || '/{folder}' WHERE source_path LIKE ?", (placeholder, alt_pattern))
        
        # Translation Paths for demos: 
        # These are usually in my_translation/zh-CN-xxxxx
        # Let's map them robustly.
        trans_folders = {
            'zh-CN-Test_Project_Remis_stellaris': 'zh-CN-Test_Project_Remis_stellaris',
            'zh-CN-Test_Project_Remis_Vic3': 'zh-CN-Test_Project_Remis_Vic3', # Note: mapping to the bundled structure
            'Multilanguage-Test_Project_Remis_Vic3': 'zh-CN-Test_Project_Remis_Vic3',
            'zh-CN-蕾姆丝计划演示模组：最后一位罗马人': 'zh-CN-Test_Project_Remis_Vic3',
            'zh-CN-Test_Project_Remis_EU5': 'zh-CN-Test_Project_Remis_EU5'
        }
        
        for t_folder, bundled_name in trans_folders.items():
             t_pattern = f'%/{t_folder}'
             t_alt_pattern = f'%\\{t_folder}'
             cursor.execute(f"UPDATE projects SET target_path = ? || '/{bundled_name}' WHERE target_path LIKE ? OR target_path LIKE ?", 
                            (TRANS_ROOT_PLACEHOLDER, t_pattern, t_alt_pattern))

    # Force set target_path if it's NULL for our demo projects
    cursor.execute(f"UPDATE projects SET target_path = ? || '/zh-CN-Test_Project_Remis_stellaris' WHERE project_id = ? AND (target_path IS NULL OR target_path = '')", 
                   (TRANS_ROOT_PLACEHOLDER, KEEP_PROJECT_IDS[0]))
    cursor.execute(f"UPDATE projects SET target_path = ? || '/zh-CN-Test_Project_Remis_Vic3' WHERE project_id = ? AND (target_path IS NULL OR target_path = '')", 
                   (TRANS_ROOT_PLACEHOLDER, KEEP_PROJECT_IDS[1]))
    cursor.execute(f"UPDATE projects SET target_path = ? || '/zh-CN-Test_Project_Remis_EU5' WHERE project_id = ? AND (target_path IS NULL OR target_path = '')", 
                   (TRANS_ROOT_PLACEHOLDER, KEEP_PROJECT_IDS[2]))

    conn.commit()
    # file_path in project_files is RELATIVE to project root usually? 
    # Let's check the dump or knowledge...
    # Usually file_path is relative in Remis? 
    # Let's check one record from project_files.
    
    conn.commit()
    
    # Check file paths
    print("[CHECK] Verifying file paths...")
    # If file paths are absolute, we must fix them.
    cursor.execute("SELECT file_path FROM project_files LIMIT 1")
    row = cursor.fetchone()
    if row:
        sample_path = row[0]
        print(f"Sample file path: {sample_path}")
        if "J:" in sample_path or ":" in sample_path:
             print("[SANITIZE] Fixing absolute file paths in project_files...")
             cursor.execute("""
                UPDATE project_files
                SET file_path = REPLACE(file_path, 'J:\\V3_Mod_Localization_Factory\\source_mod\\', ? || '/')
             """, (DEMO_ROOT_PLACEHOLDER,))
             cursor.execute("""
                UPDATE project_files
                SET file_path = REPLACE(file_path, 'J:\\V3_Mod_Localization_Factory\\my_translation\\', ? || '/')
             """, (TRANS_ROOT_PLACEHOLDER,))
             conn.commit()
    
    # 7. Cleanup & Optimize
    print("[CLEAN] Vacuuming...")
    cursor.execute("VACUUM")
    conn.close()
    
    print(f"[SUCCESS] Skeleton Generated at {OUTPUT_DB}")
    
    # 8. Generate Mods Cache Skeleton
    print("\n[INFO] Generating Mods Cache Skeleton...")
    if os.path.exists(MODS_CACHE_DB) and os.path.getsize(MODS_CACHE_DB) > 1024:
        print(f"[COPY] Copying {MODS_CACHE_DB} -> {OUTPUT_CACHE_DB}")
        shutil.copy2(MODS_CACHE_DB, OUTPUT_CACHE_DB)
        print(f"[SUCCESS] Mods Cache Skeleton Generated at {OUTPUT_CACHE_DB}")
    else:
        print(f"[WARN] DEV mods_cache.sqlite not found or empty. Skipping cache skeleton.")
        print(f"[HINT] Run 'Upload Translations' for demo projects in DEV mode to populate it.")

if __name__ == "__main__":
    create_skeleton()
