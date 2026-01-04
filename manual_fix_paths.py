
import sqlite3
import os
from scripts.app_settings import REMIS_DB_PATH

def manual_fix_paths():
    print(f"Repairing database at: {REMIS_DB_PATH}")
    if not os.path.exists(REMIS_DB_PATH):
        print("DB not found")
        return

    conn = sqlite3.connect(REMIS_DB_PATH)
    cursor = conn.cursor()
    
    # Simulate the self-healing logic I just added
    print("Running self-healing repairs...")
    
    # 1. Fix Vic3 Demo Path (Multilanguage -> zh-CN)
    cursor.execute("""
        UPDATE projects 
        SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_Vic3', 'zh-CN-Test_Project_Remis_Vic3')
        WHERE project_id = 'a525f596-6c71-43fe-ade2-52c9205a2720' 
          AND target_path LIKE '%Multilanguage-Test_Project_Remis_Vic3%'
    """)
    print(f"[REPAIR] Fixed {cursor.rowcount} Vic3 path issues.")

    # 2. Fix Stellaris Demo Path
    cursor.execute("""
        UPDATE projects 
        SET target_path = REPLACE(target_path, 'Multilanguage-Test_Project_Remis_stellaris', 'zh-CN-Test_Project_Remis_stellaris')
        WHERE project_id = '6049331a-433d-4d09-9205-165c3aad6010'
          AND target_path LIKE '%Multilanguage-Test_Project_Remis_stellaris%'
    """)
    print(f"[REPAIR] Fixed {cursor.rowcount} Stellaris path issues.")

    # 3. Ensure EU5 Demo Glossary is Main
    cursor.execute("UPDATE glossaries SET is_main = 1 WHERE game_id = 'eu5' AND name = 'remis_demo_eu5' AND is_main = 0")
    print(f"[REPAIR] Fixed {cursor.rowcount} EU5 demo glossary issues.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    manual_fix_paths()
