import os
import logging
from typing import List, Dict, Any, Optional
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.strategies.file_linking import FileLinkingStrategy, ParadoxFileLinkingStrategy

logger = logging.getLogger(__name__)

class KanbanService:
    """
    Service to manage Kanban board state and logic.
    Strictly handles data manipulation (JSON Sidecar) and does NOT perform disk scanning.
    """

    def __init__(self, repository=None, linking_strategy: Optional[FileLinkingStrategy] = None):
        # Default to Paradox strategy if none provided
        self.linking_strategy = linking_strategy or ParadoxFileLinkingStrategy()
        self.repository = repository

    def get_board(self, source_path: str) -> Dict[str, Any]:
        """
        Retrieves the Kanban board data from the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            return json_manager.get_kanban_data()
        except Exception as e:
            logger.error(f"Failed to get kanban board for {source_path}: {e}")
            raise

    def save_board(self, source_path: str, kanban_data: Dict[str, Any]) -> None:
        """
        Saves the Kanban board data to the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            json_manager.save_kanban_data(kanban_data)
        except Exception as e:
            logger.error(f"Failed to save kanban board for {source_path}: {e}")
            raise

    async def update_file_status_sync(self, project_id: str, source_path: str, file_id: str, status: str) -> None:
        """
        Updates file status in DB and also moves it in the Kanban JSON.
        """
        if not self.repository:
            logger.warning("KanbanService: Repository not initialized, skipping DB sync")
            return

        await self.repository.update_file_status_by_id(file_id, status)

        try:
            board = self.get_board(source_path)
            tasks = board.get("tasks", {})
            
            target_key = None
            if file_id in tasks:
                target_key = file_id
            else:
                for tid, t_obj in tasks.items():
                    if t_obj.get('id') == file_id:
                        target_key = tid
                        break
            
            if target_key:
                # Synchronize ID if changed (e.g. migration)
                if target_key != file_id:
                    tasks[file_id] = tasks.pop(target_key)
                    target_key = file_id
                    logger.info(f"KanbanService: Aligned task key during status update: {file_id}")

                old_status = tasks[target_key].get('status')
                if old_status != status:
                    tasks[target_key]['status'] = status
                    self.save_board(source_path, board)
                    
                    file_name = tasks[target_key].get('title', file_id)
                    await self.repository.add_history_entry(
                        project_id=project_id,
                        action_type='file_update',
                        description=f"Changed status of '{file_name}' to {status}"
                    )
            else:
                logger.warning(f"Task for file {file_id} not found in Kanban. Skipping JSON update.")

        except Exception as e:
            logger.error(f"Failed to sync kanban after individual file update: {e}")

    async def save_board_and_sync(self, project_id: str, source_path: str, kanban_data: Dict[str, Any]) -> None:
        """
        Saves kanban board, updates file statuses in DB, and logs activity.
        """
        if not self.repository:
            # Fallback to simple save if no repo
            self.save_board(source_path, kanban_data)
            return

        try:
            old_board = self.get_board(source_path)
            old_tasks = old_board.get("tasks", {})
        except Exception:
            old_tasks = {}

        self.save_board(source_path, kanban_data)
        
        try:
            new_tasks = kanban_data.get("tasks", {})
            moved_tasks = []
            for tid, new_task in new_tasks.items():
                old_task = old_tasks.get(tid)
                if old_task and old_task.get('status') != new_task.get('status'):
                    moved_tasks.append(new_task)
            
            # Batch update DB statuses
            for task in moved_tasks:
                if task.get('type') == 'file':
                    await self.repository.update_file_status_by_id(task['id'], task['status'])
            
            if moved_tasks:
                # Logging logic
                first = moved_tasks[0]
                desc = f"Moved '{first.get('title')}' to {first.get('status')}"
                if len(moved_tasks) > 1:
                    desc += f" (and {len(moved_tasks)-1} others)"
                
                recent_logs = await self.repository.get_recent_logs(limit=3)
                is_dupe = any(l['project_id'] == project_id and l['type'] == 'file_update' and l['description'] == desc for l in recent_logs)
                
                if not is_dupe:
                    await self.repository.add_history_entry(project_id, 'file_update', desc)
                else:
                    logger.info(f"Suppressed duplicate file_update log for {project_id}")
            else:
                recent_logs = await self.repository.get_recent_logs(limit=5)
                # Check for general kanban update (layout changes, etc)
                # This is a heuristic, avoiding spam
                is_dupe = any(l['project_id'] == project_id and l['type'] == 'kanban_update' for l in recent_logs)
                if not is_dupe:
                     await self.repository.add_history_entry(project_id, 'kanban_update', "Updated Kanban board layout")
                
        except Exception as e:
            logger.error(f"Error during kanban diff/sync: {e}")

        await self.repository.touch_project(project_id)
        logger.info(f"Saved kanban and synchronized status for project {project_id}")

    def sync_files_to_board(self, source_path: str, files: List[Dict[str, Any]]) -> None:
        """
        Syncs a list of files (provided by an external scanner) to the Kanban board.
        Delegates core linking and task creation logic to the active FileLinkingStrategy.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            kanban_data = json_manager.get_kanban_data()
            tasks = kanban_data.get("tasks", {})
            columns = kanban_data.get("columns", [])
            
            # Robustness: Ensure default columns exist
            default_columns = ["todo", "in_progress", "proofreading", "paused", "done"]
            if len(columns) < 3:
                columns = default_columns
            
            # DELEGATE: Use the strategy to process files and update tasks
            updated_tasks = self.linking_strategy.process_files(source_path, files, tasks)

            # Save Board
            json_manager.save_kanban_data({
                "columns": columns,
                "tasks": updated_tasks,
                "column_order": kanban_data.get("column_order", columns)
            })
            logger.info(f"KanbanService: Synced board for {source_path}. Total tasks: {len(updated_tasks)}")
            
        except Exception as e:
            logger.error(f"Failed to sync files to kanban: {e}")
            raise
