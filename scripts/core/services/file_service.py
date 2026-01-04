import os
import uuid
import logging
from typing import List, Dict, Any
from pathlib import Path

from scripts.core.loc_parser import parse_loc_file
from scripts.utils.i18n_utils import iso_to_paradox

logger = logging.getLogger(__name__)

class FileService:
    """
    Service to orchestrate file scanning, database synchronization, and notification of other services.
    Acts as the source of truth for 'Disk State' -> 'DB State'.
    """

    def __init__(self, kanban_service, archive_manager, project_repository):
        self.kanban_service = kanban_service
        self.archive_manager = archive_manager
        self.project_repository = project_repository

    def scan_dir(self, root_path: str, file_type: str, search_lang: str, project_id: str) -> List[Dict]:
        """
        Scans a directory for localization files.
        search_lang: The Paradox-style language key (e.g. 'simp_chinese') to filter/identify files.
        """
        if not os.path.exists(root_path):
            logger.warning(f"FileService: Directory not found: {root_path}")
            return []
        
        files_found = []
        for root, dirs, files in os.walk(root_path):
            # Exclude hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                # We can check if file matches the language pattern to be safer, 
                # but currently we just pick up all typical Loc extensions.
                # If we want to strictly follow the language, we could filter here.
                # For now, keeping it broad to catch everything, but we log the context.
                if file.endswith(('.yml', '.yaml', '.txt', '.csv', '.json')):
                    # Special case for Paradox metadata
                    current_file_type = file_type
                    if file == 'metadata.json' or file == 'descriptor.mod':
                        current_file_type = 'metadata'
                    elif file == '.remis_project.json':
                        # Internal project file, skip or mark as system?
                        # User asked if we still use it -> Yes.
                        # Do we want it in the file list? Maybe as 'config'?
                        # Let's include it for transparency but mark as config.
                        current_file_type = 'config'
                    
                    full_path = os.path.join(root, file)
                    
                    # Count lines
                    line_count = 0
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            line_count = sum(1 for _ in f)
                    except Exception as e:
                        logger.error(f"Failed to count lines for {full_path}: {e}")

                    files_found.append({
                        # Use lower() for path to ensure case-insensitivity on Windows
                        'file_id': str(uuid.uuid5(uuid.NAMESPACE_URL, full_path.lower().replace('\\', '/'))),
                        'project_id': project_id,
                        'file_path': full_path,
                        'status': 'todo',
                        'original_key_count': 0,
                        'line_count': line_count,
                        'file_type': current_file_type
                    })
        
        logger.info(f"FileService: Scanned {file_type} dir {root_path}: {len(files_found)} files")
        return files_found

    def scan_and_sync_files(self, project_id: str, source_path: str, translation_dirs: List[str], project_name: str) -> None:
        """
        Orchestrates:
        1. Get Project Config (for Source Lang)
        2. Scan Files (Source + Translations) using ISO -> Paradox mapping
        3. Sync to DB
        4. Trigger Kanban & Archive
        """
        # 1. Fetch Source Language from DB (Repository)
        # We need the ISO code from DB to convert to Paradox key for disk operations.
        # Although scan_dir currently grabs everything, future strict scanning will need this.
        # And ArchiveManager/Kanban might need to know the 'disk language'.
        project = self.project_repository.get_project(project_id)
        if not project:
            logger.error(f"FileService: Project {project_id} not found during sync")
            return

        iso_source = project.source_language
        disk_source_lang = iso_to_paradox(iso_source)
        
        logger.info(f"FileService: Syncing '{project_name}'. ISO='{iso_source}' -> Disk='{disk_source_lang}'")
        
        files_to_upsert = []

        # Scan source directory
        files_to_upsert.extend(self.scan_dir(source_path, 'source', disk_source_lang, project_id))
        
        # Scan translation directories
        for trans_dir in translation_dirs:
            files_to_upsert.extend(self.scan_dir(trans_dir, 'translation', disk_source_lang, project_id))

        # 2. JSON Hydration (Status Reconciliation)
        # Establish .remis_project.json as the SSOT for file statuses.
        try:
            kanban_data = self.kanban_service.get_board(source_path)
            kanban_tasks = kanban_data.get("tasks", {})
            
            for f in files_to_upsert:
                file_id = f['file_id']
                if file_id in kanban_tasks:
                    # Use status from JSON if it exists
                    json_status = kanban_tasks[file_id].get('status')
                    if json_status:
                        f['status'] = json_status
            
            logger.info("FileService: Hydrated file statuses from JSON sidecar.")
        except Exception as e:
            logger.warning(f"FileService: Could not hydrate from JSON (normal for new projects): {e}")

        logger.info(f"FileService: Total files to upsert: {len(files_to_upsert)}")

        # 3. Update Database (Upsert & Clean) via Repository
        try:
            # Get existing file IDs for this project
            existing_file_ids = set(self.project_repository.get_project_file_ids(project_id))
            
            # Upsert new/updated files (Batch)
            self.project_repository.batch_upsert_files(files_to_upsert)
            
            # Calculate obsolete files
            current_scan_ids = set(f['file_id'] for f in files_to_upsert)
            files_to_delete = existing_file_ids - current_scan_ids
            
            if files_to_delete:
                logger.info(f"FileService: Removing {len(files_to_delete)} obsolete files/ghosts.")
                self.project_repository.delete_files_by_ids(list(files_to_delete))

        except Exception as e:
            logger.error(f"FileService: DB Sync failed: {e}")
            raise e

        # 3. Notify Kanban Service
        try:
            self.kanban_service.sync_files_to_board(source_path, files_to_upsert)
        except Exception as e:
            logger.error(f"FileService: Kanban Sync failed: {e}")

        # 4. Notify Archive Manager
        self._notify_archive_manager(project_id, project_name, files_to_upsert)

    def _notify_archive_manager(self, project_id: str, project_name: str, files: List[Dict]):
        """
        Orchestrates archiving logic.
        """
        try:
            source_files_data = []
            for f in files:
                if f['file_type'] == 'source' and f['file_path'].endswith(('.yml', '.yaml')):
                    try:
                        entries = parse_loc_file(Path(f['file_path']))
                        if entries:
                            source_files_data.append({
                                'filename': os.path.basename(f['file_path']),
                                'key_map': [e[0] for e in entries],
                                'texts_to_translate': [e[1] for e in entries]
                            })
                    except Exception as e:
                        logger.error(f"Failed to parse {f['file_path']} for archiving: {e}")

            if source_files_data:
                # Use project.name as mod name for archive
                mod_id = self.archive_manager.get_or_create_mod_entry(project_name, project_id)
                if mod_id:
                    self.archive_manager.create_source_version(mod_id, source_files_data)
                    logger.info("FileService: Archive updated.")
        except Exception as e:
             logger.error(f"FileService: Archive notification failed: {e}")
