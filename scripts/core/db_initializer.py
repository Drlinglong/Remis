import shutil
import logging
import os
import sqlite3
from scripts import app_settings

# Setup a dedicated logger for initialization that writes to a file in AppData
init_logger = logging.getLogger("remis_init")
init_logger.setLevel(logging.DEBUG)

def setup_init_logging():
    try:
        log_dir = app_settings.APP_DATA_DIR
        log_file = os.path.join(log_dir, "init_debug.log")
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        init_logger.addHandler(file_handler)
        init_logger.info(f"Logging initialized. AppData: {log_dir}")
        init_logger.info(f"Resource Dir: {app_settings.RESOURCE_DIR}")
    except Exception:
        pass

def fix_demo_paths(conn, persistent_demo_root, persistent_translation_root):
    """Hydrates placeholders in the database with actual persistent AppData paths using robust regex."""
    import re
    try:
        demo_root = persistent_demo_root.replace("\\", "/")
        trans_root = persistent_translation_root.replace("\\", "/")
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        if not cursor.fetchone():
            return

        init_logger.info(f"[INIT] Hydrating demo paths. Source: {demo_root}, Translation: {trans_root}")
        
        # 1. Update Placeholders
        cursor.execute("UPDATE projects SET source_path = REPLACE(source_path, '{{BUNDLED_DEMO_ROOT}}', ?)", (demo_root,))
        cursor.execute("UPDATE projects SET target_path = REPLACE(target_path, '{{BUNDLED_TRANSLATION_ROOT}}', ?)", (trans_root,))
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_files'")
        if cursor.fetchone():
             cursor.execute("UPDATE project_files SET file_path = REPLACE(file_path, '{{BUNDLED_DEMO_ROOT}}', ?)", (demo_root,))

        # 2. Robust Regex Fix for leaked Dev Paths (Case insensitive, slash agnostic)
        # We find anything that looks like J:\...V3_Mod_Localization_Factory\source_mod\... and map to demo_root
        # And any J:\...V3_Mod_Localization_Factory\my_translation\... map to trans_root
        
        dev_root_pattern = re.compile(r".*V3_Mod_Localization_Factory/source_mod/", re.IGNORECASE)
        trans_root_pattern = re.compile(r".*V3_Mod_Localization_Factory/my_translation/", re.IGNORECASE)

        # Process projects
        cursor.execute("SELECT project_id, source_path, target_path FROM projects")
        projects = cursor.fetchall()
        for pid, s_path, t_path in projects:
            new_s = s_path.replace("\\", "/")
            new_t = t_path.replace("\\", "/") if t_path else ""
            
            # Apply regex
            if dev_root_pattern.search(new_s):
                new_s = dev_root_pattern.sub(demo_root + "/", new_s)
            
            if t_path and trans_root_pattern.search(new_t):
                new_t = trans_root_pattern.sub(trans_root + "/", new_t)
            
            if new_s != s_path or new_t != t_path:
                cursor.execute("UPDATE projects SET source_path = ?, target_path = ? WHERE project_id = ?", (new_s, new_t, pid))

        # Process project_files
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_files'")
        if cursor.fetchone():
            cursor.execute("SELECT file_id, file_path FROM project_files")
            files = cursor.fetchall()
            for fid, f_path in files:
                new_f = f_path.replace("\\", "/")
                if dev_root_pattern.search(new_f):
                    new_f = dev_root_pattern.sub(demo_root + "/", new_f)
                
                if new_f != f_path:
                    cursor.execute("UPDATE project_files SET file_path = ? WHERE file_id = ?", (new_f, fid))
        
        # [REPAIR] Self-Healing for Known Hydration Errors
        init_logger.info("[INIT] Running self-healing repairs...")
        
        # 1. Fix Vic3 Demo Path (Multilanguage -> zh-CN)
        # Fixes: C:/.../Multilanguage-Test_Project_Remis_Vic3 -> C:/.../zh-CN-Test_Project_Remis_Vic3
        # [CRITICAL] Also rename the directory on disk if it exists!
        try:
            old_dir_name = "Multilanguage-Test_Project_Remis_Vic3"
            new_dir_name = "zh-CN-Test_Project_Remis_Vic3"
            
            # persistent_translation_root is passed as an arg to this function
            # Ensure we are looking in the Translation Root
            p_trans_root = persistent_translation_root # e.g. .../my_translation
            
            old_full_path = os.path.join(p_trans_root, old_dir_name)
            new_full_path = os.path.join(p_trans_root, new_dir_name)
            
            if os.path.exists(old_full_path) and not os.path.exists(new_full_path):
                import shutil
                shutil.move(old_full_path, new_full_path)
                init_logger.info(f"[REPAIR] Renamed valid disk folder: {old_dir_name} -> {new_dir_name}")
            elif os.path.exists(old_full_path) and os.path.exists(new_full_path):
                # Ambiguous state, merge or trust new? Trust new, maybe removing old to avoid confusion
                # For safety, let's just log
                init_logger.warning(f"[REPAIR] Both {old_dir_name} and {new_dir_name} exist. Using {new_dir_name}.")
        except Exception as e:
            init_logger.error(f"[REPAIR] Failed to rename disk folder: {e}")

        cursor.execute("""
            UPDATE projects 
            SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_Vic3', 'zh-CN-Test_Project_Remis_Vic3')
            WHERE project_id = 'a525f596-6c71-43fe-ade2-52c9205a2720' 
              AND target_path LIKE '%Multilanguage-Test_Project_Remis_Vic3%'
        """)
        if cursor.rowcount > 0:
            init_logger.info(f"[REPAIR] Fixed {cursor.rowcount} Vic3 path issues.")

        # 2. Fix Stellaris Demo Path (if needed)
        try:
            old_dir_name = "Multilanguage-Test_Project_Remis_stellaris"
            new_dir_name = "zh-CN-Test_Project_Remis_stellaris"
            
            p_trans_root = persistent_translation_root
            
            old_full_path = os.path.join(p_trans_root, old_dir_name)
            new_full_path = os.path.join(p_trans_root, new_dir_name)
            
            if os.path.exists(old_full_path) and not os.path.exists(new_full_path):
                import shutil
                shutil.move(old_full_path, new_full_path)
                init_logger.info(f"[REPAIR] Renamed valid disk folder: {old_dir_name} -> {new_dir_name}")
        except Exception as e:
            init_logger.error(f"[REPAIR] Failed to rename disk folder (Stellaris): {e}")

        cursor.execute("""
            UPDATE projects 
            SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_stellaris', 'zh-CN-Test_Project_Remis_stellaris')
            WHERE project_id = '6049331a-433d-4d09-9205-165c3aad6010'
              AND target_path LIKE '%Multilanguage-Test_Project_Remis_stellaris%'
        """)

        # 3. Ensure EU5 Demo Glossary is Main
        # Fixes: Glossary not being selected automatically
        cursor.execute("UPDATE glossaries SET is_main = 1 WHERE game_id = 'eu5' AND name = 'remis_demo_eu5' AND is_main = 0")
        if cursor.rowcount > 0:
            init_logger.info(f"[REPAIR] Fixed EU5 demo glossary is_main flag.")

        conn.commit()
    except Exception as e:
        init_logger.error(f"[ERROR] Failed to fix demo paths: {e}")

