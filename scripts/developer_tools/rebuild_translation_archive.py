import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.app_settings import MODS_CACHE_DB_PATH
from scripts.core.project_manager import ProjectManager
from scripts.core.services.translation_archive_service import TranslationArchiveService


async def rebuild_archive(project_ids=None, include_archived=False, reset_db=False):
    if reset_db and os.path.exists(MODS_CACHE_DB_PATH):
        os.remove(MODS_CACHE_DB_PATH)
        print(f"[INFO] Removed existing archive DB: {MODS_CACHE_DB_PATH}")

    manager = ProjectManager()
    archive_service = TranslationArchiveService()

    projects = await manager.repository.list_projects()
    selected = []
    for project in projects:
        data = project.model_dump()
        if project_ids and data["project_id"] not in project_ids:
            continue
        if not include_archived and data.get("status") == "archived":
            continue
        selected.append(data)

    print(f"[INFO] Rebuilding archive for {len(selected)} project(s)")
    for project in selected:
        source_path = project.get("source_path")
        if not source_path or not Path(source_path).exists():
            print(f"[WARN] Skipping {project['name']} ({project['project_id']}): source path missing")
            continue

        print(f"[INFO] Rebuilding {project['name']} ({project['project_id']})")
        result = archive_service.upload_project_translations(
            project_id=project["project_id"],
            project_name=project["name"],
            source_path=source_path,
            source_lang_code=project.get("source_language", "en"),
        )
        print(
            f"[INFO]   status={result.get('status')} "
            f"match_count={result.get('match_count', 0)} "
            f"message={result.get('message', '')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Rebuild translation archive DB from current projects.")
    parser.add_argument("--project-id", action="append", dest="project_ids", help="Only rebuild the specified project_id. Can be repeated.")
    parser.add_argument("--include-archived", action="store_true", help="Include archived projects.")
    parser.add_argument("--reset-db", action="store_true", help="Delete mods_cache.sqlite before rebuilding.")
    args = parser.parse_args()

    asyncio.run(
        rebuild_archive(
            project_ids=args.project_ids,
            include_archived=args.include_archived,
            reset_db=args.reset_db,
        )
    )


if __name__ == "__main__":
    main()
