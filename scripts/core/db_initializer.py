import json
import logging
import os
import re
import shutil
import sqlite3

from scripts import app_settings
from scripts.core.db_migrations import migrate_main_database


init_logger = logging.getLogger("remis_init")
init_logger.setLevel(logging.DEBUG)
DEV_PROJECT_ROOT_PATTERN = re.compile(r"[A-Za-z]:[\\/]+[^\\/\n]*V3_Mod_Localization_Factory", re.IGNORECASE)


def setup_init_logging():
    try:
        log_dir = app_settings.APP_DATA_DIR
        log_file = os.path.join(log_dir, "init_debug.log")
        abs_log_file = os.path.abspath(log_file)
        for handler in init_logger.handlers:
            if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == abs_log_file:
                return

        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        init_logger.addHandler(file_handler)
        init_logger.info("Logging initialized. AppData: %s", log_dir)
        init_logger.info("Resource Dir: %s", app_settings.RESOURCE_DIR)
    except Exception:
        pass


def is_main_db_fresh(db_path):
    if not os.path.exists(db_path) or os.path.getsize(db_path) < 1024:
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_count = cursor.fetchone()[0]
        conn.close()
        return table_count == 0
    except Exception:
        return True


def import_seed_inserts(conn, seed_path, allowed_tables):
    if not os.path.exists(seed_path):
        init_logger.warning("[SEED] Missing seed file: %s", seed_path)
        return 0

    import re

    inserted = 0
    statement_lines = []

    def flush_statement():
        nonlocal inserted
        if not statement_lines:
            return

        statement = "\n".join(statement_lines).strip()
        statement_lines.clear()

        if not statement.upper().startswith("INSERT INTO"):
            return

        match = re.match(r"INSERT INTO\s+([A-Za-z_][A-Za-z0-9_]*)", statement, re.IGNORECASE)
        if not match:
            return

        table_name = match.group(1)
        if table_name not in allowed_tables:
            return

        safe_statement = re.sub(r"^INSERT INTO", "INSERT OR IGNORE INTO", statement, flags=re.IGNORECASE)
        conn.execute(safe_statement)
        inserted += 1

    with open(seed_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("--"):
                continue

            statement_lines.append(raw_line.rstrip("\n"))
            if stripped.endswith(";"):
                flush_statement()

    flush_statement()
    return inserted


def seed_main_database(db_path, resource_dir):
    data_dir = os.path.join(resource_dir, "data")
    seed_main = os.path.join(data_dir, "seed_data_main.sql")
    seed_projects = os.path.join(data_dir, "seed_data_projects.sql")

    conn = sqlite3.connect(db_path)
    try:
        main_count = import_seed_inserts(conn, seed_main, {"glossaries", "entries"})
        project_count = import_seed_inserts(
            conn,
            seed_projects,
            {"projects", "project_files", "project_history", "activity_log"},
        )
        conn.commit()
        init_logger.info(
            "[SEED] Imported %s main statements and %s project statements.",
            main_count,
            project_count,
        )
    finally:
        conn.close()


def fix_demo_paths(conn, persistent_demo_root, persistent_translation_root):
    """Hydrates demo placeholders and legacy dev paths with current runtime paths."""
    try:
        demo_root = persistent_demo_root.replace("\\", "/")
        trans_root = persistent_translation_root.replace("\\", "/")
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        if not cursor.fetchone():
            return

        init_logger.info("[INIT] Hydrating demo paths. Source: %s, Translation: %s", demo_root, trans_root)

        demo_folders = [
            "Test_Project_Remis_stellaris",
            "Test_Project_Remis_Vic3",
            "Test_Project_Remis_EU5",
        ]
        translation_folders = {
            "zh-CN-Test_Project_Remis_stellaris": "zh-CN-Test_Project_Remis_stellaris",
            "Multilanguage-Test_Project_Remis_stellaris": "zh-CN-Test_Project_Remis_stellaris",
            "zh-CN-Test_Project_Remis_Vic3": "zh-CN-Test_Project_Remis_Vic3",
            "Multilanguage-Test_Project_Remis_Vic3": "zh-CN-Test_Project_Remis_Vic3",
            "zh-CN-Test_Project_Remis_EU5": "zh-CN-Test_Project_Remis_EU5",
        }

        def remap_known_path(path_value):
            if not path_value:
                return path_value

            normalized = path_value.replace("\\", "/")
            normalized = normalized.replace("{{BUNDLED_DEMO_ROOT}}", demo_root)
            normalized = normalized.replace("{{BUNDLED_TRANSLATION_ROOT}}", trans_root)
            normalized = normalized.replace("{{DEMO_ROOT}}/demos", demo_root)
            normalized = normalized.replace("{{DEMO_ROOT}}", demo_root)

            for folder in demo_folders:
                marker = f"/{folder}"
                if marker in normalized:
                    suffix = normalized.split(marker, 1)[1]
                    return f"{demo_root}/{folder}{suffix}"

            for folder_name, bundled_name in translation_folders.items():
                marker = f"/{folder_name}"
                if marker in normalized:
                    suffix = normalized.split(marker, 1)[1]
                    return f"{trans_root}/{bundled_name}{suffix}"

            return normalized

        dev_root_pattern = re.compile(r".*V3_Mod_Localization_Factory/source_mod/", re.IGNORECASE)
        trans_root_pattern = re.compile(r".*V3_Mod_Localization_Factory/my_translation/", re.IGNORECASE)

        cursor.execute("SELECT project_id, source_path, target_path FROM projects")
        for pid, s_path, t_path in cursor.fetchall():
            if not s_path:
                continue

            new_s = remap_known_path(s_path)
            new_t = remap_known_path(t_path) if t_path else ""

            if dev_root_pattern.search(new_s):
                new_s = dev_root_pattern.sub(demo_root + "/", new_s)
            if t_path and trans_root_pattern.search(new_t):
                new_t = trans_root_pattern.sub(trans_root + "/", new_t)

            if new_s != s_path or new_t != t_path:
                cursor.execute(
                    "UPDATE projects SET source_path = ?, target_path = ? WHERE project_id = ?",
                    (new_s, new_t, pid),
                )

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_files'")
        if cursor.fetchone():
            cursor.execute("SELECT file_id, file_path FROM project_files")
            for fid, f_path in cursor.fetchall():
                if not f_path:
                    continue

                new_f = remap_known_path(f_path)
                if dev_root_pattern.search(new_f):
                    new_f = dev_root_pattern.sub(demo_root + "/", new_f)

                if new_f != f_path:
                    cursor.execute("UPDATE project_files SET file_path = ? WHERE file_id = ?", (new_f, fid))

        init_logger.info("[INIT] Running self-healing repairs...")

        try:
            old_dir_name = "Multilanguage-Test_Project_Remis_Vic3"
            new_dir_name = "zh-CN-Test_Project_Remis_Vic3"
            old_full_path = os.path.join(persistent_translation_root, old_dir_name)
            new_full_path = os.path.join(persistent_translation_root, new_dir_name)
            if os.path.exists(old_full_path) and not os.path.exists(new_full_path):
                shutil.move(old_full_path, new_full_path)
                init_logger.info("[REPAIR] Renamed valid disk folder: %s -> %s", old_dir_name, new_dir_name)
        except Exception as e:
            init_logger.error("[REPAIR] Failed to rename disk folder: %s", e)

        cursor.execute(
            """
            UPDATE projects
            SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_Vic3', 'zh-CN-Test_Project_Remis_Vic3')
            WHERE project_id = 'a525f596-6c71-43fe-ade2-52c9205a2720'
              AND target_path LIKE '%Multilanguage-Test_Project_Remis_Vic3%'
            """
        )

        try:
            old_dir_name = "Multilanguage-Test_Project_Remis_stellaris"
            new_dir_name = "zh-CN-Test_Project_Remis_stellaris"
            old_full_path = os.path.join(persistent_translation_root, old_dir_name)
            new_full_path = os.path.join(persistent_translation_root, new_dir_name)
            if os.path.exists(old_full_path) and not os.path.exists(new_full_path):
                shutil.move(old_full_path, new_full_path)
                init_logger.info("[REPAIR] Renamed valid disk folder: %s -> %s", old_dir_name, new_dir_name)
        except Exception as e:
            init_logger.error("[REPAIR] Failed to rename disk folder (Stellaris): %s", e)

        cursor.execute(
            """
            UPDATE projects
            SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_stellaris', 'zh-CN-Test_Project_Remis_stellaris')
            WHERE project_id = '6049331a-433d-4d09-9205-165c3aad6010'
              AND target_path LIKE '%Multilanguage-Test_Project_Remis_stellaris%'
            """
        )

        cursor.execute(
            "UPDATE glossaries SET is_main = 1 WHERE game_id = 'eu5' AND name = 'remis_demo_eu5' AND is_main = 0"
        )
        conn.commit()
    except Exception as e:
        init_logger.error("[ERROR] Failed to fix demo paths: %s", e)


def run_projects_db_migrations(db_path):
    """Handles schema updates for the managed main database."""
    try:
        version = migrate_main_database(db_path)
        init_logger.info("Database schema initialized/verified with migrations. Current version: %s", version)
    except Exception as e:
        init_logger.error("Failed to run DB migrations: %s", e)


def hydrate_json_configs(app_data_dir):
    """Recursively finds all .remis_project.json files and fixes hardcoded paths."""
    init_logger.info("[JSON] Hydrating .remis_project.json files (Targeted Scan)...")

    app_data_root = app_data_dir.replace("\\", "/")
    target_dirs = [
        os.path.join(app_data_dir, "my_translation"),
        os.path.join(app_data_dir, "demos"),
    ]

    fix_count = 0
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue

        for root, _, files in os.walk(target_dir):
            if ".remis_project.json" not in files:
                continue

            json_path = os.path.join(root, ".remis_project.json")
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    content = f.read()

                original_content = content
                content = DEV_PROJECT_ROOT_PATTERN.sub(app_data_root, content)

                content = content.replace("/source_mod/", "/demos/")
                content = content.replace("\\\\source_mod\\\\", "/demos/")
                content = content.replace("Multilanguage-Test_Project_Remis_Vic3", "zh-CN-Test_Project_Remis_Vic3")
                content = content.replace(
                    "Multilanguage-Test_Project_Remis_stellaris",
                    "zh-CN-Test_Project_Remis_stellaris",
                )
                content = content.replace("\\\\", "/")

                if content != original_content:
                    with open(json_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    fix_count += 1
                    init_logger.info("[JSON] Fixed paths in: %s", json_path)
            except Exception as e:
                init_logger.error("Failed to hydrate JSON at %s: %s", json_path, e)

    init_logger.info("[JSON] Hydration complete. Fixed %s config files.", fix_count)


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

    if not os.path.exists(config_path):
        init_logger.info("[INIT] Config missing. Creating default config.json.")
        default_config = {
            "api_keys": {},
            "theme": "dark",
            "language": "zh-CN",
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
        except Exception as e:
            init_logger.error("Failed to create config: %s", e)

    main_db_is_fresh = is_main_db_fresh(remis_db_path)
    if main_db_is_fresh:
        init_logger.info("[INIT] Fresh main DB detected. Building schema and importing seeds.")

    mods_cache_path = os.path.join(app_data_dir, "mods_cache.sqlite")
    mods_cache_skeleton = os.path.join(resource_dir, "assets", "mods_cache_skeleton.sqlite")
    if main_db_is_fresh:
        try:
            if os.path.exists(mods_cache_skeleton):
                if os.path.exists(mods_cache_path):
                    os.remove(mods_cache_path)
                shutil.copy2(mods_cache_skeleton, mods_cache_path)
                init_logger.info("Mods Cache Skeleton copied (AI Drafts pre-populated).")
            else:
                init_logger.info("Mods Cache Skeleton not bundled. AI Drafts will be empty until Upload.")
        except Exception as e:
            init_logger.error("Mods Cache Copy failed: %s", e)

    p_demos = os.path.join(app_data_dir, "demos")
    b_demos = os.path.join(resource_dir, "demos")
    p_trans = os.path.join(app_data_dir, "my_translation")
    b_trans = os.path.join(resource_dir, "my_translation")

    def extract(src_dir, dst_dir, label, force=False):
        if os.path.exists(src_dir) and (not os.path.exists(dst_dir) or force):
            try:
                if os.path.exists(dst_dir):
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                init_logger.info("%s extracted (Force=%s).", label, force)
                return True
            except Exception as e:
                init_logger.error("Failed to extract %s: %s", label, e)
        return False

    def safe_extract_configs(src_dir, dst_dir):
        if not os.path.exists(src_dir):
            return
        if not os.path.exists(dst_dir):
            try:
                os.makedirs(dst_dir)
            except OSError:
                return

        for filename in os.listdir(src_dir):
            src_file = os.path.join(src_dir, filename)
            dst_file = os.path.join(dst_dir, filename)
            if os.path.isfile(src_file) and not os.path.exists(dst_file):
                try:
                    shutil.copy2(src_file, dst_file)
                    init_logger.info("[CONFIG] Extracted default config: %s", filename)
                except Exception as e:
                    init_logger.error("[CONFIG] Failed to extract %s: %s", filename, e)

    demo_extracted = extract(b_demos, p_demos, "Demos", force=main_db_is_fresh)
    trans_extracted = extract(b_trans, p_trans, "Translations", force=False)

    config_dir = app_settings.CONFIG_DIR
    bundled_config_dir = os.path.join(resource_dir, "data", "config")
    safe_extract_configs(bundled_config_dir, config_dir)

    run_projects_db_migrations(remis_db_path)

    if main_db_is_fresh:
        try:
            seed_main_database(remis_db_path, resource_dir)
        except Exception as e:
            init_logger.error("[SEED] Failed to import main DB seed data: %s", e)

    if demo_extracted or trans_extracted or main_db_is_fresh:
        try:
            conn = sqlite3.connect(remis_db_path)
            fix_demo_paths(conn, p_demos, p_trans)
            conn.close()
            hydrate_json_configs(app_data_dir)
        except Exception as e:
            init_logger.error("[INIT] Failed during path hydration: %s", e)
