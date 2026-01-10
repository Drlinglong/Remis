import sqlite3
import os
import shutil
import uuid
import re
import datetime
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from scripts.app_settings import PROJECTS_DB_PATH, SOURCE_DIR, GAME_ID_ALIASES

# Configure logger
logger = logging.getLogger(__name__)

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services.kanban_service import KanbanService
from scripts.core.archive_manager import archive_manager
from scripts.core.loc_parser import parse_loc_file
from scripts.utils.i18n_utils import paradox_to_iso

@dataclass
class Project:
    project_id: str
    name: str
    game_id: str
    source_path: str
    target_path: str
    status: str  # 'active', 'archived', 'deleted'
    created_at: str
    notes: str = "" # Added notes field

@dataclass
class ProjectFile:
    file_id: str
    project_id: str
    file_path: str  # Relative path within the project source
    status: str  # 'todo', 'proofreading', 'done'
    original_key_count: int
    line_count: int = 0 # Added line count
    file_type: str = 'source' # 'source' or 'translation'

class ProjectManager:
    def __init__(self, file_service=None, project_repository=None, kanban_service=None, db_path: str = PROJECTS_DB_PATH):
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

        # Fallback for KanbanService (Legacy/Test support)
        # Allows instantiation without arguments, but production code should ALWAYS inject.
        if not self.kanban_service:
            if self.file_service and hasattr(self.file_service, 'kanban_service'):
                 self.kanban_service = self.file_service.kanban_service
            else:
                from scripts.core.services.kanban_service import KanbanService
                self.kanban_service = KanbanService()
        
        # Fallback for Repository (Legacy/Test support)
        if not self.repository:
            from scripts.core.repositories.project_repository import ProjectRepository
            self.repository = ProjectRepository(db_path)

    def create_project(self, name: str, folder_path: str, game_id: str, source_language: str) -> Dict[str, Any]:
        """
        Creates a new project.
        1. Moves folder to SOURCE_DIR if not already there.
        2. Scans for files.
        3. Creates DB records.
        4. Initializes JSON sidecar.
        """
        # Normalize game_id
        game_id = GAME_ID_ALIASES.get(game_id.lower(), game_id)
        
        logger.info(f"Creating project '{name}' from '{folder_path}' for game '{game_id}' (Source: {source_language})")

        # 1. Handle Folder Movement/Validation
        source_root = os.path.abspath(SOURCE_DIR)
        abs_folder_path = os.path.abspath(folder_path)

        final_source_path = abs_folder_path

        # Check if folder is inside SOURCE_DIR
        if not abs_folder_path.startswith(source_root):
            logger.info(f"Folder {abs_folder_path} is not in {source_root}. Moving...")
            target_dir_name = os.path.basename(abs_folder_path)
            final_source_path = os.path.join(source_root, target_dir_name)

            # Handle naming collision
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
        
        from scripts.schemas.project import Project as PydanticProject # Renamed to avoid conflict with dataclass Project
        
        new_project = PydanticProject(
            project_id=project_id,
            name=name,
            game_id=game_id,
            source_path=final_source_path,
            source_language=source_language,
            status='active',
            created_at=now,
            last_modified=now
        )
        
        saved_project = self.repository.create_project(new_project)
        
        # Initialize JSON sidecar with empty translation_dirs
        # User will add translation directories via Manage Paths UI
        json_manager = ProjectJsonManager(final_source_path)
        json_manager.update_config({
            "translation_dirs": [],
            "source_language": source_language
        })

        # Scan files (Initial Scan)
        self.refresh_project_files(project_id)
        
        return saved_project.model_dump()

    def get_project_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves project details associated with a specific file ID."""
        project_data = self.repository.get_project_by_file_id(file_id)
        if project_data:
             # Fetch source_language from JSON if source_path exists in data
             # The repo returns p.*, so source_path is there.
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

    def refresh_project_files(self, project_id: str):
        """Rescans source and translation directories and updates the DB and JSON sidecar."""
        project = self.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        source_path = project['source_path']
        
        # Get translation_dirs from JSON sidecar
        try:
            json_manager = ProjectJsonManager(source_path)
            config = json_manager.get_config()
            translation_dirs = config.get('translation_dirs', [])
        except Exception as e:
            logger.error(f"Failed to load translation_dirs from JSON: {e}")
            translation_dirs = []

        # Delegate to FileService
        if self.file_service:
            self.file_service.scan_and_sync_files(project_id, source_path, translation_dirs, project['name'])
        else:
            logger.error("FileService not initialized in ProjectManager!")


    # Removed _sync_kanban_with_files (Logic moved to KanbanService)

    def get_projects(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns a list of projects, ordered by last_modified."""
        projects = self.repository.list_projects(status)
        # Convert Pydantic models to dicts for API compatibility
        return [p.model_dump() for p in projects]

    def get_non_active_projects(self) -> List[Dict[str, Any]]:
        """Fetches all projects that are not 'active' (e.g., archived, deleted)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE status != 'active' ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        p = self.repository.get_project(project_id)
        return p.model_dump() if p else None

    def get_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        """Returns all files for a project."""
        files = self.repository.get_project_files(project_id)
        return [f.model_dump() for f in files]

    def update_project_status(self, project_id: str, status: str):
        self.repository.update_project_status(project_id, status)
        self.repository.add_activity_log(
            project_id=project_id,
            activity_type='status_change',
            description=f"Status updated to: {status}"
        )

    def update_project_notes(self, project_id: str, notes: str):
        """Updates the notes for a project."""
        self.repository.update_project_notes(project_id, notes)
        self.repository.add_activity_log(
            project_id=project_id,
            activity_type='note_added',
            description="Added a new note"
        )
        logger.info(f"Updated notes for project {project_id}")

    def save_project_kanban(self, project_id: str, kanban_data: Dict[str, Any]):
        """Saves kanban board, updates file statuses in DB, and logs activity."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # 1. Get Old Board for Diff (Read before save)
        try:
            old_board = self.kanban_service.get_board(project['source_path'])
            old_tasks = old_board.get("tasks", {})
        except Exception:
            old_tasks = {}

        # 2. Save NEW Board to disk
        self.kanban_service.save_board(project['source_path'], kanban_data)
        
        # 3. Process Diff and Log
        try:
            new_tasks = kanban_data.get("tasks", {})
            moved_tasks = []
            for tid, new_task in new_tasks.items():
                old_task = old_tasks.get(tid)
                if old_task and old_task.get('status') != new_task.get('status'):
                    moved_tasks.append(new_task)
            
            # Update DB for moved files
            for task in moved_tasks:
                if task.get('type') == 'file':
                    self.repository.update_file_status_by_id(task['id'], task['status'])
            
            # Log with De-duplication check
            if moved_tasks:
                first = moved_tasks[0]
                desc = f"Moved '{first.get('title')}' to {first.get('status')}"
                if len(moved_tasks) > 1:
                    desc += f" (and {len(moved_tasks)-1} others)"
                
                # Check for recent identical log (within last 3 logs) to prevent race-induced doubles
                recent_logs = self.repository.get_recent_logs(limit=3)
                is_dupe = any(l['project_id'] == project_id and l['type'] == 'file_update' and l['description'] == desc for l in recent_logs)
                
                if not is_dupe:
                    self.repository.add_activity_log(project_id, 'file_update', desc)
                else:
                    logger.info(f"Suppressed duplicate file_update log for {project_id}")
            else:
                # Layout update de-dupe
                recent_logs = self.repository.get_recent_logs(limit=5)
                is_dupe = any(l['project_id'] == project_id and l['type'] == 'kanban_update' for l in recent_logs)
                if not is_dupe:
                    self.repository.add_activity_log(project_id, 'kanban_update', "Updated Kanban board layout")
                
        except Exception as e:
            logger.error(f"Error during kanban diff/sync: {e}")

        # 4. Final Touch
        self.repository.touch_project(project_id)
        logger.info(f"Saved kanban and synchronized status for project {project_id}")

    async def update_file_status_with_kanban_sync(self, project_id: str, file_id: str, status: str):
        """Updates file status in DB and also moves it in the Kanban JSON."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # 1. Update DB Status
        self.repository.update_file_status_by_id(file_id, status)

        # 2. Update Kanban Board (JSON sidecar)
        try:
            board = self.kanban_service.get_board(project['source_path'])
            tasks = board.get("tasks", {})
            
            # Find the task corresponding to this file_id
            target_key = None
            if file_id in tasks:
                target_key = file_id
            else:
                # Fallback: search values for internal id (ID alignment issue)
                for tid, t_obj in tasks.items():
                    if t_obj.get('id') == file_id:
                        target_key = tid
                        break
            
            if target_key:
                # If key is misaligned, fix it now
                if target_key != file_id:
                    tasks[file_id] = tasks.pop(target_key)
                    target_key = file_id
                    logger.info(f"ProjectManager: Aligned task key during status update: {file_id}")

                old_status = tasks[target_key].get('status')
                if old_status != status:
                    tasks[target_key]['status'] = status
                    self.kanban_service.save_board(project['source_path'], board)
                    
                    # Log activity
                    file_name = tasks[target_key].get('title', file_id)
                    self.repository.add_activity_log(
                        project_id, 
                        'file_update', 
                        f"Changed status of '{file_name}' to {status}"
                    )
            else:
                # If task doesn't exist in Kanban but exists in DB, we should probably trigger a sync
                logger.warning(f"Task for file {file_id} not found in Kanban. Triggering sync...")
                self.refresh_project_files(project_id)

        except Exception as e:
            logger.error(f"Failed to sync kanban after individual file update: {e}")

        self.repository.touch_project(project_id)

    def update_file_status(self, project_id: str, file_path: str, status: str):
        """Updates the status of a file in a project."""
        # Find file_id or update by path via repo if repo supports it
        # Current repo doesn't have update_file_status_by_path, but Manager had it.
        # Let's add it to repo or just use SQL here for one last time (not recommended).
        # Better: use repository.update_file_status_by_id if we have the ID.
        # For simplicity and isolation, I'll update the repo to handle this or use the safer path.
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE project_files
                SET status = ?
                WHERE project_id = ? AND file_path = ?
            ''', (status, project_id, file_path))
            conn.commit()
            
            # Log activity
            self.repository.add_activity_log(
                project_id=project_id,
                activity_type='file_update',
                description=f"File {os.path.basename(file_path)} status updated to {status}"
            )
            self.repository.touch_project(project_id) # Trigger last_modified
        finally:
            conn.close()

    def update_file_status_by_id(self, file_id: str, status: str):
        self.repository.update_file_status_by_id(file_id, status)

    def delete_project(self, project_id: str, delete_source_files: bool = False):
        try:
            project = self.get_project(project_id)
            if not project:
                return False

            # Remove config file from disk first if exists
            if 'source_path' in project and os.path.exists(project['source_path']):
                config_path = os.path.join(project['source_path'], '.remis_project.json')
                if os.path.exists(config_path):
                    try:
                        os.remove(config_path)
                    except Exception as e:
                        logger.error(f"Failed to delete JSON sidecar: {e}")
            
            # Delete from DB via Repository
            self.repository.delete_project(project_id)
            
            # Optional: Delete source folder
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

    def add_translation_path(self, project_id: str, translation_path: str):
        """
        Adds a translation directory to the project's configuration and refreshes files.
        """
        project = self.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        source_path = project['source_path']
        json_manager = ProjectJsonManager(source_path)
        config = json_manager.get_config()
        translation_dirs = config.get('translation_dirs', [])

        # Normalize path
        abs_path = os.path.abspath(translation_path)

        if abs_path not in translation_dirs:
            translation_dirs.append(abs_path)
            json_manager.update_config({"translation_dirs": translation_dirs})
            logger.info(f"Added translation path {abs_path} to project {project_id}")
            
            # Log activity
            self.repository.add_activity_log(
                project_id=project_id,
                activity_type='path_registered',
                description="Auto-registered translation output path"
            )

            # Refresh files to include new translation files
            self.refresh_project_files(project_id)
        else:
            logger.info(f"Translation path {abs_path} already exists for project {project_id}")

    def update_project_metadata(self, project_id: str, game_id: str, source_language: str):
        """
        Updates the project's metadata (game_id and source_language).
        """
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Normalize game_id
        game_id = GAME_ID_ALIASES.get(game_id.lower(), game_id)

        # Update DB (game_id and source_language)
        # Note: repository.update_project_metadata updates both game_id and source_language
        self.repository.update_project_metadata(project_id, game_id, source_language)

        # Update JSON sidecar (source_language)
        try:
            json_manager = ProjectJsonManager(project['source_path'])
            json_manager.update_config({"source_language": source_language})
        except Exception as e:
            logger.error(f"Failed to update source_language in JSON for project {project_id}: {e}")
            # Non-fatal, but should be noted
        
        logger.info(f"Updated metadata for project {project_id}: game_id={game_id}, source_language={source_language}")

    def upload_project_translations(self, project_id: str) -> Dict[str, Any]:
        """
        Scans existing translation files in the project and uploads them to the archive.
        """
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        source_path = project['source_path']
        project_name = project['name']

        # 1. Get Project Config
        json_manager = ProjectJsonManager(source_path)
        config = json_manager.get_config()
        translation_dirs = config.get('translation_dirs', [])
        
        if not translation_dirs:
            return {"status": "warning", "message": "No translation directories configured."}

        # 2. Parse Source Files to build the "Expected Structure"
        # We need this to identify which filename a key belongs to in the archive
        source_files_data = []
        all_source_keys = {} # key -> filename
        
        # We search for .yml/.yaml in source_path
        for root, _, files in os.walk(source_path):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    full_path = Path(os.path.join(root, file))
                    try:
                        entries = parse_loc_file(full_path)
                        if entries:
                            filename = os.path.basename(full_path)
                            source_files_data.append({
                                'filename': filename,
                                'key_map': [e[0] for e in entries],
                                'texts_to_translate': [e[1] for e in entries]
                            })
                            for e in entries:
                                all_source_keys[e[0]] = filename
                    except Exception as e:
                        logger.error(f"Failed to parse source file {full_path}: {e}")

        if not source_files_data:
            return {"status": "warning", "message": "No source files found to match against."}

        # 3. Initialize Archive Version
        mod_id = archive_manager.get_or_create_mod_entry(project_name, project_id)
        if not mod_id:
            return {"status": "error", "message": "Failed to initialize mod archive entry."}
        
        version_id = archive_manager.create_source_version(mod_id, source_files_data)
        if not version_id:
            return {"status": "error", "message": "Failed to create source version snapshot."}

        # 4. Scan and Parse Translation Files
        # We will collect translations into file_results grouped by source filename
        file_results = {} # target_iso -> {source_filename -> [translated_texts]}
        match_count = 0
        
        from scripts.schemas.common import LanguageCode

        for trans_dir in translation_dirs:
            if not os.path.exists(trans_dir): continue
            for root, _, files in os.walk(trans_dir):
                for file in files:
                    if file.endswith(('.yml', '.yaml', '.txt')):
                        full_path = Path(os.path.join(root, file))
                        
                        # Detect Language Code from filename (_l_xxxx.yml)
                        lang_code_iso = "zh-CN" # Default
                        lang_match = re.search(r"_l_(\w+)\.(yml|yaml)$", file, re.IGNORECASE)
                        if lang_match:
                            try:
                                lang_code_iso = LanguageCode.from_str(lang_match.group(1)).value
                            except: pass
                        
                        if lang_code_iso not in file_results:
                            file_results[lang_code_iso] = {}

                        try:
                            # Use loc_parser which now captures KEY:version
                            entries = parse_loc_file(full_path)
                            if not entries: continue
                            
                            for key, value in entries:
                                source_filename = all_source_keys.get(key)
                                # [FALLBACK] If no exact match, try without :version suffix
                                if not source_filename and ":" in key:
                                    source_filename = all_source_keys.get(key.split(':')[0])
                                
                                if source_filename:
                                    # Find index of key in source file
                                    # Use find instead of next(...) for clarity
                                    source_file_data = next((fd for fd in source_files_data if fd['filename'] == source_filename), None)
                                    if not source_file_data: continue

                                    if source_filename not in file_results[lang_code_iso]:
                                        file_results[lang_code_iso][source_filename] = list(source_file_data['texts_to_translate'])
                                    
                                    try:
                                        # Try exact match first, then fallback
                                        try:
                                            idx = source_file_data['key_map'].index(key)
                                        except ValueError:
                                            if ":" in key:
                                                idx = source_file_data['key_map'].index(key.split(':')[0])
                                            else:
                                                # Also try matching key with any version suffix if source_file_data has them
                                                idx = -1
                                                for i, k in enumerate(source_file_data['key_map']):
                                                    if k.split(':')[0] == key:
                                                        idx = i
                                                        break
                                                if idx == -1: raise ValueError("Key not found")

                                        file_results[lang_code_iso][source_filename][idx] = value
                                        match_count += 1
                                    except ValueError:
                                        pass
                        except Exception as e:
                            logger.error(f"Failed to parse translation file {full_path}: {e}")

        # 5. Archive the results
        if match_count > 0:
            for lang_iso, results in file_results.items():
                if results:
                    archive_manager.archive_translated_results(version_id, results, source_files_data, lang_iso)
            
            # Add activity log
            self.repository.add_activity_log(
                project_id,
                'archive_update',
                f"Uploaded {match_count} translations to archive using exact key:version matching."
            )
            
            return {
                "status": "success", 
                "message": f"Successfully uploaded {match_count} translations across {len(file_results)} files.",
                "match_count": match_count
            }
        else:
            return {"status": "info", "message": "No matching keys found in translation files."}
