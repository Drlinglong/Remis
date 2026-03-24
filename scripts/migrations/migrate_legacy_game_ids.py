import asyncio
import os
import sys
import json
from pathlib import Path
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.getcwd())

from scripts.core.db_manager import DatabaseConnectionManager
from scripts.app_settings import GAME_ID_ALIASES, PROJECTS_DB_PATH
from scripts.core.project_json_manager import ProjectJsonManager

async def migrate_database(db_path: str):
    """Update legacy game IDs in the SQLite database to their standard format."""
    print("Migrating SQLite Database...")
    manager = DatabaseConnectionManager(db_path)
    
    async for session in manager.get_async_session():
        updated_count = 0
        try:
            # We assume GAME_ID_ALIASES correctly maps 'vic3' -> 'victoria3' etc.
            # Only update if the current game_id is a known alias and not already the standard value.
            # We will iterate through all aliases to build the update query.
            
            # Use raw SQL for batch update
            for alias, standard_id in GAME_ID_ALIASES.items():
                if alias != standard_id: # Avoid unnecessary updates
                    stmt = text("UPDATE projects SET game_id = :standard WHERE game_id = :alias")
                    result = await session.execute(stmt, {"standard": standard_id, "alias": alias})
                    updated_count += result.rowcount
            
            await session.commit()
            print(f"Database Migration Complete: {updated_count} project records updated.")
        except Exception as e:
            await session.rollback()
            print(f"Error during DB migration: {e}")

def migrate_project_sidecars():
    """Update legacy game IDs in .remis_project.json files."""
    print("Migrating Project Sidecar Files...")
    workspaces_dir = Path("j:/V3_Mod_Localization_Factory/source_mod") # Or read from config if needed, but relative to CWD is fine for this script
    if not workspaces_dir.exists():
        print(f"Directory {workspaces_dir} not found. Ensure you run this from the project root.")
        # Fallback to current directory scanning just in case
        workspaces_dir = Path(".")

    updated_count = 0
    # recursively find all .remis_project.json
    for json_path in workspaces_dir.rglob(".remis_project.json"):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            current_id = data.get('game_id')
            if current_id and current_id in GAME_ID_ALIASES:
                standard_id = GAME_ID_ALIASES[current_id]
                if current_id != standard_id:
                    data['game_id'] = standard_id
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    updated_count += 1
                    print(f"Updated sidecar: {json_path} ('{current_id}' -> '{standard_id}')")
        except Exception as e:
            print(f"Error updating sidecar {json_path}: {e}")
            
    print(f"Sidecar Migration Complete: {updated_count} files updated.")

async def main():
    print("--- Starting Architecture Refactor Migration ---")
    await migrate_database(PROJECTS_DB_PATH)
    migrate_project_sidecars()
    print("--- Migration Finished ---")

if __name__ == "__main__":
    asyncio.run(main())