def run_projects_db_migrations(conn):
    """Handles schema updates for the Projects database."""
    cursor = conn.cursor()
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
    conn.commit()

def hydrate_json_configs(app_data_dir):
    """Recursively finds all .remis_project.json files and fixes hardcoded paths safely and quickly."""
    init_logger.info("[JSON] Hydrating .remis_project.json files (Targeted Scan)...")
    import json
    import re
    
    # Normalize app_data_dir to forward slashes for replacement
    app_data_root = app_data_dir.replace("\\", "/")
    
    # Dev paths in both forward and escaped backslash formats
    dev_roots = [
        'J:/V3_Mod_Localization_Factory',
        'j:/V3_Mod_Localization_Factory',
        'J:\\\\V3_Mod_Localization_Factory',  # Escaped backslashes in JSON
        'j:\\\\V3_Mod_Localization_Factory',
    ]
    
    # Add source_mod -> demos mapping for path structure change
    source_replacements = [
        ('source_mod', 'demos'),  # source_mod in dev becomes demos in prod
    ]
    
    target_dirs = [
        os.path.join(app_data_dir, "my_translation"),
        os.path.join(app_data_dir, "demos")
    ]
    
    fix_count = 0
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
            
        for root, dirs, files in os.walk(target_dir):
            if ".remis_project.json" in files:
                json_path = os.path.join(root, ".remis_project.json")
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Replace all dev root variants
                    for dr in dev_roots:
                        content = content.replace(dr, app_data_root)
                    
                    # Also handle 'source_mod' -> 'demos' path structure
                    content = content.replace('/source_mod/', '/demos/')
                    content = content.replace('\\\\source_mod\\\\', '/demos/')
                    
                    # [FIX] Repair Multilanguage path legacy error in JSON
                    content = content.replace('Multilanguage-Test_Project_Remis_Vic3', 'zh-CN-Test_Project_Remis_Vic3')
                    content = content.replace('Multilanguage-Test_Project_Remis_stellaris', 'zh-CN-Test_Project_Remis_stellaris')

                    # Normalize all double backslashes to forward slashes (JSON escaped)
                    content = content.replace('\\\\', '/')
                    
                    if content != original_content:
                        with open(json_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        fix_count += 1
                        init_logger.info(f"[JSON] Fixed paths in: {json_path}")
                except Exception as e:
                    init_logger.error(f"Failed to hydrate JSON at {json_path}: {e}")
    init_logger.info(f"[JSON] Hydration complete. Fixed {fix_count} config files.")

def initialize_database():
    """Main entry point for DB setup."""
    setup_init_logging()
    init_logger.info("Starting Database Initialization...")

    remis_db_path = app_settings.REMIS_DB_PATH
    app_data_dir = app_settings.APP_DATA_DIR
    resource_dir = app_settings.RESOURCE_DIR
    config_path = app_settings.get_appdata_config_path()
    
    os.makedirs(app_data_dir, exist_ok=True)
    os.makedirs(os.path.dirname(remis_db_path), exist_ok=True)
    
    # [NEW] Config Self-Healing
    if not os.path.exists(config_path):
        init_logger.info("[INIT] Config missing. Creating default config.json.")
        import json
        default_config = {
            "api_keys": {},
            "theme": "dark",
            "language": "zh-CN"
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
        except Exception as e:
            init_logger.error(f"Failed to create config: {e}")

    db_needs_init = False
    
    # [STALE PATH CHECK]
    import sys
    # [STALE PATH CHECK] - Only for Frozen (End User) builds
    # In Dev mode, we expect V3_Mod_Localization_Factory paths.
    if getattr(sys, "frozen", False) and os.path.exists(remis_db_path) and os.path.getsize(remis_db_path) > 1024:
        try:
            conn = sqlite3.connect(remis_db_path)
            cursor = conn.cursor()
            # Double check: Any remaining "V3_Mod_Localization_Factory" leaked paths?
            cursor.execute("SELECT count(*) FROM projects WHERE source_path LIKE '%V3_Mod_Localization_Factory%' OR target_path LIKE '%V3_Mod_Localization_Factory%'")
            if cursor.fetchone()[0] > 0:
                db_needs_init = True
                init_logger.info("Detected leaked paths in DB. Forcing re-init.")
            
            if not db_needs_init:
                cursor.execute("SELECT count(*) FROM projects")
                if cursor.fetchone()[0] == 0:
                    db_needs_init = True
                    init_logger.info("Projects table is empty. Forcing re-init.")
            conn.close()
        except Exception:
            db_needs_init = True

    if not os.path.exists(remis_db_path) or os.path.getsize(remis_db_path) < 1024:
        db_needs_init = True

    if db_needs_init:
        init_logger.info("[INIT] Extracting fresh DB from Skeleton...")
        skeleton_source = os.path.join(resource_dir, "assets", "skeleton.sqlite")
        try:
            if os.path.exists(remis_db_path): os.remove(remis_db_path)
            if os.path.exists(skeleton_source):
                shutil.copy2(skeleton_source, remis_db_path)
                init_logger.info("Skeleton DB copied.")
            else:
                init_logger.error("Skeleton DB missing!")
        except Exception as e:
            init_logger.error(f"DB Copy failed: {e}")
        
        # [NEW] Also extract mods_cache_skeleton.sqlite for pre-populated AI Drafts
        mods_cache_path = os.path.join(app_data_dir, "mods_cache.sqlite")
        mods_cache_skeleton = os.path.join(resource_dir, "assets", "mods_cache_skeleton.sqlite")
        try:
            if os.path.exists(mods_cache_skeleton):
                if os.path.exists(mods_cache_path): os.remove(mods_cache_path)
                shutil.copy2(mods_cache_skeleton, mods_cache_path)
                init_logger.info("Mods Cache Skeleton copied (AI Drafts pre-populated).")
            else:
                init_logger.info("Mods Cache Skeleton not bundled. AI Drafts will be empty until Upload.")
        except Exception as e:
            init_logger.error(f"Mods Cache Copy failed: {e}")

    # Extraction of Demo Mods
    p_demos = os.path.join(app_data_dir, "demos")
    b_demos = os.path.join(resource_dir, "demos")
    p_trans = os.path.join(app_data_dir, "my_translation")
    b_trans = os.path.join(resource_dir, "my_translation")

    def extract(b, p, l, force=False):
        if os.path.exists(b) and (not os.path.exists(p) or db_needs_init or force):
            try:
                if os.path.exists(p): shutil.rmtree(p)
                shutil.copytree(b, p)
                init_logger.info(f"{l} extracted (Force={force}).")
                return True
            except Exception: pass
        return False

    # Force update demos to ensure new assets (English files) are present
    demo_ex = extract(b_demos, p_demos, "Demos", force=True) 
    trans_ex = extract(b_trans, p_trans, "Translations", force=False)

    if demo_ex or trans_ex or db_needs_init:
        try:
            conn = sqlite3.connect(remis_db_path)
            fix_demo_paths(conn, p_demos, p_trans)
            conn.close()
            hydrate_json_configs(app_data_dir)
        except Exception: pass

    # Migrations
    try:
        conn = sqlite3.connect(remis_db_path)
        run_projects_db_migrations(conn)
        conn.close()
    except Exception: pass
