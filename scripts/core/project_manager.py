import sqlite3
import os
import shutil
import uuid
import re
import datetime
import logging
import asyncio
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path
from scripts.app_settings import PROJECTS_DB_PATH, SOURCE_DIR, GAME_ID_ALIASES

if TYPE_CHECKING:
    from scripts.schemas.translation import IncrementalUpdateConfig

# Configure logger
logger = logging.getLogger(__name__)

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services.kanban_service import KanbanService
from scripts.core.services.translation_archive_service import TranslationArchiveService
from scripts.utils.i18n_utils import paradox_to_iso
from scripts.core.db_models import Project as DBProject, ProjectFile as DBProjectFile, ProjectHistory

# Keep deprecated dataclasses for backward compatibility if imported elsewhere,
# but internally we use DBProject/DBProjectFile Pydantic models.
@dataclass
class Project:
    project_id: str
    name: str
    game_id: str
    source_path: str
    target_path: str
    status: str
    created_at: str
    notes: str = ""

@dataclass
class ProjectFile:
    file_id: str
    project_id: str
    file_path: str
    status: str
    original_key_count: int
    line_count: int = 0
    file_type: str = 'source'

class ProjectManager:
    def __init__(self, file_service=None, project_repository=None, kanban_service=None, archive_service=None, db_path: str = PROJECTS_DB_PATH):
        """
        Args:
            file_service: Injected FileService instance. 
            project_repository: Injected ProjectRepository instance.
            kanban_service: Injected KanbanService instance.
        """
        self.db_path = db_path
        self.file_service = file_service
        self.repository = project_repository
        self.kanban_service = kanban_service

        # Fallback for KanbanService
        if not self.kanban_service:
            if self.file_service and hasattr(self.file_service, 'kanban_service'):
                 self.kanban_service = self.file_service.kanban_service
            else:
                from scripts.core.services.kanban_service import KanbanService
                self.kanban_service = KanbanService(repository=self.repository)
        
        # Fallback for Repository
        if not self.repository:
            from scripts.core.repositories.project_repository import ProjectRepository
            self.repository = ProjectRepository(db_path)

        self.archive_service = archive_service or TranslationArchiveService()

    async def create_project(self, name: str, folder_path: str, game_id: str, source_language: str) -> Dict[str, Any]:
        """
        Creates a new project.
        """
        # Normalize game_id
        game_id = GAME_ID_ALIASES.get(game_id.lower(), game_id)
        
        logger.info(f"Creating project '{name}' from '{folder_path}' for game '{game_id}' (Source: {source_language})")

        # 1. Handle Folder Movement/Validation
        source_root = os.path.abspath(SOURCE_DIR)
        abs_folder_path = os.path.abspath(folder_path)
        final_source_path = abs_folder_path

        if not abs_folder_path.startswith(source_root):
            logger.info(f"Folder {abs_folder_path} is not in {source_root}. Moving...")
            target_dir_name = os.path.basename(abs_folder_path)
            final_source_path = os.path.join(source_root, target_dir_name)
            counter = 1
            base_name = target_dir_name
            while os.path.exists(final_source_path):
                target_dir_name = f"{base_name}_{counter}"
                final_source_path = os.path.join(source_root, target_dir_name)
                counter += 1

            try:
                shutil.copytree(abs_folder_path, final_source_path)
                logger.info(f"Copied to {final_source_path}")
            except Exception as e:
                logger.error(f"Failed to copy folder: {e}")
                raise RuntimeError(f"Failed to copy folder to source directory: {e}")
        else:
            logger.info("Folder is already in source directory.")

        project_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        
        new_project = DBProject(
            project_id=project_id,
            name=name,
            game_id=game_id,
            source_path=final_source_path,
            source_language=source_language,
            status='active',
            created_at=now,
            last_modified=now
        )
        
        saved_project = await self.repository.create_project(new_project)
        
        # Initialize JSON sidecar
        json_manager = ProjectJsonManager(final_source_path)
        json_manager.update_config({
            "translation_dirs": [],
            "source_language": source_language
        })

        # Scan files (Initial Scan)
        await self.refresh_project_files(project_id)

        # Log initial creation history
        await self.log_history_event(
            project_id=project_id,
            action_type="import",
            description=f"Project '{name}' created and source files imported."
        )
        
        return saved_project.model_dump()

    async def get_project_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves project details associated with a specific file ID."""
        project_data = await self.repository.get_project_by_file_id(file_id)
        if project_data:
             try:
                 source_path = project_data.get('source_path')
                 if source_path:
                    json_manager = ProjectJsonManager(source_path)
                    config = json_manager.get_config()
                    project_data['source_language'] = config.get('source_language', 'english')
             except Exception:
                 pass
             return project_data
        return None

    async def refresh_project_files(self, project_id: str):
        """Rescans source and translation directories and updates the DB and JSON sidecar."""
        project = await self.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        source_path = project['source_path']
        
        try:
            json_manager = ProjectJsonManager(source_path)
            config = json_manager.get_config()
            translation_dirs = config.get('translation_dirs', [])
        except Exception as e:
            logger.error(f"Failed to load translation_dirs from JSON: {e}")
            translation_dirs = []

        if self.file_service:
            await self.file_service.scan_and_sync_files(project_id, source_path, translation_dirs, project['name'])
        else:
            logger.error("FileService not initialized in ProjectManager!")

    async def get_projects(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns a list of projects, ordered by last_modified."""
        projects = await self.repository.list_projects(status)
        return [p.model_dump() for p in projects]

    async def get_non_active_projects(self) -> List[Dict[str, Any]]:
        """Fetches all projects that are not 'active' (e.g., archived, deleted)."""
        # But repository list_projects filters optionally by status.
        # We need "!= 'active'". Repo might need update or we filter here.
        all_projects = await self.repository.list_projects()
        return [p.model_dump() for p in all_projects if p.status != 'active']

    # --- Project History ---

    async def log_history_event(self, project_id: str, action_type: str, description: str, snapshot_id: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        """Logs a major project event to the history table and updates project summary."""
        await self.repository.add_history_entry(
            project_id=project_id,
            action_type=action_type,
            description=description,
            snapshot_id=snapshot_id,
            extra_metadata=metadata
        )
        logger.info(f"Logged history event '{action_type}' for project {project_id}")

    async def get_project_history(self, project_id: str) -> List[Dict[str, Any]]:
        """Retrieves history for a project as a list of dictionaries."""
        history = await self.repository.get_project_history(project_id)
        return [h.model_dump() for h in history]

    async def delete_history_event(self, history_id: str):
        """Deletes a history event."""
        await self.repository.delete_history_event(history_id)
        logger.info(f"Deleted history event {history_id}")

    # --- Workflows ---

    async def run_incremental_update_workflow(self, config: "IncrementalUpdateConfig"):
        """Orchestrates the incremental update workflow."""
        from scripts.workflows.update_translate import run_incremental_update
        from scripts.app_settings import LANGUAGE_BY_CODE, GAME_PROFILES, GAME_PROFILES_BY_ID
        
        project_id = config.project_id
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get language and game info
        source_lang_code = project.get("source_language", "en")
        # Handle cases where source_language might be 'english' instead of 'en' 
        # (check paradox_to_iso in utils if needed, but let's assume code for now)
        source_lang_info = LANGUAGE_BY_CODE.get(source_lang_code)
        
        # Fallback for common name mappings if needed
        if not source_lang_info:
             if source_lang_code.lower() == 'english': source_lang_info = LANGUAGE_BY_CODE.get("en")
             else: source_lang_info = LANGUAGE_BY_CODE.get("en") # Ultimate fallback

        # Target language handling (from config list)
        target_lang_infos = []
        for code in config.target_lang_codes:
            info = LANGUAGE_BY_CODE.get(code.value)
            if info:
                target_lang_infos.append(info)
        
        game_id = project.get("game_id", "victoria3")
        
        # 1. Try string ID lookup first (e.g. "victoria3")
        game_profile = GAME_PROFILES_BY_ID.get(game_id)
        
        # 2. Fallback to numeric lookup if game_id is actually a number
        if not game_profile:
            game_profile = GAME_PROFILES.get(game_id)

        if not game_profile:
             logger.error(f"Game profile not found for '{game_id}'. Available: {list(GAME_PROFILES_BY_ID.keys())}")
             # Last effort fallback to victoria3
             game_profile = GAME_PROFILES_BY_ID.get("victoria3", {})

        return await run_incremental_update(
            project_id=project_id,
            target_lang_infos=target_lang_infos,
            source_lang_info=source_lang_info,
            game_profile=game_profile,
            selected_provider=config.api_provider,
            model_name=config.model,
            dry_run=config.dry_run,
            custom_source_path=config.custom_source_path,
            use_resume=config.use_resume
        )

    async def check_project_archive(self, project_id: str) -> Dict[str, Any]:
        """Checks if there's valid archival data for this project to perform incremental update."""
        project = await self.get_project(project_id)
        if not project:
            return {"exists": False, "reason": "Project not found"}
        
        project_name = project['name']
        # Target language code is extracted dynamically from archive. 
        
        latest_version = self.archive_service.archive_manager.get_latest_version(project_name)
        if not latest_version:
            return {"exists": False, "reason": "No previous version found in archive."}
            
        target_languages = self.archive_service.archive_manager.get_archived_languages(latest_version['id'])
        if not target_languages:
            return {"exists": False, "reason": "No translations found in archive."}
        
        target_lang = self.archive_service.archive_manager.detect_target_language(latest_version['id']) or "zh-CN"
            
        return {
            "exists": True, 
            "version_id": latest_version['id'], 
            "created_at": latest_version['created_at'],
            "target_language": target_lang, # Keep as default fallback for older frontend code
            "target_languages": target_languages,
            "project_name": project_name
        }

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        p = await self.repository.get_project(project_id)
        return p.model_dump() if p else None

    async def get_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        """Returns all files for a project."""
        files = await self.repository.get_project_files(project_id)
        return [f.model_dump() for f in files]

    async def update_project_status(self, project_id: str, status: str):
        # We use the unified add_history_entry which also updates the project status/last_modified indirectly?
        # No, update_project_status specifically sets 'status'. 
        # add_history_entry only sets 'last_activity_*' and 'last_modified'.
        await self.repository.update_project_status(project_id, status)
        await self.repository.add_history_entry(
            project_id=project_id,
            action_type='status_change',
            description=f"Status updated to: {status}"
        )

    async def update_project_notes(self, project_id: str, notes: str):
        """Updates the notes for a project."""
        await self.repository.update_project_notes(project_id, notes)
        await self.log_history_event(
            project_id=project_id,
            action_type='note_added',
            description="Added a new note"
        )
        logger.info(f"Updated notes for project {project_id}")

    async def save_project_kanban(self, project_id: str, kanban_data: Dict[str, Any]):
        """Saves kanban board, updates file statuses in DB, and logs activity."""
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        await self.kanban_service.save_board_and_sync(project_id, project['source_path'], kanban_data)

    async def update_file_status_with_kanban_sync(self, project_id: str, file_id: str, status: str):
        """Updates file status in DB and also moves it in the Kanban JSON."""
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        await self.kanban_service.update_file_status_sync(project_id, project['source_path'], file_id, status)
        
        await self.repository.touch_project(project_id)

    async def update_file_status(self, project_id: str, file_path: str, status: str):
        """Updates the status of a file in a project."""
        # Use simple UPDATE via connection helper if ID not available?
        # Actually Repository delete_project uses _get_connection internally.
        # But we made repo fully async. 
        # Ideally we should use file_id. If we only have path, we need to query ID first.
        # For now, let's try to avoid direct DB here. 
        # Assuming we can find the file ID or just implementing update_file_status_by_path in repo?
        # Let's revert to using repository if possible. But repo interface is `update_file_status_by_id`.
        # I'll query for file first.
        # Wait, get_project_files returns all files. I can find it there.
        files = await self.repository.get_project_files(project_id)
        target_file = next((f for f in files if f.file_path == file_path), None)
        
        if target_file:
            await self.repository.update_file_status_by_id(target_file.file_id, status)
            await self.log_history_event(
                project_id=project_id,
                action_type='file_update',
                description=f"File {os.path.basename(file_path)} status updated to {status}"
            )
            await self.repository.touch_project(project_id)
        else:
            logger.warning(f"File {file_path} not found in project {project_id} during status update.")

    async def update_file_status_by_id(self, file_id: str, status: str):
        await self.repository.update_file_status_by_id(file_id, status)

    async def delete_project(self, project_id: str, delete_source_files: bool = False):
        try:
            project = await self.get_project(project_id)
            if not project:
                return False

            if 'source_path' in project and os.path.exists(project['source_path']):
                config_path = os.path.join(project['source_path'], '.remis_project.json')
                if os.path.exists(config_path):
                    try:
                        os.remove(config_path)
                    except Exception as e:
                        logger.error(f"Failed to delete JSON sidecar: {e}")
            
            await self.repository.delete_project(project_id)
            
            if delete_source_files and 'source_path' in project and os.path.exists(project['source_path']):
                try:
                    shutil.rmtree(project['source_path'])
                    logger.info(f"Deleted source directory: {project['source_path']}")
                except Exception as e:
                    logger.error(f"Failed to delete source directory {project['source_path']}: {e}")

            return True
                
        except Exception as e:
            logger.error(f"Failed to delete project: {e}")
            raise e

    async def add_translation_path(self, project_id: str, translation_path: str):
        """
        Adds a translation directory to the project's configuration and refreshes files.
        """
        project = await self.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        source_path = project['source_path']
        json_manager = ProjectJsonManager(source_path)
        config = json_manager.get_config()
        translation_dirs = config.get('translation_dirs', [])

        abs_path = os.path.abspath(translation_path)

        if abs_path not in translation_dirs:
            translation_dirs.append(abs_path)
            json_manager.update_config({"translation_dirs": translation_dirs})
            logger.info(f"Added translation path {abs_path} to project {project_id}")
            
            await self.log_history_event(
                project_id=project_id,
                action_type='path_registered',
                description="Auto-registered translation output path"
            )

            await self.refresh_project_files(project_id)
        else:
            logger.info(f"Translation path {abs_path} already exists for project {project_id}")

    async def update_project_metadata(self, project_id: str, game_id: str, source_language: str):
        """
        Updates the project's metadata (game_id and source_language).
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        game_id = GAME_ID_ALIASES.get(game_id.lower(), game_id)

        await self.repository.update_project_metadata(project_id, game_id, source_language)

        try:
            json_manager = ProjectJsonManager(project['source_path'])
            json_manager.update_config({"source_language": source_language})
        except Exception as e:
            logger.error(f"Failed to update source_language in JSON for project {project_id}: {e}")
        
        logger.info(f"Updated metadata for project {project_id}: game_id={game_id}, source_language={source_language}")

    async def upload_project_translations(self, project_id: str) -> Dict[str, Any]:
        """
        Scans existing translation files in the project and uploads them to the archive.
        Delegates to TranslationArchiveService.
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        result = self.archive_service.upload_project_translations(
            project_id=project_id,
            project_name=project['name'],
            source_path=project['source_path'],
            source_lang_code=project.get('source_language', 'en')
        )
        
        if result.get('status') == 'success':
             match_count = result.get('match_count', 0)
             await self.log_history_event(
                project_id,
                'archive_update',
                f"Uploaded {match_count} translations to archive using exact key:version matching."
            )
        
        return result
