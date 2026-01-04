import sqlite3
import os
import sys

# Add project root to sys.path to allow imports if needed, 
# though we might just use raw sqlite3 here to avoid dependency issues during build.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from scripts import app_settings

# Configuration
# Configuration
# Exact names from the DB (as seen in diagnostic output)
KEEP_PROJECT_NAMES = [
    "Project Remis - Demo Mod - Stellaris", 
    "蕾姆丝计划 - 演示Mod - 维多利亚3",
    "Project Remis - Demo Mod -EU5"
]
OUTPUT_FILE_MAIN = os.path.join(project_root, 'data', 'seed_data_main.sql')
OUTPUT_FILE_PROJECTS = os.path.join(project_root, 'data', 'seed_data_projects.sql')

# ... (rest of imports and config)
SOURCE_DB = app_settings.DATABASE_PATH
SOURCE_PROJECTS_DB = app_settings.PROJECTS_DB_PATH

def get_db_connection(db_path):
    if not os.path.exists(db_path):
        print(f"Warning: Database not found at {db_path}")
        return None
    return sqlite3.connect(db_path)

def export_schema(cursor, table_name):
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    row = cursor.fetchone()
    if row:
        return row[0] + ";\n"
    return ""

def export_table_data(cursor, table_name, condition=None, params=None):
    query = f"SELECT * FROM {table_name}"
    if condition:
        query += f" WHERE {condition}"
    
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
        
    rows = cursor.fetchall()
    statements = []
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    cols_str = ", ".join(column_names)
    
    for row in rows:
        values = []
        for val in row:
            if val is None:
                values.append("NULL")
            elif isinstance(val, str):
                # Escape single quotes
                val_escaped = val.replace("'", "''")
                values.append(f"'{val_escaped}'")
            else:
                values.append(str(val))
        vals_str = ", ".join(values)
        statements.append(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});")
    
    return statements

def sanitize_path(path):
    path = path.replace("\\", "/")
    # Handle development paths mapping to demos
    if "/source_mod/" in path:
        parts = path.split("/source_mod/")
        return "{{DEMO_ROOT}}/demos/" + parts[1]
    if "/demos/" in path:
        parts = path.split("/demos/")
        return "{{DEMO_ROOT}}/demos/" + parts[1]
    
    # If it's a translation output path in the user's workspace, try to sanitize it
    if "/my_translation/" in path:
         # For seed data, we probably want to clear this or point to a default
         return ""
         
    return path

def main():
    print(f"Exporting seed data...")
    
    # 1. Export Glossary Data (from main DB)
    print(f"Exporting main DB to {OUTPUT_FILE_MAIN}...")
    with open(OUTPUT_FILE_MAIN, 'w', encoding='utf-8') as f:
        f.write("-- Remis Main DB Seed Data\n")
        f.write("BEGIN TRANSACTION;\n\n")
        
        conn_main = get_db_connection(SOURCE_DB)
        if conn_main:
            cursor = conn_main.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                if table == "sqlite_sequence": continue
                f.write(f"-- Schema for {table}\n")
                f.write(export_schema(cursor, table))
                
                f.write(f"-- Data for {table}\n")
                statements = export_table_data(cursor, table)
                for stmt in statements:
                    f.write(stmt + "\n")
                f.write("\n")
            
            conn_main.close()
        f.write("COMMIT;\n")
        
    # 2. Export Projects (from projects.sqlite)
    print(f"Exporting projects DB to {OUTPUT_FILE_PROJECTS}...")
    with open(OUTPUT_FILE_PROJECTS, 'w', encoding='utf-8') as f:
        f.write("-- Remis Projects DB Seed Data\n")
        f.write("BEGIN TRANSACTION;\n\n")
        
        conn_proj = get_db_connection(SOURCE_PROJECTS_DB)
        if conn_proj:
            cursor = conn_proj.cursor()
            
            # Export Schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                if table == "sqlite_sequence": continue
                f.write(f"-- Schema for {table}\n")
                f.write(export_schema(cursor, table))
            
            # Export Data - Selective
            print("Exporting Demo Projects...")
            placeholders = ','.join(['?'] * len(KEEP_PROJECT_NAMES))
            query = f"SELECT * FROM projects WHERE name IN ({placeholders})"
            cursor.execute(query, KEEP_PROJECT_NAMES)
            projects = cursor.fetchall()
            
            col_names = [d[0] for d in cursor.description]
            path_idx = -1
            if 'source_path' in col_names:
                path_idx = col_names.index('source_path')
            
            for row in projects:
                row_list = list(row)
                if path_idx != -1 and row_list[path_idx]:
                    row_list[path_idx] = sanitize_path(row_list[path_idx])
                
                values = []
                for val in row_list:
                    if val is None: values.append("NULL")
                    elif isinstance(val, str): values.append(f"'{val.replace("'", "''")}'")
                    else: values.append(str(val))
                
                f.write(f"INSERT INTO projects ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                
                project_id = row[0]
                
                if 'project_files' in tables:
                    f.write(f"-- Files for project {row_list[1]}\n")
                    
                    cursor.execute("PRAGMA table_info(project_files)")
                    file_cols = [c[1] for c in cursor.fetchall()]
                    file_path_idx = -1
                    if 'file_path' in file_cols:
                        file_path_idx = file_cols.index('file_path')
                        
                    cursor.execute("SELECT * FROM project_files WHERE project_id=?", (project_id,))
                    files = cursor.fetchall()
                    
                    for f_row in files:
                        f_list = list(f_row)
                        if file_path_idx != -1 and f_list[file_path_idx]:
                            f_list[file_path_idx] = sanitize_path(f_list[file_path_idx])
                            
                        f_values = []
                        for val in f_list:
                            if val is None: f_values.append("NULL")
                            elif isinstance(val, str): f_values.append(f"'{val.replace("'", "''")}'")
                            else: f_values.append(str(val))
                        
                        f.write(f"INSERT INTO project_files ({', '.join(file_cols)}) VALUES ({', '.join(f_values)});\n")

            conn_proj.close()
        f.write("COMMIT;\n")
    
    print("Export complete.")

if __name__ == "__main__":
    main()
